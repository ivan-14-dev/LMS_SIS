# 🔍 Audit Technique des SIS - Rapport Complet

## 📊 Résumé Exécutif

| Catégorie | Criticité | SIS Secondaire | SIS Supérieur |
|-----------|-----------|----------------|---------------|
| **Sécurité** | 🔴 Critique | 5 problèmes | 5 problèmes |
| **Architecture** | 🟠 Majeur | 4 problèmes | 4 problèmes |
| **Code Quality** | 🟡 Moyen | 8 problèmes | 8 problèmes |
| **Performance** | 🟡 Moyen | 3 problèmes | 3 problèmes |
| **Tests** | 🔴 Critique | Non fonctionnels | Non fonctionnels |
| **Infrastructure** | 🟠 Majeur | 2 problèmes | 2 problèmes |

---

## 🔴 1. PROBLÈMES CRITIQUES DE SÉCURITÉ

### 1.1 SECRET_KEY en dur avec valeur par défaut faible
**Fichiers:** `config/settings.py` (les deux SIS)
```python
# ❌ PROBLÈME
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
```

**Impact:** Si la variable d'environnement n'est pas définie, la clé secrète est prévisible.

**Solution:**
```python
# ✅ CORRECTION
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in environment")
```

### 1.2 DEBUG=True par défaut
```python
# ❌ PROBLÈME
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
```

**Impact:** En production, si la variable n'est pas définie, DEBUG sera True (fuite d'informations sensibles).

**Solution:**
```python
# ✅ CORRECTION  
DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"
```

### 1.3 ALLOWED_HOSTS = "*" par défaut
```python
# ❌ PROBLÈME
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")
```

**Impact:** Vulnérabilité aux attaques HTTP Host header.

### 1.4 WEBHOOK_SECRET faible en développement
**Fichier:** `apps/integration/api.py`
```python
# ❌ PROBLÈME
secret = getattr(settings, "WEBHOOK_SECRET", "dev-secret")
```

**Impact:** Si non configuré, les webhooks sont validés avec un secret prévisible.

### 1.5 Credentials OAuth non validés
**Fichier:** `apps/integration/edx_client.py`
```python
# ❌ PROBLÈME - aucune validation
self.oauth_client_id = oauth_client_id or getattr(settings, "EDX_OAUTH_CLIENT_ID", "sis-client")
self.oauth_client_secret = oauth_client_secret or getattr(settings, "EDX_OAUTH_CLIENT_SECRET", "")
```

**Impact:** Le client peut fonctionner avec des credentials vides.

---

## 🟠 2. PROBLÈMES D'ARCHITECTURE

### 2.1 Duplication de code massive entre les deux SIS
**Problème:** Les fichiers `config/settings.py` des deux SIS sont **quasiment identiques** (>90%).

**Fichiers dupliqués:**
- `config/settings.py` (200+ lignes identiques)
- `apps/core/middleware.py` (60 lignes identiques)
- `apps/core/logging.py` (identique)
- `apps/integration/edx_client.py` (~95% identique)
- `apps/integration/sync_service.py` (~90% identique)

**Solution:** Créer un package `sis_common` partagé:
```
sis_apps/
├── sis_common/                  # NOUVEAU
│   ├── settings/
│   │   ├── base.py              # Configuration commune
│   │   └── security.py
│   ├── middleware/
│   ├── integration/
│   │   ├── base_client.py
│   │   └── base_sync_service.py
│   └── core/
├── sis_secondaire/
│   └── config/
│       └── settings.py          # extends sis_common.settings.base
└── sis_superieur/
```

### 2.2 Serializers vides
**Constat:** 58 fichiers `serializers.py` existent mais sont **tous vides**:
```python
"""Serializers for etudiants."""
# Serializers for etudiants   <-- Commentaire uniquement!
```

**Impact:** Aucune validation des données API, pas de transformation, pas de documentation OpenAPI correcte.

### 2.3 ViewSets incomplets
**Exemple:** `apps/eleves/api.py`
```python
class ElevesViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    # queryset et serializer_class à définir  <-- NON IMPLÉMENTÉ!
    
    def get_queryset(self):
        return []  # ❌ Retourne toujours vide!
```

**Constat:** Tous les ViewSets retournent des listes vides.

### 2.4 Migrations non générées
**Constat:** Tous les dossiers `migrations/` ne contiennent que `__init__.py`.

```bash
# Exemple
sis_apps/sis_superieur/apps/integration/migrations/
└── __init__.py   # PAS DE MIGRATIONS
```

**Impact:** La base de données ne peut pas être initialisée.

---

## 🟡 3. PROBLÈMES DE QUALITÉ DE CODE

