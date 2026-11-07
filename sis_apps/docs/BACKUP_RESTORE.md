# Sauvegarde et restauration (Postgres, SIS Secondaire / SIS Supérieur)

> **Distribution Compose actuelle :** utilisez `scripts/sis_backup.py` et
> [le guide établissement](INSTALLATION_ETABLISSEMENT.md#exploitation-et-restauration).
> Il sauvegarde ensemble bases, médias, stockages privés, Redis et configuration,
> dans un dépôt chiffré, et refuse d'écraser une installation existante.
> Les scripts shell ci-dessous restent des outils historiques partiels :
> leur combinaison ne garantit pas un snapshot cohérent de l'application.

Les deux variantes SIS utilisent `django-tenants` : chaque établissement vit
dans son propre schéma Postgres, au sein d'une **même base de données** par
variante (`sis_secondaire`, `sis_superieur` en production). Une sauvegarde
`pg_dump` de la base entière couvre donc automatiquement le schéma `public`
(métadonnées globales, table des tenants/domaines) et tous les schémas
tenants en une seule opération — il n'y a pas besoin de sauvegarder chaque
établissement séparément.

Les scripts se trouvent dans `sis_apps/scripts/` et sont partagés entre les
deux variantes : ils opèrent uniquement via les variables d'environnement
`DB_*` déjà utilisées par `config/settings.py`, il suffit de les exporter avec
les valeurs de la variante concernée avant de les invoquer.

## Prérequis

- Le client `pg_dump`/`pg_restore` doit être installé et de version
  compatible avec le serveur Postgres cible (idéalement identique).
- Les variables d'environnement suivantes doivent être définies (mêmes noms
  que dans `config/settings.py`) :
  - `DB_NAME`, `DB_USER`, `DB_PASSWORD` (obligatoires)
  - `DB_HOST` (défaut `localhost`), `DB_PORT` (défaut `5432`)

## Sauvegarde

```bash
cd sis_apps
export DB_NAME=sis_secondaire DB_USER=... DB_PASSWORD=... DB_HOST=... DB_PORT=...
./scripts/backup.sh /chemin/vers/repertoire_de_sauvegardes
```

Le script :

1. exécute `pg_dump --format=custom` (format compressé, portable, permettant
   une restauration sélective par table/schéma si nécessaire) ;
2. horodate le fichier produit (`<DB_NAME>_<horodatage_UTC>.dump`) ;
3. vérifie l'intégrité de l'archive générée via `pg_restore --list`.

**Planification** : ce script doit être exécuté par une tâche planifiée
(cron, CronJob Kubernetes, etc.) à une fréquence conforme à la politique de
rétention de l'établissement, avec les archives copiées vers un stockage
distinct de la base primaire (objet de stockage externe, autre zone de
disponibilité). Chiffrer les archives au repos et restreindre leur accès, au
même titre que les autres volumes sensibles documentés dans
`DEPLOIEMENT_INTEGRATIONS.md`.

## Restauration

```bash
cd sis_apps
export DB_NAME=sis_secondaire DB_USER=... DB_PASSWORD=... DB_HOST=... DB_PORT=...
./scripts/restore.sh /chemin/vers/sauvegarde.dump
```

