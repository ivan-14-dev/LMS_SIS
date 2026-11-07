# SIS Secondaire & SIS Supérieur

Deux applications Django distinctes intégrées au LMS Open edX.

> **Installation établissement :**
> [guide Compose, configuration et exploitation](docs/INSTALLATION_ETABLISSEMENT.md).
> Le pack installe les SIS, pas le LMS Open edX.
>
> **📚 Documentation complète** : [docs/ROADMAP_OPERATIONNEL.md](docs/ROADMAP_OPERATIONNEL.md)
>
> **✅ TODO produit priorisée** :
> [docs/TODO_PRODUIT.md](docs/TODO_PRODUIT.md)

## Modes de déploiement

| Mode | Variable | Description |
|------|----------|-------------|
| **SIS Secondaire seul** | `SIS_MODE=secondaire` | Lycées, collèges |
| **SIS Supérieur seul** | `SIS_MODE=superieur` | Universités, grandes écoles |
| **Dual SIS** | `SIS_MODE=dual` | Les deux SIS, avec bases et comptes distincts |

Un établissement peut choisir d'utiliser **un seul SIS** ou **les deux** selon son profil.

## Installation recommandée

Suivez le [guide établissement](docs/INSTALLATION_ETABLISSEMENT.md).
`scripts/sisctl.py configure`, `init`, puis `start` fournissent le parcours
conteneurisé. Les migrations sont déjà versionnées : **ne les générez pas
pendant une installation**.

## Développement sans conteneurs

Ces commandes supposent Python 3.12, un environnement virtuel et des services
PostgreSQL/Redis déjà disponibles. Le serveur Django de développement ne doit
pas être exposé en production.