### 3.1 Gestion d'erreurs trop générique
**Pattern répété 20+ fois:**
```python
# ❌ PROBLÈME
try:
    # code
except Exception as e:
    return Response({"error": str(e)}, status=500)
```

**Impact:** 
- Toutes les erreurs retournent 500 (même les 400 bad request)
- Pas de logging structuré
- Perte d'information de debug

**Solution:**
```python
# ✅ CORRECTION
from rest_framework.exceptions import ValidationError, NotFound

try:
    # code
except ObjectDoesNotExist as e:
    raise NotFound(detail=str(e))
except ValueError as e:
    raise ValidationError(detail=str(e))
except IntegrationError as e:
    logger.exception("Integration failed", extra={"user_id": user_id})
    raise ServiceUnavailable(detail="LMS temporarily unavailable")
```

### 3.2 Objects.get() sans try/except dans les services
**Fichier:** `sync_service.py`
```python
# ❌ PROBLÈME - peut lever DoesNotExist non catchée
mapping = EdxUserMapping.objects.get(user_sis=etudiant.user)
```

**Solution:**
```python
# ✅ CORRECTION
try:
    mapping = EdxUserMapping.objects.get(user_sis=etudiant.user)
except EdxUserMapping.DoesNotExist:
    raise SyncError(f"User {etudiant.user.id} has no LMS mapping")
```

### 3.3 Absence de validation des données d'entrée API
**Exemple:** `apps/integration/api.py`
```python
# ❌ PROBLÈME - aucune validation
etudiant_id = request.data.get("etudiant_id")
course_mapping_id = request.data.get("course_mapping_id")
# Utilisé directement sans validation
```

### 3.4 Imports locaux dans les fonctions (anti-pattern)
```python
# ❌ PROBLÈME - import à chaque appel de fonction
@shared_task
def process_user_webhook(payload):
    from .webhook_handlers import WebhookHandler  # Import local répété
    from apps.etudiants.models import Etudiant
    from apps.notes.models import Note
```

### 3.5 Pas de typing/annotations
```python
# ❌ Actuel
def sync_user_to_lms(self, user_sis, role="student"):
    
# ✅ Recommandé
def sync_user_to_lms(
    self, 
    user_sis: Utilisateur, 
    role: Literal["student", "staff", "instructor"] = "student"
) -> EdxUserMapping:
```

### 3.6 Absence de docstrings détaillées
```python
# ❌ Actuel
def sync_course_to_cms(self, ecue, annee_universitaire, display_name):
    
# ✅ Recommandé  
def sync_course_to_cms(
    self, 
    ecue: ECUE, 
    annee_universitaire: AnneeUniversitaire, 
    display_name: str
) -> EdxCourseMapping:
    """
    Synchronise un ECUE vers le CMS Open edX.
    
    Args:
        ecue: L'élément constitutif de l'UE à synchroniser
        annee_universitaire: L'année universitaire pour le run du cours
        display_name: Nom affiché dans Studio/LMS
        
    Returns:
        Le mapping créé ou mis à jour
        
    Raises:
        EdxApiError: Si la création du cours échoue
        IntegrityError: Si le mapping existe déjà
    """
```

### 3.7 Constantes magiques
```python
# ❌ PROBLÈME
pending = OutboxEvent.objects.filter(statut="pending")[:100]  # Pourquoi 100?
# ...
for enrollment in EdxEnrollment.objects.filter(is_active=True)[:500]:  # Pourquoi 500?
```

**Solution:**
```python
# ✅ config/constants.py
OUTBOX_BATCH_SIZE = 100
RECONCILE_BATCH_SIZE = 500

# Utilisation
from config.constants import OUTBOX_BATCH_SIZE
pending = OutboxEvent.objects.filter(statut="pending")[:OUTBOX_BATCH_SIZE]
```

### 3.8 Pas de rate limiting sur les API
Les endpoints de synchronisation peuvent être appelés sans limite.

---

## 🟡 4. PROBLÈMES DE PERFORMANCE

### 4.1 Requêtes N+1
**Fichier:** `tasks.py`
```python
# ❌ PROBLÈME - N+1 queries
for enrollment in EdxEnrollment.objects.filter(is_active=True)[:500]:
    course = enrollment.course  # +1 query
    user_map = EdxUserMapping.objects.get(user_sis=enrollment.etudiant.user)  # +1 query
```

**Solution:**
```python
# ✅ CORRECTION
enrollments = EdxEnrollment.objects.filter(
    is_active=True
).select_related(
    'course',
    'etudiant__user__edx_mapping'
)[:500]
```

### 4.2 Pas de pagination dans les QuerySets des ViewSets
Les ViewSets ne définissent pas de `pagination_class`.

### 4.3 Pas de cache sur les données fréquemment accédées
Exemple: les mappings utilisateurs sont récupérés à chaque opération sans cache.

---