Le script demande une confirmation interactive avant de restaurer (car
`pg_restore` est appelé avec `--clean --if-exists`, qui supprime les objets
existants de la base cible avant de les recréer). Passer `--force` en second
argument permet d'automatiser la restauration dans un contexte non
interactif (ex. reconstruction d'un environnement de recette).

**Ne jamais restaurer directement sur la base de production** sans avoir
d'abord validé l'archive dans un environnement de recette isolé.

## Sauvegarde et restauration des fichiers médias

`scripts/backup.sh`/`scripts/restore.sh` ne couvrent que la base Postgres.
Les fichiers médias (`MEDIA_ROOT`, ex. copies d'examens scannées, documents
officiels générés, exports, pièces jointes) ne sont pas stockés en base et
doivent être sauvegardés séparément avec `scripts/backup_media.sh` /
`scripts/restore_media.sh`.

django-tenants ne segmente pas `MEDIA_ROOT` par schéma tenant : les fichiers
de tous les établissements d'une même variante (secondaire ou supérieur)
partagent le même répertoire média. Une archive de ce répertoire couvre donc
tous les tenants de la variante en une seule opération, tout comme
`backup.sh` le fait pour la base.

```bash
cd sis_apps
export MEDIA_ROOT=/chemin/vers/media  # valeur de config/settings.py:MEDIA_ROOT
./scripts/backup_media.sh /chemin/vers/repertoire_de_sauvegardes
```

Le script :

1. archive `MEDIA_ROOT` au format `tar.gz` ;
2. horodate l'archive produite (`<variante>_media_<horodatage_UTC>.tar.gz`) ;
3. vérifie l'intégrité de l'archive générée via `tar --test`.

Restauration :

```bash
cd sis_apps
export MEDIA_ROOT=/chemin/vers/media
./scripts/restore_media.sh /chemin/vers/sauvegarde_media.tar.gz
```

Comme pour `restore.sh`, une confirmation interactive est demandée avant
extraction (les fichiers de même nom sont écrasés) ; `--force` permet
d'automatiser la restauration dans un contexte non interactif.

**Planification et cohérence** : pour une reprise après sinistre cohérente,
sauvegarder la base et les médias au même horodatage (ou dans la même
fenêtre de maintenance), avec la même exigence de stockage distinct et de
chiffrement au repos que pour les sauvegardes Postgres.

## Test périodique de restauration

Une sauvegarde non testée n'offre aucune garantie. Il est recommandé de
valider régulièrement (au minimum trimestriellement) le cycle complet :

1. produire une sauvegarde avec `scripts/backup.sh` ;
2. la restaurer avec `scripts/restore.sh --force` dans une base Postgres
   jetable dédiée aux tests (jamais dans la base de production ni dans une
   base partagée) ;
3. produire une sauvegarde média avec `scripts/backup_media.sh` et la
   restaurer avec `scripts/restore_media.sh --force` dans un `MEDIA_ROOT`
   jetable ;
4. démarrer l'application contre cette base et ce répertoire média restaurés
   et vérifier qu'un établissement de test est bien accessible (`/health/`,
   `/ready/`, une requête authentifiée sur une API métier, et le
   téléchargement d'un fichier média existant).

## Limites actuelles

- Aucune orchestration (planification, rotation des archives, envoi vers un
  stockage distant) n'est fournie ici : ces scripts sont le socle à intégrer
  dans l'outillage d'exploitation (cron, CI/CD, opérateur Kubernetes) propre à
  chaque environnement de déploiement.

## Qualification ciblée des projets entre établissements

`sis_common/tests/test_project_tenant_isolation.py` crée deux schémas PostgreSQL
réellement migrés et peuplés, avec des identifiants utilisateurs entiers
volontairement identiques, des gestionnaires, évaluateurs et apprenants nonstaff.
Il contrôle les Hosts, les candidats, les commandes, les fichiers privés, le
rejeu de session et la désactivation locale du module. Son nettoyage cible
uniquement ses deux schémas à nom unique et leurs propres lignes de registre ;
il ne lance aucun `flush` et ne réutilise pas `fast_test`.

Dans l'environnement de tests PostgreSQL configuré de **chaque** variante :

```bash
# Depuis sis_apps/sis_secondaire, puis sis_apps/sis_superieur :
python manage.py test sis_common.tests.test_project_tenant_isolation --noinput
```

Cette régression ne prouve pas une restauration. Pour la qualifier séparément,
figer les écritures, comparer par SHA les tables brutes de tous les schémas
(comptes, droits, MFA comprise), sauvegarder puis restaurer la base entière
**et** `PRIVATE_EXAM_STORAGE_ROOT` dans une base et un volume indépendants.
La comparaison MFA doit inclure un compte synthétique sans droit métier,
réellement enrôlé par `sis_common.mfa.begin_enrollment` puis
`confirm_enrollment` avec un TOTP valide. Conserver la clé de chiffrement
synthétique nécessaire à sa lecture, sans l'inclure dans les reçus.

Comparer les empreintes **avant** les vérifications HTTP : les connexions
modifient légitimement les données de session et les téléchargements privés
ajoutent de vrais événements d'audit. Après ces contrôles positifs, relever une
nouvelle référence pour vérifier que les demandes refusées ne changent ni
projets, ni versions, ni historique. Les tests de code seuls, ou une recréation
avec les mêmes volumes, ne constituent pas une preuve de restauration et ne
changent pas le statut de recette.
