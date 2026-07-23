# SIS Secondaire & SIS Supérieur

Deux applications Django distinctes intégrées au LMS Open edX.

> **📚 Documentation complète** : [docs/ROADMAP_OPERATIONNEL.md](docs/ROADMAP_OPERATIONNEL.md)

## Modes de déploiement

| Mode | Variable | Description |
|------|----------|-------------|
| **SIS Secondaire seul** | `SIS_MODE=secondaire` | Lycées, collèges |
| **SIS Supérieur seul** | `SIS_MODE=superieur` | Universités, grandes écoles |
| **Dual SIS** | `SIS_MODE=dual` | Les deux SIS avec passerelle de transfert |

Un établissement peut choisir d'utiliser **un seul SIS** ou **les deux** selon son profil.

## Démarrage rapide

```bash
# 1. Copier et configurer l'environnement
cp .env.template .env
# Éditer .env avec vos valeurs

# 2. Utiliser le Makefile pour simplifier les commandes
make install          # Installer les dépendances
make migrations       # Générer les migrations
make migrate          # Appliquer les migrations

# 3. Lancer selon le mode choisi
make run-secondaire   # Port 8000
make run-superieur    # Port 8001
make run-dual         # Les deux
```

Voir `make help` pour toutes les commandes disponibles.

## Structure

```
openedx-platform/sis_apps/
├── sis_secondaire/    # SIS pour Lycées / Collèges (profil Secondaire)
│   ├── manage.py
│   ├── config/        # settings, urls, wsgi, celery
│   ├── apps/          # 27 modules métier
│   ├── requirements/  # dépendances Python
│   ├── static/        # assets statiques
│   ├── templates/     # templates Django
│   └── media/         # uploads
└── sis_superieur/     # SIS pour Universités (profil Enseignement Supérieur)
    ├── manage.py
    ├── config/
    ├── apps/          # 31 modules métier
    ├── requirements/
    ├── static/
    ├── templates/
    └── media/
```

## Modules — SIS Secondaire (27 apps)

- `core` : noyau, middleware, logging JSON, multi-tenant
- `etablissement` : Etablissement (TenantMixin), AnneeScolaire, Periode, Niveau
- `utilisateurs` : Utilisateur (AbstractUser), RBAC
- `classes` : Classe, Groupe, Matiere, ProgrammeMatiere, Chapitre
- `eleves` : Eleve, Inscription, Tuteur, EleveTuteur
- `enseignants` : Personnel, MatiereEnseignee, AffectationEnseignant
- `salles` : Salle (classique, labo, info, gymnase, etc.)
- `emplois_du_temps` : Creneau, Contrainte
- `presences` : Appel, Presence, Justificatif
- `evaluations` : Evaluation (interro, DS, oral, etc.)
- `notes` : Note, Bulletin
- `bulletins` : AppreciationMatiere
- `examens` : SessionExamen, EpreuveExamen, Convocation, Resultat
- `conseil_classe` : ConseilClasse, DecisionConseil, Appreciation
- `discipline` : Incident, Sanction, ConseilDiscipline
- `paiements` : TypeFrais, Facture, Paiement
- `cantine` : Menu, InscriptionCantine, PresenceCantine
- `transport` : Ligne, Arret, Vehicule, InscriptionTransport
- `internat` : Batiment, Chambre, Occupant, EtudeSurveillee
- `bibliotheque` : Livre, Exemplaire, Emprunt, Reservation
- `infirmerie` : DossierMedical, Visite, StockMedicament
- `clubs` : Club, MembreClub, SeanceClub
- `stages` : Entreprise, ConventionStage, Suivi, Evaluation, Rapport
- `portail_parent`, `portail_enseignant`, `portail_eleve`
- `integration` : EdxUserMapping, EdxCourseMapping, EdxEnrollment, EdxGradeLog, OutboxEvent

## Modules — SIS Supérieur (31 apps)