## 🔴 5. TESTS - ÉTAT CRITIQUE

### 5.1 Tests non fonctionnels
**Constat:** Tous les fichiers `tests.py` originaux sont des stubs vides:
```python
"""Model tests for integration."""
from django.test import TestCase

class IntegrationModelTestCase(TestCase):
    pass  # Aucun test!
```

### 5.2 Factories utilisant des modèles inexistants
Les factories référencent des modèles via strings (`'etablissement.Etablissement'`) mais:
- Les migrations n'existent pas
- Les tables n'existent pas
- Les tests ne peuvent pas s'exécuter

### 5.3 Pas de tests d'intégration
Aucun test vérifiant la communication avec Open edX (même mockée).

### 5.4 Coverage = 0%
Aucune métrique de couverture de code.

---

## 🟠 6. PROBLÈMES D'INFRASTRUCTURE

### 6.1 Pas de healthcheck endpoints
Aucun endpoint `/health/` ou `/ready/` pour Kubernetes/Docker.

### 6.2 Pas de métriques Prometheus
Pas d'export de métriques pour le monitoring.

### 6.3 Logging non structuré
```python
# ❌ Actuel
logger.error(f"Failed to import grades: {e}")

# ✅ Recommandé (structured logging)
logger.error(
    "Grade import failed",
    extra={
        "course_id": mapping.course_id,
        "user_id": enrollment.etudiant.id,
        "error_type": type(e).__name__,
        "error_message": str(e),
    },
    exc_info=True
)
```

---

## 📋 7. PROBLÈMES SPÉCIFIQUES PAR MODULE

### Module Integration (Critique)

| Problème | Fichier | Impact |
|----------|---------|--------|
| Pas de retry avec backoff | `edx_client.py` | Échecs silencieux |
| Pas de circuit breaker | `sync_service.py` | Cascade de failures |
| Webhooks sans idempotence | `webhook_handlers.py` | Doublons possibles |
| Outbox sans partition | `tasks.py` | Goulot d'étranglement |

### Module Utilisateurs

| Problème | Impact |
|----------|--------|
| MFA secret en clair | Risque de compromission |
| Pas de validation email | Emails invalides acceptés |
| Password reset non implémenté | Fonctionnalité manquante |

### Module Etudiants/Eleves

| Problème | Impact |
|----------|--------|
| Photo sans validation MIME | Upload de fichiers malveillants |
| IBAN/RIB en clair | Non-conformité RGPD |
| Pas de soft delete | Perte de données historiques |

---

## ✅ 8. PLAN D'ACTION PRIORITAIRE

### Phase 1: Sécurité (Semaine 1-2)
1. [ ] Corriger SECRET_KEY et DEBUG
2. [ ] Ajouter validation des credentials OAuth
3. [ ] Configurer ALLOWED_HOSTS correctement
4. [ ] Chiffrer les données sensibles (IBAN, MFA secrets)

### Phase 2: Fondations (Semaine 3-4)
1. [ ] Générer toutes les migrations
2. [ ] Créer le package `sis_common` pour la mutualisation
3. [ ] Implémenter les serializers de base
4. [ ] Compléter les ViewSets

### Phase 3: Qualité (Semaine 5-6)
1. [ ] Ajouter typing et docstrings
2. [ ] Corriger la gestion d'erreurs
3. [ ] Optimiser les queries N+1
4. [ ] Ajouter pagination

### Phase 4: Tests (Semaine 7-8)
1. [ ] Écrire les tests unitaires manquants
2. [ ] Ajouter les tests d'intégration mockés
3. [ ] Configurer le CI avec coverage minimum 80%

### Phase 5: Production-ready (Semaine 9-10)
1. [ ] Ajouter healthchecks
2. [ ] Configurer métriques Prometheus
3. [ ] Implémenter rate limiting
4. [ ] Ajouter retry/circuit breaker

---

## 📊 Métriques de Maturité

| Critère | Score Actuel | Score Cible |
|---------|--------------|-------------|
| Sécurité | 2/10 | 9/10 |
| Maintenabilité | 3/10 | 8/10 |
| Testabilité | 1/10 | 8/10 |
| Performance | 4/10 | 8/10 |
| Documentation | 3/10 | 7/10 |
| **Global** | **2.6/10** | **8/10** |

---

## 🎯 Conclusion

Les deux SIS présentent des problèmes structurels importants qui empêchent leur mise en production:

1. **Bloquants**: Migrations absentes, tests non fonctionnels, failles de sécurité
2. **Majeurs**: Duplication de code, serializers vides, ViewSets incomplets
3. **Mineurs**: Logging non structuré, pas de métriques, typing absent

**Recommandation:** Traiter en priorité les problèmes de sécurité et générer les migrations avant tout développement supplémentaire.