```bash
# 1. Copier et configurer l'environnement
cp .env.template .env
# Éditer .env avec vos valeurs

# 2. Utiliser le Makefile pour simplifier les commandes
make install          # Installer les dépendances
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

Pour un Tutor local installé dans un autre projet Compose, les API et workers
peuvent rejoindre son réseau Docker en déclarant dans le `.env` privé :

```dotenv
SIS_LMS_NETWORK=nom-du-projet-tutor_default
SIS_LMS_NETWORK_EXTERNAL=true
```

Le réseau externe doit déjà exister. Sans cette option, le réseau `lms` reste
isolé dans le projet SIS ; PostgreSQL, Redis et la passerelle restent sur le
réseau `sis`. Les URL `EDX_LMS_URL` et `EDX_CMS_URL` doivent être accessibles
depuis les conteneurs et le navigateur, avec les ports réellement exposés.
Utiliser un service OAuth dédié sans privilèges globaux, jamais un compte
administrateur humain. Les paramètres sont conservés par les sauvegardes du
`.env` et réutilisés par les commandes ordinaires de `sisctl.py`.

Un heartbeat LMS/Studio réussi ne prouve ni la livraison des webhooks ni
l'activation des automatismes : la supervision les indique comme non vérifiés
tant qu'aucune vérification correspondante n'est disponible.

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

### Projets pédagogiques (API des deux SIS)

Le module optionnel `sis.projects` est **désactivé par défaut**. Son activation
utilise `/api/v1/etablissement/current/modules/` (prévisualisation POST,
application PATCH avec `revision`, `enabled: {"sis.projects": true}` et `reason`).
La désactivation ferme toutes les routes ci-dessous, fichiers et capacités compris,
sans effacer les données. Elle ne modifie aucune habilitation.

Base : `/api/v1/core/projets/`. Les identifiants projet/équipe/jalon/livrable/évaluation
sont des UUID ; les identifiants de comptes sont des entiers. Les collections GET
utilisent `{count,next,previous,results}`, `page` et `page_size` (maximum 100).
Les commandes refusent les champs inconnus, les relations imbriquées arbitraires,
PUT, PATCH et DELETE. Aucune suppression de preuve ni remplacement de fichier.

| Route relative | Méthode et corps |
| --- | --- |
| `/` | GET, filtres `q` (titre), `mode=individuel\|collectif` ; POST `{titre,description?,mode,responsable,evaluateurs?:[compteId]}` |
| `{projet}/` | GET |
| `capacites/` | GET → `{can_create,permissions}` |
| `candidats/` | GET `?type=membre\|responsable\|evaluateur&q=terme[&projet=uuid\|&responsable=compteId]` → `{results:[{id,nom}]}` (20 maximum, recherche de 2 à 100 caractères) |
| `{projet}/configurer/` | POST `{version,titre?,description?,responsable?,evaluateurs?:[compteId]}` ; mode non modifiable |
| `{projet}/jalons/` | GET ; POST `{version,titre,consignes?,ordre,echeance,bareme}` |
| `{projet}/equipes/` | GET ; POST `{version,nom,membres:[compteId]}` |
| `{projet}/equipes/{equipe}/membres/` | POST `{version,membres:[compteId]}` (remplacement atomique des membres actifs) |
| `{projet}/equipes/{equipe}/livrables/` | GET, filtre `jalon` ; POST **multipart** `version`, `jalon`, `fichier`, `commentaire?` |
| `{projet}/equipes/{equipe}/livrables/{livrable}/telecharger/` | GET authentifié, réponse PDF privée sans cache |
| `{projet}/equipes/{equipe}/evaluations/` | GET, filtre `jalon` ; POST `{version,jalon,note_groupe,commentaire,contributions?:[{membre,note,commentaire}]}` crée un brouillon |
| `{projet}/equipes/{equipe}/evaluations/{evaluation}/publier/` | POST `{version}` |
| `{projet}/historique/` | GET, historique administratif paginé avec `acteur`, `created_at`, `action`, `metadata` |

Chaque réponse projet comprend `version` et
`actions.{can_manage,can_submit,can_evaluate}`. Les équipes exposent ces mêmes
capacités, leur liste `membres` actifs (`membre`, `nom`, `ajoute_par`, `created_at`)
et leur `projet`. Les créations/configurations de projet renvoient le projet.
Les autres mutations renvoient `{version,jalon|equipe|livrable|evaluation}` :
mettre à jour la version locale après chaque réussite, ou recharger le projet
après un conflit. Les jalons comprennent `ordre` (unique dans le projet),
`echeance` (date/heure ISO 8601), `bareme` (décimal strictement positif, maximum
10000) et leurs auteur/date. Ils sont communs à toutes les équipes et immuables.
Une remise tardive reste possible et porte `en_retard: true`.

Habilitations enregistrées : `core.gerer_projet_pedagogique` permet de créer et
organiser dans le périmètre accordé ; `core.evaluer_projet_pedagogique` exige en
plus d'être le responsable ou un évaluateur explicitement désigné. Être responsable,
staff, super-admin de rôle hérité ou membre ne confère pas implicitement ces
permissions. Les comptes apprenants ne peuvent pas administrer ou s'auto-évaluer.
Le responsable délégué doit détenir la permission de gestion ; les évaluateurs
doivent détenir celle d'évaluation. Les scopes ABAC reconnus sont `etablissement_id`
(entiers), `projet_id` (UUID canoniques sous forme de chaînes) et `responsable_id`
(entiers). Un scope inconnu ferme l'accès ; une permission scoped n'est jamais
transformée en permission globale. La création est autorisée dans le contexte du
responsable demandé : un enseignant avec `responsable_id: [son_id]` peut créer
ses projets, sans obtenir de droit sur ceux de ses collègues. `can_create` indique
qu'au moins un responsable actif, tenant-local et habilité peut être choisi dans
ce périmètre. Un scope `projet_id` seul ne permet pas de créer un projet.

Le sélecteur requiert la gestion du projet donné, sans exiger
`utilisateurs.view_utilisateur`. Avant création, `type=responsable` renvoie les
responsables éligibles dans le scope du demandeur, sans autre paramètre nécessaire.
Pour `type=membre` ou `type=evaluateur`, transmettre `responsable=<compteId>` afin
de vérifier le contexte du futur projet (par défaut : compte connecté). Les
évaluateurs sont également filtrés sur ce responsable. Un responsable hors scope
est refusé, pas remplacé par le compte connecté. `projet` et `responsable` sont
mutuellement exclusifs : une fois le projet créé, utiliser uniquement `projet`.

Un apprenant peut appartenir à **une seule équipe active par projet**. Un projet
individuel peut avoir plusieurs équipes, chacune créée avec exactement une personne
et limitée ensuite à une personne active. Une équipe vidée par retrait conserve ses
preuves mais ne permet plus de dépôt ni de publication d'évaluation. Les appartenances
retirées restent historisées ; le retrait coupe immédiatement les nouvelles requêtes
d'accès. Un téléchargement déjà autorisé/en cours ne peut pas être rappelé.
Les apprenants ne voient que leurs propres projets/équipes/livrables, les évaluations
publiées de leur équipe, et uniquement leur propre contribution individuelle.
L'historique administratif est réservé aux gestionnaires/évaluateurs habilités.

Les livrables sont limités au PDF selon le validateur existant
(`EXAM_COPY_MAX_SIZE`, 25 Mio par défaut, extension/type MIME/signature PDF).
Cela ne constitue **pas** une analyse antivirus. Ils utilisent le stockage privé
existant `PRIVATE_EXAM_STORAGE_ROOT`, sous `projets/<tenant>/<projet>/<équipe>/` :
ce répertoire doit être persistant, sauvegardé et jamais exposé par le serveur web.
La réponse ne contient ni chemin de stockage ni URL media ; elle contient
`nom`, `taille`, `sha256`, `revision`, `depose_par`, `created_at`, `en_retard`.
Chaque nouvelle remise crée une révision et conserve les fichiers précédents.
Les contrôles de périmètre précèdent la lecture/validation du fichier.

Chaque évaluation a `statut=brouillon|publiee`, `revision`, `bareme`,
`evalue_par`, `created_at`, `publie_par`, `published_at`. Notes de groupe et
individuelles sont comprises entre zéro et le barème explicite du jalon.
Un brouillon peut être incomplet ; la publication humaine exige exactement tous
les membres actuels et la dernière révision. Pour corriger, créer un nouveau
brouillon ; les évaluations et contributions précédentes restent conservées.
Les modifications d'appartenance, publications et audit partagent une transaction
et un verrou de projet ; les versions périmées sont refusées.

Erreurs : **400** champs, bornes ou comptes incompatibles ; **403** habilitation
insuffisante/module désactivé ; **404** objet, équipe ou relation hors périmètre ;
**409** version de projet périmée. L'API ne rattache pas encore les projets aux
cours/classes/ECUE ni aux compétences. Ces évaluations pédagogiques ne sont
**jamais des notes officielles SIS** : aucun transfert automatique, validation
officielle ou synchronisation LMS n'est réalisé par ce module. Ces rattachements
restent à réaliser pour compléter l'exigence 10.5.

L'interface est disponible dans « Pédagogie → Projets pédagogiques »
(`/secondaire/projets` ou `/superieur/projets`) après activation du module.
Elle propose les commandes ci-dessus selon les capacités renvoyées par le serveur :
organisation aux gestionnaires, dépôt privé aux membres et publication explicite
aux évaluateurs habilités. Un conflit de version conserve les saisies et demande
un rechargement puis une nouvelle confirmation ; aucune commande n'est rejouée
automatiquement. L'historique administratif reste consultable par API.

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