- `core`, `etablissement` (Universite), `utilisateurs`
- `structure` : Faculte, Departement, EcoleDoctorale
- `formations` : Formation (L/M/D), Parcours, MaquetteFormation
- `ue_ecue` : UE, ECUE, Prerequis, Capitalisation
- `etudiants` : Etudiant, InscriptionAdministrative, InscriptionPedagogique, AcquisitionECTS
- `inscriptions` : APIs d'inscription
- `ects` : BilanECTS
- `mobilite` : ProgrammeMobilite, CandidatureMobilite, AccordEtudes, UEAccordEtudes
- `emplois_du_temps` : EDT
- `notes` : Evaluation, Note, MoyenneECUE, MoyenneUE
- `examens` : SessionExamen, EpreuveExamen, ConvocationExamen
- `rattrapages` : InscriptionRattrapage
- `jurys` : Jury, Deliberation, DecisionJury, DecisionGlobale
- `releves` : ReleveNotes, Transcript, Attestation
- `diplomes` : Diplome, CessionDiplome
- `memoires` : SujetMemoire, Memoire, JuryMemoire, SoutenanceMemoire
- `stages` : Offre, Candidature, Convention, Suivi, Evaluation, Rapport
- `bourses` : Bourse, VersementBourse
- `paiements` : TypeFraisInscription, Facture, Paiement
- `recherche` : Laboratoire, ProjetRecherche, ProductionScientifique, These
- `bibliotheque` : Livre, Exemplaire, Emprunt, Reservation, SalleTravail
- `entreprises` : Entreprise, ContactEntreprise
- `enseignants` : EnseignantChercheur, AffectationEnseignement
- `portail_etudiant`, `portail_enseignant`, `portail_doyen`, `portail_scolarite`
- `integration` : mapping LMS + outbox

## Stack technique

- **Django 5.0** + **DRF 3.15**
- **PostgreSQL 16** multi-tenant (`django-tenants` schema-per-tenant)
- **Redis** cache + Celery broker
- **Celery 5.4** + Celery Beat (réconciliation LMS, jobs quotidiens)
- **JWT** auth, **OAuth2**, **MFA** (TOTP)
- **drf-spectacular** OpenAPI 3.1
- **django-auditlog** traçabilité
- **django-guardian** permissions objet
- **Argon2id** mots de passe
- **Celery** tâches async + Webhooks HMAC pour LMS

## Intégration Open edX

Chaque SIS expose un module `integration` avec :

- `OutboxEvent` : pattern outbox (Kafka-ready).
- `EdxUserMapping` : user SIS ↔ user LMS.
- `EdxCourseMapping` : matière/UE ↔ cours LMS.
- `EdxEnrollment` : inscriptions synchronisées.
- `EdxGradeLog` : notes LMS importées.
- Webhooks entrants (HMAC) : `user`, `enrollment`, `grade`, `certificate`.
- Webhook sortant `sync_status` : monitoring de la file.
- Tâche `reconcile_lms` (Celery Beat quotidien) : réconciliation bidirectionnelle.

## Installation (développement)

```bash
cd /home/ivan/lms/openedx-platform/sis_apps/sis_secondaire
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/base.txt
# configurer .env (DB, Redis, secrets)
python manage.py migrate_schemas --shared
python manage.py create_tenant  # crée le 1er établissement
python manage.py runserver 0.0.0.0:8001
```

```bash
cd /home/ivan/lms/openedx-platform/sis_apps/sis_superieur
# idem sur le port 8002
```

## API

- Swagger : `/api/docs/`
- Schema OpenAPI : `/api/schema/`
- Auth : Bearer JWT ou session
- Rate limit : 100 req/min/user
- Multi-tenant automatique via sous-domaine

## Conformité

- **RGPD** : DPO, registre, droit à l'oubli, export.
- **Multi-locale** : fr, en, ar, es.
- **Audit log** immuable de toutes les actions sensibles.
- **MFA obligatoire** pour admin/comptable/finance.
- **TLS 1.3**, headers HSTS, CSP, X-Frame-Options.
- **Webhooks signés HMAC** entre LMS et SIS.

## Lancement des tests

```bash
python manage.py test apps.notes
pytest apps/notes/tests/
```

## Roadmap

- v1.0 (MVP) : modules métier essentiels, multi-tenant, auth JWT, intégration LMS basique.
- v1.1 : mobilité, rattrapages, mémoires, stages, bourses.
- v1.2 : recherche, équipement, IoT (cantine), transport GPS.
- v2.0 : microservices, IA (détection fraude, recommandation).
