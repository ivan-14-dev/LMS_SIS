# Module `integration` — Communication SIS ↔ Open edX

Ce module permet à chaque SIS de communiquer **bidirectionnellement** avec le **LMS** (cours, inscriptions, notes, certificats) et le **CMS Studio** (création/modification de cours, XBlocks, assets).

## Architecture

```
┌─────────────────┐         ┌──────────────────────┐
│   SIS Django    │ ◄──────►│  Open edX LMS + CMS  │
│                 │         │                      │
│  EdxClient      │ ───────►│  /api/user/v1/...    │
│  (HTTP/JSON)    │ ───────►│  /api/courses/v1/... │
│                 │ ───────►│  /api/enrollment/v1  │
│  WebhookHandler │ ◄────── │  /api/grades/v1/...  │
│  (HMAC)         │ ◄────── │  /api/webhooks/v1/...│
│                 │         │                      │
│  Outbox pattern │         │  OAuth2 (JWT)        │
└─────────────────┘         └──────────────────────┘
```

## Composants

| Fichier | Rôle |
|---------|------|
| `edx_client.py` | Client HTTP REST vers LMS + CMS (OAuth2, timeouts, retry) |
| `webhook_handlers.py` | Handlers des webhooks entrants (LMS + CMS) avec router |
| `sync_service.py` | Orchestration bidirectionnelle (SIS → LMS, LMS → SIS) |
| `tasks.py` | Tâches Celery pour les jobs async |
| `models.py` | Tables de mapping (users, courses, enrollments, grades, outbox) |
| `api.py` | Endpoints REST : webhooks, sync, status, health |

## Flux

### SIS → LMS (Outbox + Outbox publisher)

1. Le code métier appelle `SyncService.sync_user_to_lms(...)`.
2. La fonction essaie immédiatement d'appeler le LMS.
3. En cas d'échec, un `OutboxEvent` est créé.
4. Une tâche Celery Beat `publish_outbox_events` réessaie toutes les minutes.

### LMS → SIS (Webhooks HMAC)

1. LMS envoie un POST sur `/api/v1/integration/webhook/lms/`.
2. Vérification HMAC `X-Signature: sha256=...`.
3. Routage vers la tâche Celery appropriée.
4. Handler met à jour la DB (mapping, enrollment, etc.).

### CMS → SIS (Webhooks XBlock)

1. Studio envoie un webhook sur `/api/v1/integration/webhook/cms/`.
2. Vérification HMAC.
3. Tâche `process_xblock_published` ou `process_course_published`.
4. Notification ou mise à jour des mappings.

## Endpoints API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/v1/integration/webhook/lms/` | POST | Réception webhooks LMS (HMAC) |
| `/api/v1/integration/webhook/cms/` | POST | Réception webhooks CMS (HMAC) |
| `/api/v1/integration/sync/status/` | GET | État de la file outbox + compteurs |
| `/api/v1/integration/sync/user/<id>/` | POST | Force sync d'un utilisateur vers LMS |
| `/api/v1/integration/sync/course/` | POST | Crée un cours dans Studio CMS |
| `/api/v1/integration/sync/enroll/` | POST | Inscrit un utilisateur à un cours LMS |
| `/api/v1/integration/sync/grade/` | POST | Pousse une note vers LMS (override) |
| `/api/v1/integration/sync/certificate/` | POST | Délivre un certificat LMS |
| `/api/v1/integration/health/` | GET | Santé LMS + CMS |

## Configuration

Variables d'environnement :

```bash
EDX_LMS_URL=http://localhost:8000
EDX_CMS_URL=http://localhost:8001
EDX_OAUTH_CLIENT_ID=sis-secondaire
EDX_OAUTH_CLIENT_SECRET=xxx
EDX_JWT_ISSUER=https://lms.example.com/oauth2
EDX_JWT_AUDIENCE=lms-key
EDX_JWT_PUBLIC_SIGNING_JWK_SET='{"keys":[...]}'
WEBHOOK_SECRET=xxx
```

## Sécurité

- **OAuth2** (client_credentials) entre SIS et LMS.
- **JWT RS512** pour les utilisateurs Open edX pré-mappés, avec validation de
  la signature, de l'émetteur, de l'audience et de l'expiration.
- Les clés asymétriques Open edX doivent être activées et le JWKS public du LMS
  doit être fourni au SIS.
- Les cookies JWT Open edX doivent être partagés avec le domaine du SIS. Les
  requêtes MFE sont acceptées uniquement avec `USE-JWT-COOKIE: true` et les
  écritures restent protégées par CSRF.
- **HMAC SHA-256** sur tous les webhooks (header `X-Signature`).
- **CSRF exempt** sur les webhooks (signés HMAC).
- **Rate limiting** via DRF.
- **Audit** via `django-auditlog` sur les modèles de mapping.

## Modèles

| Modèle | Rôle |
|--------|------|
| `EdxUserMapping` | User SIS ↔ User LMS |
| `EdxCourseMapping` | Matiere+Classe (Secondaire) / ECUE (Supérieur) ↔ Course LMS |
| `EdxEnrollment` | Inscription Eleve/Etudiant ↔ Course LMS |
| `EdxGradeLog` | Log des notes LMS importées |
| `OutboxEvent` | File d'attente pour sync différée |

## Tâches Celery

| Tâche | Schedule | Rôle |
|-------|----------|------|
| `publish_outbox_events` | 60s | Publie les événements en attente |
| `reconcile_lms` | 02:00 quotidien | Réconciliation bidirectionnelle |
| `sync_all_pending_eleves` | 03:00 quotidien | Sync initiale des utilisateurs |
| `process_user_webhook` | async | Traite webhook user LMS |
| `process_enrollment_webhook` | async | Traite webhook enrollment |
| `process_grade_webhook` | async | Traite webhook note LMS |
| `process_xblock_published` | async | Traite webhook CMS XBlock |
| `process_course_published` | async | Traite webhook CMS cours publié |
