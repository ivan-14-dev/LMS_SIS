# Roadmap Opérationnelle - SIS Secondaire & SIS Supérieur

> **Objectif** : Rendre les deux SIS pleinement opérationnels et permettre aux établissements de choisir d'utiliser l'un, l'autre, ou les deux systèmes.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Prérequis techniques](#2-prérequis-techniques)
3. [Phase 1 : Fondations (Critique)](#3-phase-1--fondations-critique)
4. [Phase 2 : Intégration LMS/CMS](#4-phase-2--intégration-lmscms)
5. [Phase 3 : Tests et Qualité](#5-phase-3--tests-et-qualité)
6. [Phase 4 : Multi-SIS et Configuration](#6-phase-4--multi-sis-et-configuration)
7. [Phase 5 : Production](#7-phase-5--production)
8. [Annexes](#8-annexes)

---

## 1. Vue d'ensemble

### Architecture cible

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Open edX Platform                                │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────┐  │
│  │     LMS     │    │     CMS     │    │      SIS Layer              │  │
│  │  (Courses)  │◄──►│  (Studio)   │◄──►│  ┌─────────┐ ┌───────────┐  │  │
│  │             │    │             │    │  │   SIS   │ │    SIS    │  │  │
│  │  Étudiants  │    │  Contenus   │    │  │Secondaire│ │ Supérieur │  │  │
│  │  Progrès    │    │  Cours      │    │  │(Lycées) │ │(Universités)│ │  │
│  │  Notes      │    │  XBlocks    │    │  └────┬────┘ └─────┬─────┘  │  │
│  └──────┬──────┘    └──────┬──────┘    │       │            │        │  │
│         │                  │           │       └─────┬──────┘        │  │
│         │                  │           │             │               │  │
│         └────────┬─────────┘           │    ┌────────▼────────┐      │  │
│                  │                     │    │ Module          │      │  │
│                  │                     │    │ Integration     │      │  │
│                  └─────────────────────┼───►│ (Sync Service)  │      │  │
│                                        │    └─────────────────┘      │  │
│                                        └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             ┌──────────┐    ┌──────────┐    ┌──────────┐
             │PostgreSQL│    │  Redis   │    │  Celery  │
             │(Tenants) │    │ (Cache)  │    │ (Tasks)  │
             └──────────┘    └──────────┘    └──────────┘
```

### Modes de déploiement supportés

| Mode | Description | Cas d'usage |
|------|-------------|-------------|
| **SIS Secondaire seul** | Lycées, collèges | Établissements enseignement secondaire |
| **SIS Supérieur seul** | Universités, grandes écoles | Enseignement supérieur |
| **Dual SIS** | Les deux SIS + passerelle | Cités scolaires, campus mixtes |

---

## 2. Prérequis techniques

### Infrastructure minimale

```yaml
# docker-compose.yml (exemple)
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: openedx
      POSTGRES_USER: openedx
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    
  # Base de données séparée pour SIS Secondaire
  db_sis_secondaire:
    image: postgres:16
    environment:
      POSTGRES_DB: sis_secondaire
      POSTGRES_USER: sis
      POSTGRES_PASSWORD: ${SIS_DB_PASSWORD}

  # Base de données séparée pour SIS Supérieur  
  db_sis_superieur:
    image: postgres:16
    environment:
      POSTGRES_DB: sis_superieur
      POSTGRES_USER: sis
      POSTGRES_PASSWORD: ${SIS_DB_PASSWORD}
```

### Variables d'environnement requises

```bash
# .env.template - À copier en .env et compléter

# === SÉCURITÉ (OBLIGATOIRE) ===
DJANGO_SECRET_KEY=          # Générer avec: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DB_PASSWORD=                # Mot de passe PostgreSQL fort
SIS_DB_PASSWORD=            # Mot de passe SIS fort

# === BASE DE DONNÉES ===
DB_HOST=localhost
DB_PORT=5432
DB_NAME_SECONDAIRE=sis_secondaire
DB_NAME_SUPERIEUR=sis_superieur
DB_USER=sis

# === REDIS ===
REDIS_URL=redis://127.0.0.1:6379/1

# === OPEN EDX INTEGRATION ===
EDX_LMS_URL=http://localhost:18000
EDX_CMS_URL=http://localhost:18010
EDX_OAUTH_CLIENT_ID=sis-integration
EDX_OAUTH_CLIENT_SECRET=              # Obtenir depuis Admin LMS

# === PRODUCTION ===
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=sis.example.com,*.sis.example.com
CORS_ALLOWED_ORIGINS=https://lms.example.com,https://studio.example.com

# === MODE SIS (choisir) ===
SIS_MODE=dual   # Options: secondaire, superieur, dual
```

---

## 3. Phase 1 : Fondations (Critique)

### 3.1 Génération des migrations

**Statut actuel** : ❌ Aucune migration générée (dossiers vides)

**Actions requises** :

```bash
# === SIS Secondaire ===
cd /home/ivan/lms/openedx-platform/sis_apps/sis_secondaire

# Générer les migrations pour chaque app (dans l'ordre des dépendances)
python manage.py makemigrations core
python manage.py makemigrations etablissement
python manage.py makemigrations utilisateurs
python manage.py makemigrations classes
python manage.py makemigrations enseignants
python manage.py makemigrations eleves
python manage.py makemigrations salles
python manage.py makemigrations emplois_du_temps
python manage.py makemigrations presences
python manage.py makemigrations evaluations
python manage.py makemigrations notes
python manage.py makemigrations bulletins
python manage.py makemigrations examens
python manage.py makemigrations conseil_classe
python manage.py makemigrations discipline
python manage.py makemigrations paiements
python manage.py makemigrations cantine
python manage.py makemigrations transport
python manage.py makemigrations internat
python manage.py makemigrations bibliotheque
python manage.py makemigrations infirmerie
python manage.py makemigrations clubs
python manage.py makemigrations stages
python manage.py makemigrations portail_parent
python manage.py makemigrations portail_enseignant
python manage.py makemigrations portail_eleve
python manage.py makemigrations integration

# Appliquer les migrations
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant

# === SIS Supérieur ===
cd /home/ivan/lms/openedx-platform/sis_apps/sis_superieur

# Même processus pour les 31 apps
python manage.py makemigrations core
python manage.py makemigrations etablissement
python manage.py makemigrations utilisateurs
python manage.py makemigrations structure
python manage.py makemigrations formations
python manage.py makemigrations ue_ecue
python manage.py makemigrations etudiants
python manage.py makemigrations inscriptions
python manage.py makemigrations ects
python manage.py makemigrations mobilite
python manage.py makemigrations emplois_du_temps
python manage.py makemigrations notes
python manage.py makemigrations examens
python manage.py makemigrations rattrapages
python manage.py makemigrations jurys
python manage.py makemigrations releves
python manage.py makemigrations diplomes
python manage.py makemigrations memoires
python manage.py makemigrations stages
python manage.py makemigrations bourses
python manage.py makemigrations paiements
python manage.py makemigrations recherche
python manage.py makemigrations bibliotheque
python manage.py makemigrations entreprises
python manage.py makemigrations enseignants
python manage.py makemigrations maquettes
python manage.py makemigrations portail_etudiant
python manage.py makemigrations portail_enseignant
python manage.py makemigrations portail_doyen
python manage.py makemigrations portail_scolarite
python manage.py makemigrations integration

python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant
```

### 3.2 Création du super utilisateur

```bash
# Pour chaque SIS
python manage.py createsuperuser --username admin --email admin@example.com
```

### 3.3 Configuration du premier tenant

```python
# Script: scripts/create_initial_tenant.py
from apps.etablissement.models import Etablissement, Domain

# Créer l'établissement (tenant public/shared)
tenant = Etablissement.objects.create(
    schema_name='public',
    nom='Administration centrale',
    code='ADMIN',
    # ... autres champs
)

# Créer le domaine
Domain.objects.create(
    domain='admin.sis.local',
    tenant=tenant,
    is_primary=True,
)
```

---

## 4. Phase 2 : Intégration LMS/CMS

### 4.1 Configuration OAuth2 dans Open edX

**Dans le LMS Admin** (`/admin/oauth2_provider/application/`) :

```
Name: SIS Integration
Client type: Confidential
Authorization grant type: Client credentials
Client ID: sis-integration
Client Secret: [généré automatiquement - à copier dans .env]
```

### 4.2 Webhooks LMS → SIS

Configurer les webhooks Open edX pour notifier le SIS :

| Événement LMS | Endpoint SIS | Description |
|---------------|--------------|-------------|
| `user.created` | `/api/v1/webhooks/user/` | Nouveau utilisateur |
| `enrollment.created` | `/api/v1/webhooks/enrollment/` | Inscription cours |
| `grade.updated` | `/api/v1/webhooks/grade/` | Note mise à jour |
| `certificate.issued` | `/api/v1/webhooks/certificate/` | Certificat délivré |
| `xblock.published` | `/api/v1/webhooks/xblock/` | Contenu publié (CMS) |

**Configuration dans `lms.yml`** :

```yaml
WEBHOOK_SUBSCRIPTIONS:
  - url: "https://sis.example.com/api/v1/webhooks/user/"
    events: ["user.created", "user.updated"]
    secret: "${WEBHOOK_SECRET}"
  - url: "https://sis.example.com/api/v1/webhooks/enrollment/"
    events: ["enrollment.created", "enrollment.deleted"]
    secret: "${WEBHOOK_SECRET}"
  - url: "https://sis.example.com/api/v1/webhooks/grade/"
    events: ["grade.updated"]
    secret: "${WEBHOOK_SECRET}"
```

### 4.3 Améliorer le EdxClient

**Fichier à modifier** : `apps/integration/edx_client.py`

```python
# Ajouts recommandés :

class EdxClient:
    # ... code existant ...

    def health_check(self) -> dict:
        """Vérifie la connectivité LMS et CMS."""
        status = {"lms": False, "cms": False}
        try:
            r = requests.get(f"{self.lms_url}/heartbeat", timeout=5)
            status["lms"] = r.status_code == 200
        except Exception:
            pass
        try:
            r = requests.get(f"{self.cms_url}/heartbeat", timeout=5)
            status["cms"] = r.status_code == 200
        except Exception:
            pass
        return status

    def get_user_progress(self, course_key: str, username: str) -> dict:
        """Récupère la progression complète d'un utilisateur."""
        url = f"{self.lms_url}/api/courses/v1/courses/{course_key}/progress/{username}/"
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_course_structure(self, course_key: str) -> dict:
        """Récupère la structure complète d'un cours (sections, subsections)."""
        url = f"{self.cms_url}/api/courses/v1/courses/{course_key}/structure/"
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()
```

### 4.4 Tâches Celery manquantes

**Fichier** : `apps/integration/tasks.py` - Ajouter :

```python
@shared_task(bind=True, max_retries=3)
def sync_student_to_lms(self, etudiant_id: int):
    """Synchronise un étudiant vers le LMS."""
    from apps.etudiants.models import Etudiant
    try:
        etudiant = Etudiant.objects.get(pk=etudiant_id)
        service = SyncService()
        service.sync_user_to_lms(etudiant.user, role="student")
    except Exception as exc:
        self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=3)
def sync_course_to_cms(self, ecue_id: int):
    """Crée un cours dans le CMS pour une ECUE."""
    from apps.ue_ecue.models import ECUE
    try:
        ecue = ECUE.objects.select_related('ue').get(pk=ecue_id)
        service = SyncService()
        service.sync_course_to_cms(
            ecue,
            ecue.ue.formation.annee_universitaire,
            display_name=f"{ecue.code} - {ecue.intitule}"
        )
    except Exception as exc:
        self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task
def health_check_edx():
    """Vérifie périodiquement la connexion LMS/CMS."""
    from .edx_client import get_edx_client
    client = get_edx_client()
    status = client.health_check()
    if not all(status.values()):
        logger.error(f"EdX health check failed: {status}")
    return status
```

---

## 5. Phase 3 : Tests et Qualité

### 5.1 Structure de tests recommandée

**Statut actuel** : ❌ Tous les fichiers `tests.py` sont vides

**Structure cible** :

```
apps/
├── integration/
│   └── tests/
│       ├── __init__.py
│       ├── test_models.py        # Tests unitaires modèles
│       ├── test_sync_service.py  # Tests service de sync
│       ├── test_edx_client.py    # Tests client (mocked)
│       ├── test_webhooks.py      # Tests handlers webhooks
│       ├── test_tasks.py         # Tests tâches Celery
│       └── test_api.py           # Tests endpoints API
├── etudiants/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       └── factories.py          # Factories pour tests
```

### 5.2 Exemple de tests à implémenter

**Fichier** : `apps/integration/tests/test_models.py`

```python
"""Tests des modèles d'intégration."""
import pytest
from django.test import TestCase
from apps.integration.models import EdxUserMapping, EdxCourseMapping, OutboxEvent
from apps.utilisateurs.models import Utilisateur


class EdxUserMappingTestCase(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            username='test_user',
            email='test@example.com',
            password='testpass123',
            role='etudiant'
        )

    def test_create_mapping(self):
        mapping = EdxUserMapping.objects.create(
            user_sis=self.user,
            username_edx='edx-test-user'
        )
        self.assertEqual(str(mapping), 'test_user ↔ edx-test-user')
        self.assertTrue(mapping.actif)

    def test_unique_username_edx(self):
        EdxUserMapping.objects.create(user_sis=self.user, username_edx='unique-user')
        with self.assertRaises(Exception):
            # Créer un autre user pour tester l'unicité
            user2 = Utilisateur.objects.create_user(username='test2', email='t2@e.com', password='p')
            EdxUserMapping.objects.create(user_sis=user2, username_edx='unique-user')


class OutboxEventTestCase(TestCase):
    def test_create_event(self):
        event = OutboxEvent.objects.create(
            event_type='user.sync',
            aggregate_type='user',
            aggregate_id='123',
            payload={'action': 'create'}
        )
        self.assertEqual(event.statut, 'pending')
        self.assertEqual(event.nb_tentatives, 0)

    def test_dead_letter_after_retries(self):
        event = OutboxEvent.objects.create(
            event_type='user.sync',
            aggregate_type='user',
            aggregate_id='123',
            payload={},
            nb_tentatives=5,
            statut='failed'
        )
        # Simuler le passage en dead letter
        if event.nb_tentatives >= 5:
            event.statut = 'dead'
            event.save()
        self.assertEqual(event.statut, 'dead')
```

**Fichier** : `apps/integration/tests/test_sync_service.py`

```python
"""Tests du service de synchronisation."""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.integration.sync_service import SyncService
from apps.integration.models import EdxUserMapping


class SyncServiceTestCase(TestCase):
    @patch('apps.integration.sync_service.get_edx_client')
    def test_sync_user_to_lms_creates_mapping(self, mock_client):
        mock_client.return_value.create_user.return_value = {'id': 12345}
        
        user = Utilisateur.objects.create_user(
            username='sync_test', email='sync@test.com', password='pass'
        )
        
        service = SyncService()
        mapping = service.sync_user_to_lms(user, role='student')
        
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.user_id_edx, 12345)
        mock_client.return_value.create_user.assert_called_once()

    @patch('apps.integration.sync_service.get_edx_client')
    def test_sync_user_failure_creates_outbox_event(self, mock_client):
        mock_client.return_value.create_user.side_effect = Exception('API Error')
        
        user = Utilisateur.objects.create_user(
            username='fail_test', email='fail@test.com', password='pass'
        )
        
        service = SyncService()
        with self.assertRaises(Exception):
            service.sync_user_to_lms(user)
        
        # Vérifier qu'un événement outbox a été créé
        from apps.integration.models import OutboxEvent
        self.assertTrue(OutboxEvent.objects.filter(
            event_type='user.sync',
            aggregate_id=str(user.id)
        ).exists())
```

### 5.3 Factories pour les tests

**Fichier** : `apps/etudiants/tests/factories.py`

```python
"""Factories pour générer des données de test."""
import factory
from factory.django import DjangoModelFactory
from apps.utilisateurs.models import Utilisateur
from apps.etudiants.models import Etudiant, InscriptionAdministrative
from apps.etablissement.models import Universite, AnneeUniversitaire


class UniversiteFactory(DjangoModelFactory):
    class Meta:
        model = Universite
    
    schema_name = factory.Sequence(lambda n: f'univ_{n}')
    nom = factory.Faker('company', locale='fr_FR')
    code = factory.Sequence(lambda n: f'UNIV{n:03d}')


class UtilisateurFactory(DjangoModelFactory):
    class Meta:
        model = Utilisateur
    
    username = factory.Sequence(lambda n: f'user_{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    first_name = factory.Faker('first_name', locale='fr_FR')
    last_name = factory.Faker('last_name', locale='fr_FR')
    role = 'etudiant'


class EtudiantFactory(DjangoModelFactory):
    class Meta:
        model = Etudiant
    
    universite = factory.SubFactory(UniversiteFactory)
    user = factory.SubFactory(UtilisateurFactory)
    matricule = factory.Sequence(lambda n: f'ETU{n:06d}')
    date_naissance = factory.Faker('date_of_birth', minimum_age=18, maximum_age=30)
    lieu_naissance = factory.Faker('city', locale='fr_FR')
    sexe = factory.Iterator(['M', 'F'])
    adresse = factory.Faker('address', locale='fr_FR')
    code_postal = factory.Faker('postcode', locale='fr_FR')
    ville = factory.Faker('city', locale='fr_FR')
    telephone = factory.Faker('phone_number', locale='fr_FR')
```

### 5.4 Configuration pytest

**Fichier** : `pytest.ini` (à créer à la racine de chaque SIS)

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
addopts = -v --tb=short --strict-markers
markers =
    slow: marks tests as slow
    integration: marks tests requiring external services
```

---

## 6. Phase 4 : Multi-SIS et Configuration

### 6.1 Module de configuration centrale

Pour permettre à un établissement d'utiliser un ou deux SIS, créer un module de configuration :

**Fichier** : `sis_apps/sis_config/models.py`

```python
"""Configuration centrale pour le choix du/des SIS."""
from django.db import models


class SISConfiguration(models.Model):
    """Configuration globale du déploiement SIS."""
    
    MODE_CHOICES = [
        ('secondaire', 'SIS Secondaire uniquement'),
        ('superieur', 'SIS Supérieur uniquement'),
        ('dual', 'SIS Secondaire + Supérieur'),
    ]
    
    etablissement_nom = models.CharField(max_length=300)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    
    # URLs des services
    url_sis_secondaire = models.URLField(blank=True)
    url_sis_superieur = models.URLField(blank=True)
    
    # Partage de données entre SIS
    partage_utilisateurs = models.BooleanField(
        default=True,
        help_text="Partager les utilisateurs entre les deux SIS"
    )
    partage_etablissements = models.BooleanField(
        default=False,
        help_text="Un établissement peut avoir des sections secondaire et supérieur"
    )
    
    # Intégration LMS
    lms_url = models.URLField()
    cms_url = models.URLField()
    oauth_client_id = models.CharField(max_length=100)
    
    class Meta:
        verbose_name = "Configuration SIS"


class PasserelleSIS(models.Model):
    """Passerelle pour le transfert d'étudiants entre SIS."""
    
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('approuve', 'Approuvé'),
        ('refuse', 'Refusé'),
        ('complete', 'Complété'),
    ]
    
    # Élève côté secondaire
    eleve_secondaire_id = models.PositiveBigIntegerField()
    etablissement_secondaire = models.CharField(max_length=100)
    
    # Étudiant côté supérieur (après transfert)
    etudiant_superieur_id = models.PositiveBigIntegerField(null=True, blank=True)
    etablissement_superieur = models.CharField(max_length=100, blank=True)
    
    # Workflow
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_demande = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    motif_refus = models.TextField(blank=True)
    
    # Données transférées
    dossier_scolaire = models.JSONField(default=dict)
    notes_bac = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = "Passerelle SIS"
        verbose_name_plural = "Passerelles SIS"
```

### 6.2 API de passerelle entre SIS

**Fichier** : `sis_apps/sis_config/api.py`

```python
"""API pour la communication inter-SIS."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response


class PasserelleViewSet(viewsets.ModelViewSet):
    """API pour les transferts secondaire → supérieur."""
    
    @action(detail=False, methods=['post'])
    def initier_transfert(self, request):
        """Initie un transfert d'élève vers le supérieur."""
        eleve_id = request.data.get('eleve_id')
        etablissement_cible = request.data.get('etablissement_superieur')
        
        # Récupérer le dossier de l'élève depuis SIS Secondaire
        dossier = self._get_dossier_eleve(eleve_id)
        
        # Créer la demande de passerelle
        passerelle = PasserelleSIS.objects.create(
            eleve_secondaire_id=eleve_id,
            etablissement_secondaire=request.data.get('etablissement_origine'),
            etablissement_superieur=etablissement_cible,
            dossier_scolaire=dossier,
        )
        
        return Response({'passerelle_id': passerelle.id}, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def approuver_transfert(self, request, pk=None):
        """Approuve et exécute le transfert vers SIS Supérieur."""
        passerelle = self.get_object()
        
        # Créer l'étudiant dans SIS Supérieur
        etudiant_data = self._transformer_eleve_en_etudiant(passerelle.dossier_scolaire)
        # ... logique de création
        
        passerelle.statut = 'complete'
        passerelle.save()
        
        return Response({'status': 'transfert_complete'})
```

### 6.3 Script de démarrage conditionnel

**Fichier** : `sis_apps/start_sis.sh`

```bash
#!/bin/bash
# Script de démarrage conditionnel des SIS

SIS_MODE=${SIS_MODE:-dual}

echo "=== Démarrage SIS en mode: $SIS_MODE ==="

case $SIS_MODE in
    "secondaire")
        echo "Démarrage SIS Secondaire uniquement..."
        cd /app/sis_secondaire
        gunicorn config.wsgi:application --bind 0.0.0.0:8000 &
        celery -A config worker -l info &
        celery -A config beat -l info &
        ;;
    "superieur")
        echo "Démarrage SIS Supérieur uniquement..."
        cd /app/sis_superieur
        gunicorn config.wsgi:application --bind 0.0.0.0:8000 &
        celery -A config worker -l info &
        celery -A config beat -l info &
        ;;
    "dual")
        echo "Démarrage des deux SIS..."
        # SIS Secondaire sur port 8000
        cd /app/sis_secondaire
        gunicorn config.wsgi:application --bind 0.0.0.0:8000 &
        celery -A config worker -l info -Q secondaire &
        
        # SIS Supérieur sur port 8001
        cd /app/sis_superieur
        gunicorn config.wsgi:application --bind 0.0.0.0:8001 &
        celery -A config worker -l info -Q superieur &
        
        # Celery Beat partagé
        celery -A config beat -l info &
        ;;
    *)
        echo "Mode SIS inconnu: $SIS_MODE"
        exit 1
        ;;
esac

wait
```

---

## 7. Phase 5 : Production

### 7.1 Checklist pré-production

#### Sécurité

- [ ] `SECRET_KEY` unique et sécurisée (via variable d'environnement)
- [ ] `DEBUG = False`
- [ ] `ALLOWED_HOSTS` configuré avec les vrais domaines
- [ ] HTTPS activé (`SECURE_SSL_REDIRECT = True`)
- [ ] Cookies sécurisés (`SESSION_COOKIE_SECURE = True`)
- [ ] CORS limité aux domaines autorisés
- [ ] Rate limiting activé (DRF throttling)
- [ ] MFA activé pour les admins

#### Base de données

- [ ] Migrations appliquées
- [ ] Backups automatisés configurés
- [ ] Connection pooling (PgBouncer recommandé)
- [ ] Indices vérifiés sur les champs fréquemment requêtés

#### Performance

- [ ] Redis configuré pour le cache
- [ ] Celery workers dimensionnés
- [ ] Static files servis par WhiteNoise ou CDN
- [ ] Gzip activé

#### Monitoring

- [ ] Logging configuré vers un service centralisé
- [ ] Health checks endpoints actifs
- [ ] Alertes configurées (erreurs, latence)

### 7.2 Configuration Nginx

```nginx
# /etc/nginx/sites-available/sis.conf

upstream sis_secondaire {
    server 127.0.0.1:8000;
}

upstream sis_superieur {
    server 127.0.0.1:8001;
}

server {
    listen 443 ssl http2;
    server_name sis-secondaire.example.com;
    
    ssl_certificate /etc/letsencrypt/live/sis-secondaire.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sis-secondaire.example.com/privkey.pem;
    
    location / {
        proxy_pass http://sis_secondaire;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static/ {
        alias /app/sis_secondaire/staticfiles/;
        expires 30d;
    }
    
    location /media/ {
        alias /app/sis_secondaire/media/;
    }
}

server {
    listen 443 ssl http2;
    server_name sis-superieur.example.com;
    
    ssl_certificate /etc/letsencrypt/live/sis-superieur.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sis-superieur.example.com/privkey.pem;
    
    location / {
        proxy_pass http://sis_superieur;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static/ {
        alias /app/sis_superieur/staticfiles/;
        expires 30d;
    }
    
    location /media/ {
        alias /app/sis_superieur/media/;
    }
}
```

### 7.3 Dockerfile

```dockerfile
# Dockerfile pour SIS
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copier les requirements
COPY requirements/base.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code
COPY . .

# Collecter les fichiers statiques
RUN python manage.py collectstatic --noinput

# Utilisateur non-root
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

---

## 8. Annexes

### A. Ordre de priorité des tâches

| Priorité | Tâche | Effort | Impact |
|----------|-------|--------|--------|
| 🔴 P0 | Générer les migrations | 2h | Bloquant |
| 🔴 P0 | Configurer .env production | 1h | Sécurité |
| 🟠 P1 | Implémenter tests unitaires | 1 semaine | Qualité |
| 🟠 P1 | Configurer OAuth2 LMS | 2h | Intégration |
| 🟡 P2 | Tests d'intégration | 3 jours | Fiabilité |
| 🟡 P2 | Module passerelle SIS | 3 jours | Fonctionnel |
| 🟢 P3 | Documentation API (OpenAPI) | 2 jours | Maintenance |
| 🟢 P3 | Monitoring et alertes | 1 jour | Opérations |

### B. Commandes utiles

```bash
# Vérifier l'état des migrations
python manage.py showmigrations

# Créer un tenant de test
python manage.py create_tenant --schema_name=test --name="Test School"

# Lancer les tests
pytest --cov=apps --cov-report=html

# Vérifier les imports cycliques
python -c "import apps.integration"

# Générer le schéma OpenAPI
python manage.py spectacular --file schema.yaml

# Health check LMS/CMS
python manage.py shell -c "from apps.integration.edx_client import get_edx_client; print(get_edx_client().health_check())"
```

### C. Contacts et ressources

- **Documentation Open edX** : https://docs.openedx.org
- **API Open edX** : https://docs.openedx.org/en/latest/developers/references/rest_apis.html
- **Django Tenants** : https://django-tenants.readthedocs.io

---

## Changelog

| Version | Date | Auteur | Modifications |
|---------|------|--------|---------------|
| 1.0 | 2026-07-22 | — | Version initiale |

