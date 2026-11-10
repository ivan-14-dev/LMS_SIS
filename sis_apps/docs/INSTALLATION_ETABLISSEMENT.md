# Installer le SIS d'un établissement

## Périmètre et limites

Cette distribution Compose installe les SIS, leur interface, PostgreSQL, Redis,
les workers, le planificateur et le proxy HTTPS. Elle **n'installe pas Open edX** :
le LMS et Studio sont facultatifs en authentification locale ; lorsqu'ils sont
retenus, ils doivent fonctionner et être administrés séparément.
La compatibilité d'une version Tutor avec ce fork doit être qualifiée avant
d'en faire une distribution complète LMS + SIS.
Le déploiement séparé décrit ci-dessous utilise Tutor 22.0.4 ; il ne remplace
ni les bases SIS ni leurs comptes et ne prouve pas à lui seul leur intégration.

Les variantes sont `secondaire`, `superieur` et `dual`. En mode dual, chaque SIS
possède sa base, ses fichiers et ses sessions. Un compte administrateur dans un
SIS ne donne pas automatiquement accès à l'autre.

Ne considérez pas une installation locale comme une homologation de production :
SMTP/SMS, SSO réel, règles pédagogiques, sauvegarde hors machine, capacité,
protection des données et recette par les utilisateurs restent à valider sur
l'infrastructure de l'établissement.

### Le SIS comme point d'entrée

Communiquez l'adresse du SIS aux utilisateurs. L'accueil et les menus sont
adaptés aux affiliations et permissions effectives, pas au seul nom du rôle :

| Profil | Accès depuis l'accueil |
|---|---|
| Apprenant | Dossier, résultats, documents, emploi du temps personnel et « Mes cours » vers le LMS si le compte est associé. |
| Enseignant | Activité pédagogique, classes et évaluations autorisées ; « Créer/modifier un cours » uniquement après confirmation d'un accès enseignant à un cours. |
| Administration | Dossiers, inscriptions, classes/affectations, évaluations et finances selon les permissions déjà attribuées. Aucun droit Studio global implicite. |
| Parent du secondaire | Dossiers des seuls enfants autorisés, documents et suivi familial ; aucun raccourci Studio ni accès à l'API personnelle LMS. |

`/<variante>/cours-lms` présente les cours de l'établissement dont la dernière
décision d'accès SIS a été confirmée par Open edX. Les accès retirés, demandes
encore en attente, cours désactivés et identités non confirmées sont exclus.
Ce n'est pas une interrogation en temps réel des droits natifs : les contrôles
Open edX restent souverains à l'ouverture du cours. Les liens ouvrent un nouvel
onglet pour garder le SIS accessible. Créer un nouveau cours ou publier reste
soumis aux droits natifs ; le bouton ne les attribue pas.

Les URL navigateur `LMS_BASE_URL` et `STUDIO_BASE_URL` doivent désigner les
origines publiques du LMS et de Studio lors de la construction du frontend,
pas leurs seuls noms de conteneurs. En mode `local`, la connexion Open edX
reste distincte et l'interface l'indique. En mode `lms`, le raccordement SSO
décrit ci-dessous réutilise la connexion native. Aucun compte n'est associé
automatiquement par similarité de nom ou d'email.

`/<variante>/mon-emploi-du-temps` est une consultation personnelle, sans droits
de modification du planning. Au secondaire, elle suit la classe actuelle ;
au supérieur, les inscriptions validées, choix pédagogiques et affectations
individuelles, avec leurs groupes TD/TP. Les créneaux sans groupe sont communs.
Les dates, semaines et fréquences restent affichées : ce n'est pas une promesse
que chaque créneau se déroule aujourd'hui. Le suivi parental reste dans les
dossiers d'enfants autorisés, pas dans cet endpoint apprenant.

Le logo institutionnel peut rester l'identité principale du SIS. Pour les
interfaces Open edX, conserver les mentions et attributions applicables :
la [politique de marque](https://openedx.org/trademark-licensing-details/)
recommande le badge « Powered by Open edX » en pied de page avec son lien.

## Type d'établissement et accès individuels

Dans **Administration → Établissement → Identité**, le catalogue commun permet
de choisir collège/lycée, université/grande école, formation professionnelle
ou établissement mixte. Un changement de type ajoute les modèles d'offres
manquants ; le type mixte prépare secondaire et supérieur. Les offres déjà
personnalisées, leurs rattachements, les inscriptions et les résultats restent
inchangés. Dans **Profils et offres**, adapter ces modèles puis les rattacher
aux classes/formations ; dans **Organisation et règles**, ouvrir
**Règles héritées** pour publier un défaut. Les modules déjà installés se
gèrent dans **Modules**.

Ce réglage ne transforme pas une classe en formation universitaire et
n'installe pas les modules spécifiques de l'autre moteur. Le mode `dual`
conserve deux bases, des comptes locaux séparés et deux contextes métier :
le regroupement de tous les modules dans un moteur unique nécessite encore
une migration dédiée. Le libellé « mixte » n'est pas une fusion de données.

Dans **Administration → Utilisateurs → Rôles et accès individuels**, choisir
un compte pour ajouter des permissions directes, refuser explicitement des
permissions héritées ou retirer un service personnel. Les refus priment sur
les octrois directs, groupes et rôles, y compris côté API. Retirer la lecture
des dossiers/résultats bloque aussi leur portail agrégé pour éviter un accès
par un autre écran. Retirer un service ne supprime pas ses dossiers.

Un super-utilisateur peut attribuer plusieurs rôles métier. Le titulaire
choisit **Mon rôle actif** dans l'en-tête ; seul un rôle effectivement attribué
est accepté par le serveur. Le changement vide le cache de l'espace précédent
et ne modifie pas le rôle principal. Les permissions explicites restent
attachées au compte. Le rôle ne crée ni dossier apprenant, ni profil enseignant,
ni relation parent-enfant. Les affectations et périmètres demeurent requis.
Un enseignant également apprenant ne peut pas gérer une évaluation à laquelle
il est inscrit, ni saisir, modifier ou supprimer sa propre note.

La gestion de ce formulaire exige les permissions globales
`utilisateurs.view_utilisateur`, `utilisateurs.change_utilisateur` et
`auth.change_group` ; l'interface exige aussi `auth.view_group` pour le
catalogue. Un gestionnaire ne peut déléguer une permission qu'il ne possède
pas sans restriction. L'attribution de rôles et le rétablissement des services
hérités requièrent un super-utilisateur. Les propres droits du gestionnaire
et les comptes super-utilisateurs sont protégés. Les modifications sont
journalisées et une édition concurrente est refusée par un conflit HTTP 409.

Les retraits LMS/Studio mettent en file les révocations des accès attribués
par le SIS ; la confirmation distante dépend des workers et du fournisseur.
Les raccourcis SIS sont retirés immédiatement. Les droits attribués directement
dans Open edX restent à gérer dans Open edX. Réactiver le service ne réaccorde
pas automatiquement les affectations retirées. Un parent sans rôle enseignant
actif et affectation confirmée ne reçoit aucun accès Studio.

## Préparer le serveur

- Linux avec Docker Engine, le plugin Docker Compose **≥ 2.20** et Python **≥ 3.11**.
- Git, accès aux registres d'images et aux dépôts de dépendances.
- Pour démarrer un pilote SIS : prévoir environ 4 vCPU, 8 Gio de RAM et 40 Gio de
  disque **hors documents, sauvegardes et Open edX**. Ce sont des réserves initiales,
  pas une capacité garantie ; mesurer avec les effectifs et usages attendus.
  Une mesure locale avec 61 apprenants par SIS a observé environ 994 Mio
  pour les 11 conteneurs dual au repos. Elle exclut Open edX, l'hôte et les pics
  de compilation ; elle ne constitue pas un test de charge.
- Trois noms DNS, par exemple `sis.ecole.example`, `secondaire.ecole.example`
  et `superieur.ecole.example`, pointant vers le serveur.
- Ports TCP 80 et 443 disponibles. PostgreSQL et Redis ne sont pas publiés.
  Si un proxy/Tutor utilise déjà ces ports, prévoir une machine distincte ou
  intégrer explicitement le routage dans le proxy existant.
- Pour le mode LMS uniquement : un client OAuth confidentiel SIS dans Open edX, son secret, l'audience, l'issuer
  exact et le **JWKS public** RSA/RS512. Ne copiez jamais la clé privée du LMS.

### Installation autonome, sans Open edX

Depuis la racine du dépôt :

```sh
cd sis_apps
python3 scripts/sisctl.py configure \
  --project-name sis-ecole \
  --mode secondaire \
  --auth-mode local \
  --domain ecole.example
python3 scripts/sisctl.py preflight --offline
python3 scripts/sisctl.py preflight --installation --ports
```

Aucun paramètre `EDX_*`, fichier JWKS ou secret OAuth n'est nécessaire ni
généré. Poursuivez avec la création de l'établissement (`init`) puis `start`
ci-dessous. `--mode dual` nécessite une initialisation par variante.
`--auth-mode local` choisit les comptes SIS : il **n'active pas DEBUG** et
conserve HTTPS en production. Pour un pilote uniquement sur la machine,
ajoutez `--local --domain ecole.localhost` ; HTTP reste lié à la boucle locale.

L'interface utilise son origine pour initialiser son socle technique lorsque
les URL LMS sont absentes ; cela ne configure aucun LMS côté serveur. Le
diagnostic d'intégration doit rester « non configuré », sans appel distant.
Les comptes, la scolarité et les paiements manuels ne requièrent pas Open edX.
Les fonctions externes restent indisponibles jusqu'à leur raccordement.

Une authentification locale peut aussi utiliser le provisioning LMS : fournir
`--lms-url` et `--cms-url` ensemble avec le client OAuth. Le JWKS n'est alors
nécessaire que si l'authentification JWT Open edX est retenue. Un paramétrage
partiel est refusé par le précontrôle ; les clés JWT présentes sont toujours
contrôlées, y compris en mode local.

### Installation avec authentification Open edX

Depuis la racine du dépôt :

```sh
cd sis_apps
python3 scripts/sisctl.py configure \
  --project-name sis-ecole \
  --mode secondaire \
  --domain ecole.example \
  --lms-url https://lms.ecole.example \
  --cms-url https://studio.ecole.example \
  --oauth-client-id sis-integration \
  --audience openedx \
  --jwks /chemin/protege/lms-public-jwks.json
```

L'issuer par défaut est `LMS_URL/oauth2` ; utilisez `--issuer` s'il diffère.
Les URL LMS et Studio doivent être des origines complètes sans chemin,
paramètre ni identifiant intégré, en HTTPS sauf avec `--local`.
Les clients SIS demandent explicitement `asymmetric_jwt=true` à Open edX :
son endpoint OAuth peut sinon retourner un jeton symétrique, qui ne peut pas
être vérifié avec le JWKS public. Ne partagez pas le secret de signature du
LMS pour contourner ce refus. Le SIS accepte uniquement le RS512 configuré,
l'issuer et l'audience attendus, et un jeton explicitement non restreint
(`is_restricted=false`) ; les restrictions LMS ne sont pas des droits SIS.

Un mapping actif vers un compte SIS actif reste obligatoire. Un compte ayant
activé le MFA local **ne peut pas se connecter avec le seul jeton LMS** :
il doit utiliser la connexion locale et son second facteur. La fédération
du MFA n'est pas encore implémentée. La recette API avec des jetons réellement
signés par Open edX couvre ces refus et les révocations locales, mais ne
constitue pas une qualification du SSO navigateur.

Le secret OAuth est demandé sans affichage. Les autres secrets sont générés
aléatoirement dans `.env`, avec des permissions `0600`. Une configuration
existante n'est jamais écrasée.
Le JWKS fourni doit contenir les paramètres publics RSA `n` et `e` ;
l'installateur refuse tout composant de clé privée avant de demander le secret
OAuth ou de créer `.env`.
Utilisez le secret généré par Open edX, sur une seule ligne, sans apostrophe
ni `$` initial ; l'installateur refuse ces formes plutôt que de produire une
valeur interprétée différemment par les lecteurs de `.env`.

Pour un test sur cette machine uniquement, ajoutez `--local`, utilisez un domaine
comme `ecole.localhost`, et des URL locales adaptées. Ce mode active DEBUG et HTTP
sur `127.0.0.1:8080` : **ne l'exposez pas à un réseau public**.

### Précontrôles sans démarrage

Depuis `sis_apps`, avant `init` :

```sh
python3 scripts/sisctl.py preflight --offline
python3 scripts/sisctl.py preflight --installation --ports
```

Le premier contrôle ne contacte ni Docker ni un réseau : permissions privées
du fichier, clés requises et format de la clé de chiffrement, JWKS public,
mode, domaines/URL/HTTPS, ports et confinement de DEBUG à une IP de boucle locale.
Les affectations `.env` dupliquées sont refusées. Il ne valide pas les signatures
réelles du LMS. Pour un fichier déplacé, ajouter `--env-file CHEMIN` **avant**
le nom de la sous-commande. Le second contrôle Docker, la version de Compose, sa configuration,
l'existence d'un réseau LMS déclaré externe et la disponibilité des ports TCP.
L'option `--ports` est destinée à une **installation neuve arrêtée** ; elle échoue
normalement si sa propre passerelle utilise déjà les ports.
Sans `--ports`, ce contrôle est aussi exécuté par `init`, `start` et `update`.
Aucun de ces précontrôles ne réserve un port, ne délivre de certificat ou ne
qualifie DNS, SMTP, OAuth et capacité du serveur. L'absence de backend SMTP
de production produit un avertissement, pas une livraison d'email fictive.
Les valeurs sont littérales : utiliser des apostrophes pour les valeurs contenant
espaces, `$` ou antislash, pas une interpolation `${VARIABLE}` ni des échappements
entre guillemets doubles. Les formes ambiguës sont refusées avec le numéro de
ligne, sans afficher la valeur. Un `#` non précédé d'espace reste dans la valeur.

Attribuer un `COMPOSE_PROJECT_NAME` distinct par installation **sur le même
hôte Docker**, y compris les restaurations. `configure --project-name` le conserve
dans `.env` ; pour les anciennes configurations sans cette clé, le nom reste
`lms-sis`. Les scripts privilégient ce fichier, pas les variables homonymes
exportées dans le shell : changer une image/un port exige de modifier le fichier.
Les profils sont déterminés par `SIS_MODE`, pas par `COMPOSE_PROFILES`.
Les commandes de maintenance partagent un verrou
`.<COMPOSE_PROJECT_NAME>.operations.lock` à côté du fichier `.env` ; conserver
le même répertoire privé, accessible en écriture au compte d'exploitation, pour
toutes les automatisations. Ce verrou ne couvre ni les commandes Docker manuelles
ni une autre machine/racine de configuration.

### Choisir la connexion

Par défaut, l'interface utilise l'authentification Open edX (`SIS_AUTH_MODE=lms`).
Ajoutez `--auth-mode local` lors de la configuration pour utiliser les comptes SIS
locaux avec session HTTP-only, CSRF et MFA. Ce choix n'active aucune donnée fictive
et ne désactive pas les permissions des API.

Le MFA SIS local ne protège pas une connexion fédérée : celle-ci doit être
protégée par le LMS ou son fournisseur d'identité. Les utilisateurs importés
reçoivent un mot de passe inutilisable ; ils doivent utiliser la récupération
par email ou être associés explicitement à une identité Open edX.

### Préparer le LMS séparé avec Tutor

Les comptes SIS disposent d'un UUID technique stable pour les intégrations.
Ne pas le recalculer lors d'un changement de nom, d'adresse ou de rôle. Les
anciens mappings LMS restent valides ; cette migration ne fusionne pas des
comptes existants et n'active pas le SSO. Un retour arrière applicatif peut
conserver la colonne et son défaut SQL ; ne pas annuler cette migration pour
revenir à l'image précédente, ce qui supprimerait les nouveaux identifiants.

Tutor et les versions qualifiées des plugins actifs Indigo/MFE sont épinglés
dans `deploy/tutor/requirements.txt`. Les autres plugins installés avec `full`
ne sont pas pour autant activés : forums, certificats avancés et services
complémentaires exigent leur propre configuration et recette.
[Tutor indique](https://docs.tutor.edly.io/gettingstarted/requirements.html)
au minimum 4 Go de RAM/2 CPU/8 Go de disque et recommande 8 Go/4 CPU/25 Go,
**en plus des besoins du SIS et des autres services de l'hôte**. Réserver aussi
les pics des migrations/imports et sauvegardes. Ne pas arrêter un service tiers
ou modifier son proxy pour libérer les ports.

Depuis `sis_apps`, utiliser un environnement Python et une racine Tutor distincts
du dépôt et du Compose SIS. Les fichiers générés contiennent des secrets :

```sh
umask 077
python3 -m venv /chemin/prive/deploiement-lms/venv
/chemin/prive/deploiement-lms/venv/bin/python -m pip install -r deploy/tutor/requirements.txt
export PATH="/chemin/prive/deploiement-lms/venv/bin:$PATH"
export TUTOR_ROOT=/chemin/prive/deploiement-lms/tutor
tutor config save \
  --set LOCAL_PROJECT_NAME=lms-etablissement \
  --set LMS_HOST=lms.ecole.example \
  --set CMS_HOST=studio.lms.ecole.example \
  --set MFE_HOST=apps.lms.ecole.example \
  --set PLATFORM_NAME='Plateforme de formation' \
  --set CONTACT_EMAIL=formation@ecole.example \
  --set LANGUAGE_CODE=fr \
  --set ENABLE_HTTPS=true
tutor local launch --non-interactive --pullimages
```

Ces commandes supposent DNS, ressources et ports validés pour le serveur LMS.
En présence d'un proxy, suivre la
[configuration officielle](https://docs.tutor.edly.io/sysadmin/proxy.html) :
`ENABLE_WEB_PROXY=false`, port HTTP interne dédié lié à `127.0.0.1` et routes
explicites pour LMS/Studio/MFE. Conserver `ENABLE_HTTPS=true` lorsque le proxy
termine TLS. Ne jamais afficher `config.yml` ou les fichiers Compose rendus
dans un ticket public.

Pour une **qualification locale isolée**, sans changement du proxy existant :

```sh
tutor config save \
  --set LOCAL_PROJECT_NAME=sis-lms-qualification \
  --set LMS_HOST=lms.sis.localhost \
  --set CMS_HOST=studio.lms.sis.localhost \
  --set MFE_HOST=apps.lms.sis.localhost \
  --set CONTACT_EMAIL=lms@example.test \
  --set ENABLE_HTTPS=false \
  --set ENABLE_WEB_PROXY=false \
  --set CADDY_HTTP_PORT=127.0.0.1:59080 \
  --set OPENEDX_LMS_UWSGI_WORKERS=1 \
  --set OPENEDX_CMS_UWSGI_WORKERS=1
install -m 600 deploy/tutor/qualification.override.yml \
  "$TUTOR_ROOT/env/local/docker-compose.override.yml"
install -m 600 deploy/tutor/qualification.jobs.override.yml \
  "$TUTOR_ROOT/env/local/docker-compose.jobs.override.yml"
tutor local dc config --quiet
tutor local dc pull
tutor local start --detach permissions mysql mongodb redis meilisearch smtp
tutor local do init
tutor local start --detach
```

Contrôler que le port 59080 est disponible avant ces commandes. Cette configuration
borne les ressources et limite les workers à un processus ; elle n'est pas un
dimensionnement de production. L'initialisation précède le démarrage des services
applicatifs pour ne pas cumuler leurs pics mémoire.

#### Accès local normal sur un port explicite

`CADDY_HTTP_PORT` ne modifie que le port publié, pas les URL générées par Tutor.
Pour ouvrir le LMS dans un navigateur ordinaire, sans `--host-resolver-rules`,
utiliser l'adaptateur **local uniquement**, désactivé par défaut :

```sh
python -m pip install ./deploy/openedx/tutor-sis-local-urls
tutor plugins enable sis_local_urls
tutor config save \
  --set SIS_LOCAL_URLS_ENABLED=true \
  --set SIS_LOCAL_URLS_PORT=59080 \
  --set ENABLE_HTTPS=false --set ENABLE_WEB_PROXY=false \
  --set CADDY_HTTP_PORT=127.0.0.1:59080 \
  --set LMS_HOST=lms.sis.localhost:59080 \
  --set CMS_HOST=studio.lms.sis.localhost:59080 \
  --set MFE_HOST=apps.lms.sis.localhost:59080 \
  --set JWT_COMMON_ISSUER=http://lms.sis.localhost:59080/oauth2
tutor local dc config --quiet
```

Sauvegarder d'abord la racine existante à froid et vérifier la lecture intégrale
du snapshot chiffré. L'adaptateur possède
`env/local/docker-compose.prod.override.yml` : ne pas écraser un fichier
opérateur préexistant à cet emplacement. Les limites de ressources restent dans
`docker-compose.override.yml`, inchangé. Conserver la wheel de l'adaptateur avec
la racine sauvegardée et la réinstaller avant toute régénération/restauration.
Il refuse HTTPS, les domaines autres que `localhost`/`*.localhost`, les ports
incohérents et toute publication autre que `127.0.0.1`. Il nécessite Compose
supportant `!override` et ne s'applique pas à `tutor dev`.

Caddy écoute aussi le port 59080 **dans son réseau Docker** ; ses alias DNS,
les domaines des cookies LMS/Studio et leurs `ALLOWED_HOSTS` restent sans port.
Le port public vient de `Host`, non du `X-Forwarded-Port` standard de Tutor.
Les MFE récupèrent leurs URL aux API de configuration runtime : aucune
reconstruction de leur image n'est nécessaire. L'image Open edX et les données
ne sont pas modifiées.

Sur une installation existante, changer **seulement** `redirect_uris` de
l'application OAuth `cms-sso` vers
`http://studio.lms.sis.localhost:59080/complete/edx-oauth2/`, par une opération
administrative ciblée sans journaliser les identifiants. Ne pas relancer
`launch`, l'initialisation complète, ni `create_dot_application` (cette commande
peut journaliser les secrets). Le callback de développement d'une future
initialisation est normalisé sans double port par le plugin. Recréer uniquement :

```sh
tutor local dc up -d --no-deps --force-recreate \
  caddy lms cms lms-worker cms-worker mfe smtp
curl --fail http://lms.sis.localhost:59080/heartbeat
curl --fail http://studio.lms.sis.localhost:59080/heartbeat
```

Ouvrir `http://lms.sis.localhost:59080/` et
`http://studio.lms.sis.localhost:59080/` directement ; les applications utilisent
`http://apps.lms.sis.localhost:59080/`. Vérifier connexion, cours, réponse/score
historique sans soumission, Studio et déconnexion. Les mots de passe, MFA,
permissions et clés de signature restent inchangés. Un SIS raccordé doit
recevoir les mêmes URL publiques et l'issuer exact
`http://lms.sis.localhost:59080/oauth2` ; les anciens JWT peuvent nécessiter une
nouvelle connexion. Ne pas modifier automatiquement les autres déploiements SIS.

La recette navigateur sans règle de résolution a relu le cours et son score 1/1,
ouvert Studio et vérifié la fermeture des sessions. Avec l'image native qualifiée,
le retour automatique après déconnexion apprenant peut rester sur « déconnecté » :
le lien de retour visible fonctionne et l'API refuse bien la session terminée.
L'adaptateur 0.1.1 corrige les deux anciens chemins de logos du pied de page
Indigo vers les PNG déjà présents sous `/static/indigo/images/` : images
identiques, sans reconstruction ni changement de marque. L'endpoint optionnel
d'onboarding de télésurveillance peut encore retourner 404 pour un cours non
surveillé ; ne pas activer cette fonction ni simuler son endpoint pour le masquer.

Après disponibilité réelle de LMS/Studio/MFE : créer des comptes de recette
séparés, publier un cours, l'inscrire à un apprenant, effectuer une activité,
puis contrôler le résultat après redémarrage. Les commandes `tutor local do
createuser --help` et `importdemocourse --help` décrivent les opérations supportées.
Ne pas transmettre un mot de passe personnel en argument ni importer des dossiers
utilisateur dans la démonstration.

La qualification locale du 4 novembre 2026 couvre un cours créé dans Studio,
un exercice à sélection unique enregistré et publié, une inscription apprenant
et une correction réelle à 1/1. Après arrêt et redémarrage des services, le
cours, l'inscription, la réponse et le score ont été relus sans nouvelle
soumission. Cet exercice est **non noté dans la moyenne du cours** : il ne
constitue ni un résultat académique officiel, ni une synchronisation vers le SIS.
La personnalisation complète du LMS reste à qualifier. Le pilote SSO navigateur
distinct est décrit ci-dessous.

Pour la sauvegarde du LMS, conserver une destination et une clé distinctes de
celles du SIS, hors de `TUTOR_ROOT`. Arrêter tous ses services avant de
sauvegarder l'ensemble de cette racine : configuration, environnements générés,
MySQL, MongoDB, fichiers et autres données persistantes. Le snapshot local de
qualification utilise Restic 0.18.1, un montage source en lecture seule et
`--network none` ; `check --read-data` a vérifié les données chiffrées avant le
redémarrage. La restauration vers une racine et un projet Tutor distincts a
également été vérifiée, LMS source arrêté : connexions, cours, inscription,
réponse et score conservés, sans nouvelle soumission. Cette recette a pris
environ 74 secondes sur 642 Mio de données et avec les images déjà disponibles ;
ce n'est pas un engagement de RTO en production.

Ces contrôles ne remplacent pas une copie hors machine ni un exercice
institutionnel. Conserver la clé séparément et reprendre la même version Tutor
et les mêmes images lors de la restauration. Régénérer les environnements avec
`TUTOR_ROOT` pointant sur la racine restaurée et vérifier les montages : ils ne
doivent pas référencer les données de la source. Ne jamais restaurer sur une
installation en service.

La création d'un compte via le connecteur SIS ne doit pas transformer un
administrateur institutionnel en administrateur global Open edX. Les privilèges
globaux LMS sont provisionnés séparément par l'exploitant ; les droits
pédagogiques sont à attribuer sur les cours concernés.

**Différence avec l'API native :** dans la distribution qualifiée,
`/api/user/v1/accounts` expose une lecture, pas une création par `POST`.
La modification d'un compte utilise `application/merge-patch+json` et ne permet
pas à un compte technique de modifier arbitrairement les autres comptes.
Les clients SIS utilisent désormais l'extension de provisioning décrite
ci-dessous, pas un faux `POST` sur cette API native. L'extension doit être
installée explicitement ; son absence produit une erreur, pas un compte fictif
ni un rattachement automatique par adresse email.

**Contrat d'inscription qualifié :** les deux clients SIS utilisent
`POST /api/enrollment/v1/enrollment` avec `user`, `course_details.course_id`,
`is_active` et, pour l'inscription, `mode`. La désinscription utilise le même
endpoint avec `is_active=false`, sans remplacer le mode existant.
`GET /api/enrollment/v1/enrollments?course_id=...` lit toutes les pages ;
un lien externe ou ne conservant pas le filtre est refusé. Les confirmations
incomplètes ou incohérentes provoquent une erreur, pas un succès local.
L'API native ne fournit pas d'identifiant numérique d'inscription à inventer.

Ce parcours a été exercé avec OAuth sur le LMS isolé, puis depuis l'API de
chaque SIS avec PostgreSQL jetable : refus apprenant, interruption réseau,
événement en attente, reprise réelle et appels répétés sans doublon.
La désinscription répétée et la réactivation ont également été vérifiées au
niveau des clients. Les résultats pédagogiques existants sont conservés.
Le traitement en lot s'arrête à la première erreur : il conserve les succès
précédents et met l'échec en attente, mais pas les éléments non encore tentés.

Cette recette exige des mappings explicites vers des comptes et cours
préexistants ; elle ne qualifie pas leur provisioning ni le SSO. Le listing
global et les inscriptions d'autrui nécessitent les autorisations Open edX
appropriées : la recette utilise un compte technique synthétique explicitement
privilégié, jamais une promotion automatique d'un compte SIS. Conserver les
identifiants OAuth dans un fichier privé hors dépôt ; la commande Open edX
de création d'application peut les écrire dans sa sortie. Ne pas publier
ces journaux ni utiliser ces secrets de recette en production.

### Provisionner les comptes SIS dans Open edX

Le paquet `deploy/openedx/sis-provisioning` fournit l'extension Django LMS
`openedx-sis-provisioning`. Elle est distincte du plugin Tutor de SSO navigateur.
Depuis `sis_apps`, construisez une image dédiée à partir de la distribution
qualifiée, puis sélectionnez-la dans **la bonne racine Tutor** :

```sh
docker build -t ecole-openedx:sis-provisioning-0.1.0 \
  -f deploy/openedx/Dockerfile ..
tutor config save --set DOCKER_IMAGE_OPENEDX=ecole-openedx:sis-provisioning-0.1.0
tutor local run --rm lms ./manage.py lms migrate sis_provisioning --noinput
tutor local start --detach lms lms-worker cms cms-worker
```

Sauvegardez le LMS avant cette opération. L'image de base par défaut est
`overhangio/openedx:22.0.4-indigo` ; un autre fork ou une autre version nécessite
une recette propre, pas seulement un changement de tag. Pour une installation
distante, publier l'image sur le registre privé autorisé de l'établissement ou
la transférer avec les outils Docker approuvés ; un tag local n'existe pas
automatiquement sur une autre machine.

Le contexte de construction est désormais la **racine du dépôt** (`..`
depuis `sis_apps`). Il fournit aussi le module natif `sis_grade_webhooks` et
la transmission du barème réel par `SubsectionGradeFactory`. Copier uniquement
le paquet de provisioning ne livre pas ces deux composants.

Le dossier `deploy/openedx` contient aussi le correctif de déconnexion
`jquery.allLoaded` pour cette version : chaque iframe attend un seul événement
`load`, sans appeler une méthode jQuery sur un élément DOM. La construction
applique le patch sans approximation puis régénère les assets LMS et Studio.
Conserver ce contexte complet, pas uniquement le paquet Python.

Utilisez un compte OAuth technique dédié, actif, sans mot de passe utilisable
et sans `is_staff`/`is_superuser`. Son application OAuth doit utiliser
`client-credentials`. Pour le seul provisioning des comptes, accordez la permission
`sis_provisioning.provision_accounts` à ce compte. Exemple pour un compte
**déjà créé et vérifié**, nommé `sis-service` :

```sh
tutor local run --rm lms ./manage.py lms shell -c \
  'from django.contrib.auth import get_user_model; from django.contrib.auth.models import Permission; u = get_user_model().objects.get(username="sis-service", is_active=True); assert not u.is_staff and not u.is_superuser and not u.has_usable_password(); u.user_permissions.add(Permission.objects.get(content_type__app_label="sis_provisioning", codename="provision_accounts"))'
```

Cette permission n'autorise pas automatiquement les inscriptions d'autrui ou
la gestion des cours dans les API natives. Qualifiez séparément les droits
nécessaires aux autres opérations du connecteur ; ne faites pas de chaque
utilisateur provisionné un administrateur global pour les obtenir.

Le contrat est `POST /api/sis/v1/accounts/{username}/` avec `email` et `name`.
Le nom LMS opaque dérivé de l'UUID SIS est conservé lors des reprises.
Un `POST` répété ne crée pas de doublon pour le même service propriétaire.
`PATCH` exige en plus l'identifiant numérique `id` déjà enregistré dans le SIS.
Les champs de mot de passe, de rôle global et d'activation sont refusés.
Le service ne peut modifier ni les comptes d'un autre service, ni un compte
désactivé ou devenu privilégié. Les clients vérifient identité, profil et
absence de privilèges dans la confirmation avant de marquer la synchronisation
comme réussie.

La création réutilise les validations natives du LMS et respecte sa politique
de création de comptes. Elle crée un compte actif avec un mot de passe
aléatoire inconnu de l'utilisateur et du SIS, jamais retourné ni conservé en
clair. L'utilisateur doit définir son mot de passe avec **Mot de passe oublié**
sur le LMS. Le SMTP du LMS doit donc être configuré et qualifié. Le lien natif
de récupération a été vérifié comme lié au bon compte ; ce contrôle ne vaut
pas preuve de livraison par votre fournisseur d'email. Le provisioning ne
simule ni acceptation des conditions d'utilisation ni activation par email.
Les changements de profil ne réinitialisent pas le mot de passe.

La présence d'un compte SIS ne déclenche plus de création massive nocturne
par défaut. Dans **Administration → Intégration LMS → Utilisateurs**,
**Associer un utilisateur** propose les comptes éligibles sans mapping :
sélectionnez la personne, examinez la cible et confirmez explicitement.
Une simple consultation ou annulation ne crée pas de compte LMS.
Les indicateurs « activation non vérifiée » ne sont pas des autorisations
de synchroniser automatiquement ; **Synchroniser tous** reste désactivé.
La reprise outbox des opérations déjà demandées continue de fonctionner.
Les anciennes tâches opérateur de synchronisation massive restent disponibles
pour les intégrations maîtrisées, mais ne sont plus planifiées par défaut.
Après une mise à jour, redémarrez Beat pour retirer ces anciennes entrées de
son stockage persistant ; cela n'annule pas les tâches déjà en file.

Un compte LMS préexistant n'est **jamais adopté par simple correspondance de
nom ou d'email**. Après contrôle manuel de son association dans le tenant SIS,
un opérateur autorisé peut le rattacher explicitement :

```sh
tutor local run --rm lms ./manage.py lms sis_bind_account \
  --manager sis-service --username ancien-compte --confirm
```

Cette commande ne renomme pas le compte et ne change pas son mot de passe.
Elle refuse les comptes privilégiés, désactivés ou appartenant déjà à un autre
service. Une association SIS révoquée doit être traitée explicitement :
la synchronisation ne la réactive plus et relit sous verrou l'état du compte.

**Qualification du 4 novembre 2026 :** les deux API SIS ont créé et modifié des
comptes dans le vrai LMS avec un service OAuth non-staff. Après une création
effective dont la réponse HTTP a été volontairement perdue, la reprise outbox
a retrouvé le même identifiant distant, même avec un profil SIS modifié entre
les tentatives. Les appels répétés ne créent pas de doublon ; un apprenant LMS
ordinaire est refusé. Les mots de passe et MFA SIS sont inchangés.

Conservez le contexte exact de l'image avec la sauvegarde de la racine Tutor,
en complément de la configuration et des bases :

```sh
mkdir -p "$TUTOR_ROOT/plugins-artifacts"
tar --exclude=__pycache__ --exclude=build --exclude='*.egg-info' \
  -czf "$TUTOR_ROOT/plugins-artifacts/sis-openedx-0.1.0-source.tar.gz" \
  -C deploy openedx
```

Lors d'une restauration, reconstruisez ou récupérez l'image correspondante
avant de démarrer le LMS. Ne restaurez pas les seuls registres dans un autre
LMS sans leurs comptes, index SQL et contenus MongoDB associés.

### Créer et raccorder les cours Studio

La même image installe une extension **CMS**, distincte des routes de comptes
du LMS. Les anciennes routes `/api/courses/v1/courses/` ne fournissent pas ce
provisioning dans la distribution qualifiée. Les deux SIS utilisent désormais
`POST`, `GET` et `PATCH /api/sis/v1/courses/{course_id}/` sur l'origine **Studio**.
Le seul champ modifiable est `display_name`. Une réponse doit confirmer
l'identifiant exact et le nom demandé ; une redirection, un refus ou un
identifiant différent ne produit pas de succès local.

Accordez au service dédié la permission `sis_provisioning.provision_courses`.
Il doit également satisfaire les règles natives de création dans
l'organisation concernée. Exemple pour les deux variantes :

```sh
tutor local run --rm cms ./manage.py cms shell -c \
  'from django.contrib.auth import get_user_model; from django.contrib.auth.models import Permission; from common.djangoapps.student.roles import OrgContentCreatorRole; u = get_user_model().objects.get(username="sis-service", is_active=True); assert not u.is_staff and not u.is_superuser and not u.has_usable_password(); u.user_permissions.add(Permission.objects.get(content_type__app_label="sis_provisioning", codename="provision_courses")); OrgContentCreatorRole(org="SIS").add_users(u); OrgContentCreatorRole(org="SIS-U").add_users(u)'
```

Ne conservez que les organisations nécessaires. Ces rôles ne ferment pas une
politique Studio autorisant déjà toute création : le contrôle natif des
créateurs (`ENABLE_CREATOR_GROUP`) doit être configuré et qualifié si une
restriction par organisation est requise.

Les UUID des matières/classes et ECUE rendent les nouveaux identifiants
indépendants des libellés, des codes locaux et de l'année civile du rejeu.
Les identifiants des associations historiques sont conservés. Un ECUE ne peut
être synchronisé pour une autre année que celle de son semestre. Une association
révoquée n'est pas réactivée et une ancienne demande outbox ne remplace pas une
synchronisation plus récente déjà réussie.

La création passe par les fonctions natives de Studio. Le service reçoit les
droits natifs sur **ce cours**, jamais `is_staff` ou `is_superuser` globaux.
Le cours est initialement vide, hors catalogue ; ce contrat n'écrit ni contenu
pédagogique ni date de publication. Les enseignants utilisent ensuite Studio
après attribution de leurs droits.

L'intention de propriété est conservée avant la création. Celle-ci écrit
dans MySQL **et** MongoDB : elle reste en autocommit, protégée par un verrou
nommé MySQL par association, pour ne pas annuler l'index SQL après une création
MongoDB effective. Une initialisation interrompue peut reprendre les étapes
natives manquantes. Ce mécanisme est qualifié sur le MySQL de la distribution,
pas sur un backend SQL alternatif. Un cours supprimé, remplacé ou appartenant
à un autre service n'est pas recréé ou adopté implicitement.

Pour un cours existant, vérifiez d'abord son association SIS et accordez
explicitement au service les droits d'auteur nécessaires dans l'équipe Studio.
Puis effectuez le rattachement opérateur :

```sh
tutor local run --rm cms ./manage.py cms sis_bind_course \
  --manager sis-service --course-id 'course-v1:SIS+EXISTANT+2026' --confirm
```

Cette commande exige les droits préexistants, ne les accorde pas elle-même,
ne transfère pas un cours détenu par un autre service et préserve contenu,
équipe et résultats. Elle est idempotente. Un rattachement manuel interrompu
se termine avec cette commande, pas par une création automatique.

**Qualification du 4 novembre 2026 :** chaque API SIS a créé un vrai cours,
perdu volontairement sa réponse, puis repris l'outbox après modification du
code local sans créer de doublon. Les modifications répétées et le refus d'un
apprenant LMS ont été exercés par HTTP/OAuth. Une interruption interne après
création MongoDB a également été reprise avec l'index SQL conservé. Le cours
historique de qualification a été rattaché explicitement, sans changement des
réponses, notes, contenus ou membres antérieurs de l'équipe.

L'attribution automatique des enseignants, les contenus/publications, les
inscriptions selon le cycle de vie et les suspensions/départs restent à
raccorder. Les méthodes de blocs, publication et autres opérations historiques
du client ne sont pas rendues compatibles par ce seul incrément.

**Limite d'inscription confirmée :** l'API native
`POST /api/enrollment/v1/enrollment` refuse l'inscription d'autrui par ce
service non-staff, même sur un cours qu'il possède et pour un compte qu'il
provisionne. Le refus HTTP 404 a été reproduit avec un JWT valide, alors que
la lecture du cours Studio réussit ; aucune inscription ni aucun rôle n'a
changé. Les premières recettes du contrat d'inscription utilisaient un autre
service privilégié : elles ne qualifient pas ce service à droits limités.
Ne lui attribuez ni privilège global ni clé API globale pour contourner ce
refus. Un contrat d'inscription explicitement borné reste à implémenter avant
d'activer cette chaîne complète en établissement.

### Raccorder le navigateur SIS au LMS

Le plugin local `deploy/tutor/tutor-sis-sso` ajoute les origines SIS explicitement
autorisées aux listes de redirection, CORS et CSRF du LMS. Il conserve les origines
natives et **ne modifie pas le domaine des cookies**. Il ne crée aucun compte,
mapping, inscription ou privilège. Sa liste `SIS_SSO_ORIGINS` est vide par défaut.
Depuis la version 0.2.0, il permet également de déclarer les callbacks de notes
signées ; `SIS_GRADE_WEBHOOK_TARGETS` est vide par défaut et se configure
séparément dans le fichier privé, jamais dans une commande contenant le secret.
Voir le [contrat des notes et les prérequis](DEPLOIEMENT_INTEGRATIONS.md#notes-détaillées-open-edx).

Depuis `sis_apps`, avec le venv Tutor et `TUTOR_ROOT` du LMS sélectionnés :

```sh
python -m pip install ./deploy/tutor/tutor-sis-sso
tutor plugins enable sis_sso
tutor config save --set 'SIS_SSO_ORIGINS=["https://sis.lms.ecole.example"]'
tutor local restart lms lms-worker
```

Utilisez des origines exactes, avec le port non standard le cas échéant, sans
chemin, paramètres, identifiants ni joker. HTTPS est obligatoire lorsque Tutor
active HTTPS. Le frontend doit pouvoir recevoir les cookies JWT natifs du LMS :
si `SESSION_COOKIE_DOMAIN=lms.ecole.example`, utilisez par exemple
`sis.lms.ecole.example`, pas un domaine frère arbitraire. Les API SIS doivent
également recevoir les cookies requis ou le JWT via `Authorization: JWT ...`. Ne pas
élargir le domaine des cookies à des sites qui ne sont pas sous votre contrôle.
Une autorisation CORS seule ne rend pas les cookies partageables.

Configurez le SIS avec `--auth-mode lms`, les URL publiques correctes, l'issuer,
l'audience et le JWKS public du LMS. Associez explicitement chaque utilisateur
au compte Open edX existant dans le bon tenant et affectez-lui son établissement
et son dossier métier. Le MFA local reste incompatible avec le seul jeton LMS :
conservez une voie de connexion locale pour les comptes concernés.
Reconstruisez le frontend après changement de mode ou d'URL. Utilisez des tags
d'image frontend **distincts pour chaque configuration** : les URL et le mode
d'authentification sont intégrés lors du build, pas injectés au démarrage Nginx.

Conservez aussi le paquet du plugin dans la sauvegarde du LMS, sans y inclure
le venv système :

```sh
mkdir -p "$TUTOR_ROOT/plugins-artifacts"
python -m pip wheel --no-deps ./deploy/tutor/tutor-sis-sso \
  --wheel-dir "$TUTOR_ROOT/plugins-artifacts"
```

À la restauration, réinstallez cette wheel dans le venv Tutor compatible avant
de régénérer les environnements ; restaurer `config.yml` ne réinstalle pas les
plugins Python.

**Pilote local du 4 novembre 2026 :** un SIS secondaire séparé, avec base et
comptes synthétiques, utilise `http://sis.lms.sis.localhost:59082` et l'API
`http://secondaire.lms.sis.localhost:59082/api/v1`. Le plugin autorise uniquement
l'origine frontend du pilote. Le routage Chromium conserve les origines :

```sh
chromium \
  --user-data-dir=/chemin/prive/recette-sso-chromium \
  --host-resolver-rules='MAP sis.lms.sis.localhost 127.0.0.1:59082,MAP secondaire.lms.sis.localhost 127.0.0.1:59082,MAP *.sis.localhost 127.0.0.1:59080' \
  http://sis.lms.sis.localhost:59082/secondaire
```

La recette part du SIS, utilise le vrai formulaire LMS, charge le dossier élève
avec sa classe et ouvre le cours sans seconde connexion. Elle relit la réponse
et le score 1/1 sans nouvelle soumission, revient au SIS, puis vérifie la
déconnexion, la suppression des cookies JWT et l'exigence d'une nouvelle
connexion. Les appels SIS ne produisent plus de 500 : les portails élève,
parent et enseignant utilisent maintenant le libellé réel du niveau scolaire.
Les builds `npm run build` désactivent la télémétrie New Relic non configurée ;
les erreurs applicatives restent visibles dans l'interface.
La configuration et la wheel du plugin ont été incluses dans une sauvegarde
chiffrée du LMS vérifiée par lecture intégrale. Après redémarrage, le même
parcours et le score ont été relus. Cela ne remplace pas une nouvelle recette
de restauration incluant le plugin sur une machine distincte.

**Limites connues :** HTTP et routage local ne qualifient pas le DNS/TLS d'un
établissement. Le parcours navigateur supérieur, les autres rôles,
l'attribution des enseignants et la fédération MFA restent à qualifier. L'erreur
native de déconnexion `this.unbind is not a function` a été corrigée dans
l'image dérivée décrite ci-dessus. Après reconstruction et déploiement, le
parcours complet réussit sans exception JavaScript tolérée : redirection vers
le catalogue, cookies JWT effacés et nouvelle connexion obligatoire.
Les SIS utilisateur conservent leur
authentification locale : le pilote ne les bascule pas en SSO.

**Complément du 10 novembre :** la nouvelle recette distincte qualifie aussi
les quatre connexions apprenant/enseignant des deux variantes, les JWT RS512
natifs et le refus d'un mapping de l'autre variante. Deux problèmes réellement
notés produisent des callbacks HTTPS signés, des propositions idempotentes puis
des notes approuvées par l'interface avec CSRF. Les comptes sont synthétiques,
le navigateur reste en HTTP local et la CA des callbacks est propre à la
recette. Ces preuves ne lèvent pas les réserves institutionnelles ou de
fédération MFA ; voir le [bilan courant](RESTE_A_FAIRE_ET_VALIDATION.md).

### Configurer les emails et l'identité visuelle

Complétez `.env` avant de construire l'interface :

```dotenv
SITE_NAME='Mon établissement'
SUPPORT_EMAIL='assistance@ecole.example'
SUPPORT_URL='https://ecole.example/assistance'
TERMS_OF_SERVICE_URL='https://ecole.example/conditions'
PRIVACY_POLICY_URL='https://ecole.example/confidentialite'
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST='smtp.ecole.example'
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER='compte-smtp'
EMAIL_HOST_PASSWORD='secret-a-renseigner'
DEFAULT_FROM_EMAIL='scolarite@ecole.example'
```

Ne placez aucun secret dans les variables de construction du frontend. Les
variables publiques frontend sont incorporées à sa compilation ; `start`
reconstruit les images après une modification de ces valeurs.

## Créer l'établissement et son administrateur

Copiez `deploy/institution.example.json` vers un fichier privé, puis modifiez :

- `schema_name` : identifiant PostgreSQL stable, en minuscules, distinct de `public`.
- `domain` : nom exact de l'API, **sans** protocole, port ni chemin.
- `institution` : identité et coordonnées réelles.
- `admin` : identifiant et email ; facultativement `edx_username` et `edx_user_id`
  pour l'association explicite avec Open edX.

Le fichier ne doit contenir aucun mot de passe.
Conservez-le en `0600`. L'installateur transmet sa configuration et le mot de
passe au processus non privilégié par l'entrée standard ; il ne rend pas le
fichier lisible par les autres utilisateurs et ne monte pas son chemin privé
dans le conteneur.

```sh
python3 scripts/sisctl.py init \
  --variant secondaire \
  --institution /chemin/protege/institution-secondaire.json
python3 scripts/sisctl.py start
python3 scripts/sisctl.py status
python3 scripts/sisctl.py check
```

Pour une livraison dont les images ont déjà été construites et vérifiées,
renseignez `SIS_IMAGE` et `SIS_FRONTEND_IMAGE` avec leurs références immuables,
puis utilisez `init --no-build` et `start --no-build`. L'initialisation conserve
les précontrôles, migrations, création du tenant et collecte des fichiers ;
elle n'essaie pas de reconstruire une image préqualifiée.

L'initialisation applique les migrations versionnées, crée le schéma et le
domaine, crée l'administrateur et collecte les fichiers statiques. Elle peut être
relancée : elle ne réinitialise pas un mot de passe existant et refuse de
réattribuer un domaine ou une identité déjà associés à un autre établissement.
Avant les migrations, `init` interroge en lecture seule les tables de paiement
des schémas déjà présents dans la base de cette variante. Il refuse de continuer
si des paiements par carte `valide` ou `rembourse` partagent une référence externe
non vide : l'index unique de la migration `paiements.0004_card_reference_unique`
échouerait. Le diagnostic indique les schémas et identifiants de paiements,
jamais les références de transaction. Ne supprimez ni ne réécrivez ces paiements
automatiquement : rapprochez-les avec la comptabilité et le prestataire avant
de relancer l'installation.

En mode `dual`, exécutez `init` une fois pour **chaque** variante avant `start`,
avec des domaines et fichiers JSON distincts. En mode `superieur`, utilisez cette
variante dans les deux commandes. `stop` conserve les bases et les fichiers :

```sh
python3 scripts/sisctl.py stop
```

Ne lancez pas `docker compose down --volumes` sur un établissement :
cela supprime ses données.

## Première utilisation

Ouvrez l'URL `FRONTEND_URL`. Dans l'administration, sélectionnez le SIS concerné.

1. Vérifiez les coordonnées, règles académiques et fonctionnalités de l'établissement.
2. Créez l'année et ses périodes/semestres, puis activez-la.
3. Définissez niveaux/matières/salles ou facultés/départements, puis les
   classes/formations nécessaires.
4. Créez les comptes avec les rôles adaptés. Pour le SSO, renseignez les
   associations Open edX dans l'administration Django de **chaque tenant**.
5. Créez les apprenants ou téléchargez le modèle d'import depuis leur liste.

### Types de périodes propres à l'établissement

Dans **Administration → Établissement → Organisation académique → Mode avancé
JSON**, complétez la configuration existante avec `catalogs.period_types`.
Exemple de fragment à intégrer :

```json
{
  "catalogs": {
    "period_types": [
      {"code": "session_courte", "label": "Session courte"},
      {"code": "session_stage", "label": "Période de stage"}
    ]
  }
}
```

Après enregistrement, **Années académiques → Périodes** (secondaire) ou
**Semestres** (supérieur) charge ce catalogue dans le champ **Type**.
Un catalogue absent ou vide conserve les choix historiques de la variante.
Un échec de chargement est affiché, sans remplacer silencieusement le catalogue.
Seuls les codes et libellés sont communiqués aux lecteurs authentifiés :
`GET /api/v1/etablissement/periodes/types/` ou
`GET /api/v1/etablissement/semestres/types/`.

Retirer un code n'efface ni ne convertit les périodes existantes : leur valeur
reste sélectionnable lors d'une modification, avec « configuration conservée ».
Les libellés suivent le catalogue courant ; si un code en est retiré, son code
est affiché. Les dates doivent rester dans l'année ouverte, et une période
clôturée reste non modifiable. Nommer un type « stage » ou « vacances »
ne crée pas automatiquement les règles métier correspondantes.

### Parcours pédagogiques

Au secondaire, **Emploi du temps** permet de créer le personnel enseignant et
les créneaux ; **Présences** permet de créer un appel, saisir ses présences,
puis le fermer et le valider. Affectez d'abord l'élève à sa classe. La validation
de l'appel relève de la vie scolaire/direction, pas du simple rôle enseignant.
Les algorithmes de génération automatique et de résolution des conflits d'EDT
ne sont pas qualifiés par ces formulaires.

**Évaluations** au secondaire et **Notes** au supérieur permettent de créer et
modifier les évaluations, puis de saisir les notes du contrôle continu non
anonyme. L'apprenant doit appartenir à la classe (secondaire), ou disposer d'une
inscription pédagogique validée ou d'une affectation individuelle au semestre
cible (supérieur). La saisie charge uniquement ces apprenants, conserve les notes
existantes et transmet uniquement les lignes modifiées, par lot de 1 000 maximum.
Une note vide reste vide, elle n'est pas transformée en zéro. Le serveur refuse
les doublons, les valeurs hors barème, les apprenants hors périmètre et les
périodes fermées ; le lot est transactionnel. Les examens et la notation anonyme
ne sont pas couverts par ce formulaire et restent à qualifier séparément.

Au secondaire, les écrans **Clubs**, **Cantine**, **Transport**, **Internat**,
**Discipline**, **Conseil de classe** et **Infirmerie** disposent maintenant de
formulaires reliés aux API : clubs/membres/séances, menus/inscriptions/pointages,
lignes/arrêts/véhicules/inscriptions, bâtiments/chambres/séjours, incidents/sanctions,
conseils et visites/stock. Créez d'abord les références dans les listes de la
même page. Les dates de fin facultatives peuvent être effacées ; les dates et
heures complètes sont affichées dans le fuseau du navigateur.

Le conseil suit les actions **Marquer tenu**, puis **Valider** ; cliquer sa
ligne ouvre l'historique. Son procès-verbal est un texte éditable, pas un PDF
généré automatiquement. Pour un incident, sélectionner le personnel rapporteur.
Une visite à l'infirmerie est attribuée au compte connecté, non à un auteur
choisi dans le formulaire ; les permissions médicales restent imposées par l'API.
Les mentions « parents prévenus/notifiés » consignent une action déjà réalisée
et **n'envoient pas elles-mêmes de message**.

Ces formulaires ne remplacent pas les règles de l'établissement : capacités et
chevauchements de séjour restent contrôlés manuellement. Les champs structurés
(allergies, équipements, participants multiples, dossiers médicaux détaillés)
et les décisions individuelles des conseils restent gérés dans l'administration
autorisée. Les listes de présences de séance ne sont pas une saisie d'appel.

Les imports acceptent CSV UTF-8 à virgules et XLSX : 5 Mo et 1 000 lignes maximum
par fichier. Respectez l'ordre des colonnes du modèle et les dates `AAAA-MM-JJ`.
Prévisualisez avant de confirmer. Toute erreur empêche l'application du lot ;
les doublons identiques sont ignorés, les données divergentes sont signalées,
et les dossiers existants ne sont jamais écrasés.

Les nouvelles listes utilisent pagination et recherche serveur. Leur export
parcourt tous les résultats filtrés, pas uniquement la page visible. Les listes
historiques utilisant les hooks génériques chargent toutes les pages : pour de
très grands effectifs, leur migration vers la pagination serveur reste préférable.

Configurez le MFA local depuis **Mon compte**. Conservez une procédure de secours
administrative contrôlée ; le lien de récupération réinitialise le mot de passe,
mais ne désactive pas le second facteur.

### Profils institutionnels et offres mixtes

Dans **Administration → Établissement → Profils et offres**, un administrateur
peut composer plusieurs configurations dans le même établissement. Le catalogue
commun aux deux SIS propose primaire, collège/lycée, université/grande école,
formation professionnelle et profil personnalisé. Un établissement peut ainsi
décrire simultanément un cursus universitaire et une formation courte.

Pour chaque offre :

1. Choisissez un profil, puis **Ajouter une offre**.
2. Adaptez son nom, ses libellés, son calendrier et son mode d'évaluation.
3. Configurez soit un barème et un seuil, soit des compétences, soit une
   décision validé/non validé. Les crédits sont facultatifs, avec un système
   et une cible propres à l'offre lorsqu'ils sont activés.
4. Utilisez **Simuler** pour vérifier les règles côté serveur.
5. Cliquez sur **Enregistrer la configuration** pour conserver les offres.

La simulation distingue une note manquante d'un zéro. Pour les compétences,
toutes doivent être renseignées ; une compétence inconnue ou une note hors
barème produit une erreur. La simulation ne publie aucune note ou décision et
n'attribue aucun crédit. Modifier les règles masque un ancien résultat de
simulation qui ne correspondrait plus au formulaire.

**Raccordement métier disponible : classes, formations, inscriptions et contrôle continu.**
Dans **Classes** ou **Formations**, choisissez une **Offre institutionnelle**.
Le rattachement conserve une copie complète de ses règles. Les nouvelles
inscriptions et évaluations héritent de cette copie ; les dossiers déjà créés
restent inchangés. Pour appliquer de nouvelles règles aux futurs dossiers,
créez une offre avec un nouveau code et sélectionnez-la sur la classe/formation.
Modifier ou retirer le modèle du catalogue ne réécrit pas les copies existantes.

Au secondaire, **Classes → Inscriptions annuelles** permet de créer puis valider
une inscription. Au supérieur, utilisez **Inscriptions administratives** puis
les affectations pédagogiques existantes. L'offre héritée figure dans la liste.
Le rattachement d'une inscription ou évaluation déjà historisée est figé :
un transfert de cursus avec conservation de toutes ses décisions reste un
parcours distinct à développer.

**Transferts simples contrôlés.** Au secondaire, sélectionnez la classe puis
**Changer de classe** sur l'élève ; au supérieur, utilisez **Transférer** sur
l'inscription administrative validée. Un motif est obligatoire. L'année doit
être ouverte ; au secondaire, la destination appartient à la même année.
Le dossier et son inscription sont modifiés ensemble, avec notification et
historique. Les dossiers comportant des règles d'offre historisées, des notes,
des résultats ou, au supérieur, des choix pédagogiques/acquis sont refusés
explicitement : leur transfert nécessite un traitement d'équivalences, non
une suppression ou une conversion automatique des acquis.

Dans **Saisir les notes**, les règles historisées déterminent les champs :
note chiffrée, compétences acquises/non acquises/non renseignées, ou décision
validé/non validé/non renseigné. La sauvegarde enregistre les résultats réels
et leurs appréciations ; un zéro reste distinct d'une absence. Un résultat
renseigné exige le statut **Présentée**. La validation d'un lot est atomique,
y compris pour les critères inconnus et les types invalides.

Le barème des nouvelles évaluations chiffrées rattachées est repris de l'offre,
indépendamment du barème libre du formulaire. Il ne peut plus être modifié
sur l'évaluation. La saisie actuelle accepte des bornes et seuils compris entre
0 et 999,99 avec au plus deux décimales ; un profil incompatible est refusé au
rattachement. Les imports Excel de notes restent réservés aux évaluations
chiffrées. Les résultats par compétences ne sont pas convertis en notes et
n'entrent donc pas dans les moyennes numériques.

**Limites :** la réussite d'une évaluation ne constitue ni une décision de jury,
ni une publication de bulletin, ni une attribution automatique de crédits ou
de diplôme. Les montants de crédits historiques du cursus restent distincts
de la cible configurée dans l'offre. Examens, notation anonyme, agrégation des
compétences sur un parcours et règles de publication restent à raccorder.
Les libellés d'une offre ne renomment pas encore tous les menus.
Les fonctionnalités pédagogiques globales restent gérées dans l'onglet
**Modules** ; ajouter une offre n'active ni Open edX ni un service externe.
Ce lot ne constitue pas une prise en charge complète de chaque catégorie.

Les configurations sont conservées dans
`configuration_academique.learning_offerings`, sous forme de définitions
complètes avec un code unique et une version. Les modifications partielles des
autres paramètres préservent les offres ; les établissements existants sans
cette clé continuent de fonctionner. Remplacer la liste remplace les
configurations d'offres, pas les dossiers académiques. Les migrations
`learning_offering_bindings` ajoutent les références, copies de règles et
résultats structurés avec des valeurs vides pour les données antérieures,
sans conversion des anciennes notes. Appliquez la procédure de mise à jour
du guide : sauvegarde, arrêt, `init` de chaque variante, puis `start` et `check`.

L'API `GET /api/v1/etablissement/current/` expose les modèles dans
`configuration_schema.institutional_profiles`. La sauvegarde utilise le
`PATCH` existant, par exemple :

```json
{
  "configuration_academique": {
    "learning_offerings": [{
      "code": "formation-soir",
      "label": "Formation pratique du soir",
      "profile": "vocational",
      "version": 1,
      "calendar": "session",
      "terminology": {
        "learner": "Stagiaire",
        "educator": "Formateur",
        "group": "Groupe"
      },
      "assessment": {
        "mode": "competency",
        "criteria": [{"code": "pratique", "label": "Maîtriser le geste professionnel"}]
      },
      "credits": null
    }]
  }
}
```

`POST /api/v1/etablissement/current/offering-preview/` reçoit `offering`
(la définition complète) et `result` : `{"score": 12}` pour les notes,
`{"criteria": {"pratique": true}}` pour les compétences, ou `{"passed": true}`
pour la décision simple. Une valeur `null` indique un résultat non renseigné.
La réponse porte le statut `passed`, `failed` ou `incomplete`.
Ces endpoints restent réservés aux administrateurs autorisés du tenant courant.
Les configurations inconnues, versions non prises en charge, doublons et valeurs
invalides sont refusés ; aucune partie du formulaire n'est enregistrée en cas
d'erreur.

Le catalogue des offres enregistrées est également consultable par les comptes
authentifiés du tenant via `GET /api/v1/etablissement/learning-offerings/`,
sans exposer les autres paramètres administratifs.
Les API de classes/formations acceptent `offre_code` et renvoient
`offre_configuration` en lecture seule. Inscriptions et évaluations renvoient
leur propre copie, elle aussi non modifiable par l'API.
La saisie de notes accepte `resultat` pour les modes non chiffrés, avec
`valeur: null` : `{"criteria": {"pratique": true}}` ou `{"passed": false}`.
Les lectures de notes exposent le barème réel et `resultat_offre`, calculé avec
les règles conservées sur l'évaluation.

### Identité, navigation et préférences d'affichage

Le nom et la couleur définis dans **Établissement** alimentent l'espace connecté.
Le logo est téléversé depuis l'administration Django, comme indiqué dans
l'onglet **Apparence**. L'API du profil ne transmet que cette identité,
pas les paramètres administratifs. Une couleur trop peu contrastée est
ajustée pour l'affichage, sans modifier la configuration enregistrée.
Une image impossible à charger est signalée dans la navigation.
La police Inter est servie par l'application, sans appel à un service de
polices. La présentation suit les conventions de la
[charte edX pour Paragon](https://github.com/edx/brand/tree/master/paragon) :
vert sombre `#00262B`, accent `#D23228`, fonds neutres, titres de 40/32/22 px,
boutons et champs rectangulaires, libellés au-dessus des champs.
La couleur institutionnelle personnalise le monogramme, et non les actions :
la même charte reste reconnaissable dans tous les espaces. Aucun logo edX
n'est utilisé comme identité de l'établissement.

Les tableaux de bord de gestion, des enseignants et des apprenants utilisent
Material UI 7 : grilles responsives, cartes, onglets, notifications et navigation.
La charte edX reste appliquée par le thème commun. Les autres pages conservent
leurs composants MUI ou Paragon harmonisés ; cette migration ne remplace pas
le moteur pédagogique. Les dépendances Material UI et icônes restent en version
majeure 7, avec `react-is` aligné sur React 18 pour éviter les erreurs de rendu.

La navigation de gestion comporte au maximum sept entrées : **Accueil**,
**Scolarité**, **Pédagogie**, **Vie de l'établissement**, **Documents**,
**Suivi et accès**, **Administration**. Les pages liées sont accessibles par
les onglets de chaque espace. Les étudiants ont une navigation réduite à
leur dossier, leurs documents, leurs démarches et leurs notifications.
Seuls les espaces et onglets autorisés sont affichés ; les URL directes et
les contrôles serveur sont conservés. Le compte reste accessible dans la
barre supérieure, et les favoris sur l'accueil et dans la palette.
Les dossiers élèves, étudiants et familles présentent leurs résultats,
documents publiés et factures dans des onglets pleine largeur ; un seul
tableau est affiché à la fois, sans supprimer les données des autres onglets.
Les services du secondaire (présences, discipline, cantine, transport, internat,
infirmerie, clubs et emploi du temps) suivent également cette disposition :
un titre de page et des onglets métier, avec les actions de gestion dans le
tableau actif.

Le bouton de recherche ouvre la palette des modules autorisés ; **Ctrl+K / ⌘K** fait de même.
Utilisez les flèches et Entrée pour naviguer, Tab pour les étoiles de favoris,
Échap pour fermer. La palette ne recherche pas de dossiers personnels et
n'exécute pas d'opération métier. Les favoris restent filtrés par les droits
et modules actifs ; ils ne donnent jamais un accès supplémentaire.

Le bouton **Préférences d'affichage** permet de choisir **Clair/Sombre** et
d'effacer les favoris. Ces préférences sont conservées dans le navigateur,
séparément pour chaque compte, établissement et API. Elles ne sont pas
synchronisées entre appareils ; aucun dossier ni jeton d'authentification
n'y est ajouté. Un stockage refusé ou corrompu est signalé, et les changements
restent alors temporaires. La barre supérieure distingue le nom de
l'établissement de l'espace métier ; elle ne permet pas de s'attribuer un rôle.

### Catalogue privé des modules installés

Dans **Administration → Établissement → Modules**, le catalogue installé est
distinct des anciennes options pédagogiques. Le catalogue comporte
le noyau identité/autorisations, le noyau historique/notifications, tous deux
obligatoires, et les modules facultatifs **Réclamations privées** et
**Missions et accès délégués**. Ils sont activés par défaut pour conserver
le fonctionnement des établissements déjà installés.

Chaque carte affiche l'état effectif, les changements non publiés, la version,
l'éditeur, les variantes compatibles, les dépendances, permissions et règles
de conservation. Activer un module n'attribue pas ses permissions à un compte.
La simulation explicite les menus et API concernés, les accès bloqués ou
rétablis, et le maintien des dossiers et notifications déjà engagées.

Modifiez son activation, indiquez un motif, utilisez **Simuler les modules**,
puis **Appliquer les modules**. La simulation ne modifie rien. L'application
enregistre une révision et un événement audité dans la même transaction ;
une révision périmée est refusée et exige un rechargement. Les droits de
configuration de l'établissement courant sont nécessaires.

Une désactivation interdit les API de réclamation, pièces comprises, même
pour un administrateur, et retire l'entrée de navigation lors du chargement
des capacités. Les dossiers et historiques sont conservés et redeviennent
accessibles à la réactivation, avec les mêmes permissions individuelles.
Les notifications déjà engagées continuent via le noyau obligatoire.

La désactivation de `sis.delegations` bloque également toutes les API de mission
(liste, détail, choix, dossiers, historique et actions), y compris pour les
administrateurs, et retire les liens « Mes missions » / « Accès délégués ».
Elle ne change aucun rôle et ne supprime aucune mission. La réactivation
rétablit le service, mais les dates, révocations et droits du responsable
restent contrôlés : une mission expirée ne redevient pas utilisable.

API : `GET /api/v1/etablissement/current/modules/` retourne le catalogue,
les valeurs effectives, leur origine et la révision. `POST` simule et `PATCH`
applique un objet tel que :

```json
{
  "revision": 0,
  "enabled": {"sis.complaints": false},
  "reason": "Suspension temporaire du service"
}
```

Le registre `sis_common/module_registry.py` contient uniquement du code
préinstallé et contrôlé avec la version de l'application. Les six options
historiques ne sont pas un catalogue de plugins. Aucun téléversement ni
chargement arbitraire de code tiers n'est proposé ; compatibilité des packages,
approbation, mises à jour d'extensions externes et marketplace restent des
lots distincts. Les activations de modules restent au niveau du tenant :
elles ne sont pas encore un paramètre héritable.

### Organisation et règles héritées

Dans **Établissement → Organisation et règles**, les boutons **Organigramme**,
**Rattachements** et **Règles héritées** ouvrent trois vues distinctes.
Dans l'organigramme, **Ajouter** crée une unité en mode libre : code, nom,
type et parent éventuel. Les catégories comprennent université, entreprise,
faculté, école, direction, service, département, filière, niveau, classe,
groupe, unité d'enseignement, équipe, campus et programme. **Autre** exige
une précision de catégorie. L'ordre des catégories n'est pas imposé : adaptez
les branches à votre établissement.

Les anciens périmètres campus/département/programme conservent leur mode et
leurs règles historiques. Une unité libre peut prolonger un ancien périmètre,
sans convertir celui-ci. Ces unités ne remplacent pas les facultés, filières
ou dossiers académiques existants. **Modifier** permet le renommage et la
précision ; code, type, parent et mode restent figés. Aucun déplacement,
détachement ou suppression d'unité n'est exposé.

Dans **Rattachements**, choisissez une unité puis une catégorie d'objets.
**Rattacher un objet existant** ouvre une recherche paginée : sélectionnez
l'objet et confirmez le rattachement figé. Les objets déjà rattachés sont
indisponibles ; changer de sélection ou de page retire le consentement.
**Annuler** n'écrit rien. **Consulter** affiche les détails et relations réels,
avec navigation vers les unités liées et pagination des relations nombreuses.

Le catalogue fermé expose utilisateurs, classes/formations, livres et
créneaux de cours, ainsi que les objets académiques réellement présents :
niveaux/groupes/matières au secondaire ; facultés/départements/écoles
doctorales/parcours/UE/ECUE au supérieur. Aucun modèle de groupe ou niveau
supérieur autonome n'est inventé. Le catalogue de livres n'accorde pas de
téléchargement privé. Ces opérations nécessitent un administrateur actif
du tenant ; elles n'octroient ni droit supplémentaire ni accès LMS.

Créez d'abord vos offres dans **Profils et offres** et enregistrez le catalogue.
Dans **Règles héritées**, sélectionnez ensuite le périmètre et choisissez d'hériter, de ne définir aucune
offre par défaut, ou de publier une offre. Un verrou interdit les redéfinitions
inférieures. Un motif est obligatoire. La date d'effet peut être future ; vide,
elle signifie maintenant. Les heures saisies utilisent le fuseau de l'appareil.
**Simuler les règles** affiche la valeur effective, sa provenance, son verrou
et les valeurs descendantes neutralisées, sans écrire de publication.
**Publier les règles** crée une révision immuable et son événement d'audit dans
la même transaction. Une révision périmée ou une date antidatée sont refusées.

Chaque publication remplace les valeurs locales du périmètre à sa date d'effet.
L'historique affiche les 50 publications les plus récentes du périmètre ;
**Consulter les règles à cette date** résout une date passée ou future.
La simulation porte sur la date choisie, pas sur tous les calendriers futurs.
Une publication future reste enregistrée même après une nouvelle publication
immédiate : pour la remplacer, publiez au même instant d'effet ; la révision
la plus récente à cet instant prévaut.

Dans la création d'une classe ou d'une formation, choisissez éventuellement
l'unité d'organisation. Sans offre explicite, l'offre effective à cet instant
est copiée avec sa provenance. Une offre verrouillée ne peut pas être contournée
par un code différent ou par une modification ultérieure du catalogue.
Le rattachement de la classe/formation est figé. Les anciens groupes,
inscriptions, évaluations et résultats ne sont pas recalculés. Un choix explicite
non verrouillé conserve les protections de snapshots déjà applicables.
Une ancienne classe/formation encore sans unité peut recevoir son premier
rattachement dans la vue dédiée ; son offre et sa provenance historiques ne
sont pas recalculées.

API : `GET /api/v1/etablissement/unites/`, création par `POST` et renommage
par `PATCH /api/v1/etablissement/unites/{id}/`.
La création API conserve le mode historique par défaut ; fournissez
`"topology_version": 2` pour le mode libre. Le type `custom` exige
`category_label`. `catalogue/` expose les catégories permises, `references/`
les objets existants paginés. `POST {id}/attachments/` attend
`{"kind": "book", "object_id": 123, "confirm": true}` ;
`GET {id}/attachments/` liste les liens et `GET {id}/attached-object/`
consulte un objet avec `kind` et `object_id`. Ces routes sont relatives à
`/api/v1/etablissement/unites/`.
`GET /api/v1/etablissement/current/hierarchy/` accepte `unit` et `at`
(ISO 8601 avec fuseau). Sur cette dernière route, `POST` simule et `PATCH` publie :

```json
{
  "unit": null,
  "base_revision": 0,
  "values": {"learning.offering": null},
  "locks": ["learning.offering"],
  "effective_from": null,
  "reason": "Aucune offre par défaut autorisée"
}
```

`values: {}` avec `locks: []` restaure l'héritage local. Une valeur non nulle de
`learning.offering` est l'objet d'offre versionné complet, pas seulement son code.
La révision vient de la lecture actuelle. Le droit d'administration de
l'établissement est requis pour simuler, publier et consulter ces règles.
Cet incrément ne fournit pas encore la hiérarchie plateforme/pays/réseau,
les autorisations par campus ni un moteur générique de workflows.

### Calendriers, examens et traçabilité

Les clôtures et activations passent par les actions dédiées, pas par un
changement direct de statut. Les créations, modifications, déplacements et
suppressions des objets académiques couverts sont contrôlés contre leurs
années/périodes/sessions d'origine et de destination. Les notes et résultats
empêchent la suppression en cascade de leurs parents. Les exceptions de
rattrapage restent soumises aux règles et fenêtres configurées.

Dans **Examens**, les deux variantes permettent de gérer sessions, épreuves,
convocations et résultats. Le résultat suit les actions **Soumettre → Vérifier
→ Valider → Publier**, selon les droits et la politique de l'établissement.
Modifier une note encore modifiable exige une nouvelle vérification ; une
modération ne peut pas écraser un résultat publié. La publication et la
réouverture sont tracées et notifient l'apprenant.

Au supérieur, le détail d'une **Formation** permet de gérer parcours, maquettes,
UE et ECUE, et de consulter les étudiants et créneaux de cette formation.
**Emploi du temps** expose les vues formation/enseignant/salle, les horaires
types, les créneaux, les réservations et leur décision. La détection des
conflits n'est pas encore un moteur exhaustif de planification multi-campus.

Le **Journal des opérations** filtre par personne et dates inclusives ; ces
filtres s'appliquent aussi au bilan et aux exports. Les réclamations, missions,
signatures et archives privées restent dans leurs historiques autorisés,
hors du journal global. Les journaux techniques conservent les
identifiants de requête, tenant et acteur, la méthode, le chemin, le statut
et la durée, sans enregistrer les corps de requête ni les secrets.

Ces protections ne constituent pas une homologation de tous les métiers :
jurys, diplômes et équivalences restent à compléter.

### Admissions et changements de cursus entre années

Les admissions réutilisent les dossiers existants, sans créer un autre compte.
Une inscription commence **En cours** au secondaire, **Provisoire** au supérieur.
Les actions **Valider**, **Refuser** et **Annuler la demande** contrôlent l'état
de départ ; refus et annulation exigent un motif. Un statut ne peut pas être
forcé par création ou modification CRUD. Un dossier déjà validé ne peut pas
être refusé ou annulé par ce circuit de demandes en attente.

**Réinscrire / changer de cursus** crée une nouvelle inscription à examiner,
dans une année postérieure sans chevauchement, avec la classe/formation choisie.
L'année d'origine peut être clôturée puisqu'aucun résultat ni inscription
d'origine n'est modifié. La destination doit être ouverte, appartenir au même
établissement et respecter les périmètres du gestionnaire. Les doublons sont
refusés. Les règles de la destination sont enregistrées dans la nouvelle
inscription ; les anciennes règles, notes et inscriptions pédagogiques restent
inchangées. Les deux historiques conservent le lien de transition, le motif,
l'acteur et la date ; l'apprenant reçoit une notification interne.

Au secondaire, valider une année future ne remplace pas immédiatement la classe
actuelle. Le basculement ultérieur des classes n'est pas automatisé par ce lot.
Les transferts dans la même année restent limités aux dossiers compatibles :
les équivalences, admissions de candidats sans dossier, sélection/classement,
listes d'attente et transferts inter-établissements ne sont pas automatisés.

### Missions déléguées aux apprenants

Un responsable doté de `core.manage_accessdelegation` peut créer un **Accès
délégué**, avec bénéficiaire, ressource, dossiers précis, dates et motif.
Les classes sont proposées au secondaire ; les formations et conventions de
stage au supérieur. Le responsable doit aussi pouvoir lire ces dossiers,
dans ses périmètres actuels. Un indicateur `is_staff` ne suffit pas.

L'apprenant retrouve **Mes missions** dans son portail. Il consulte seulement
des résumés des dossiers sélectionnés, sans changer de rôle ni obtenir des
droits de modification, de signature ou d'accès aux notes/données financières.
Une mission est limitée à 100 dossiers, sans accès global implicite.
Expiration, révocation ou perte d'habilitation du responsable retirent l'accès
côté serveur. Création et révocation notifient le bénéficiaire ; consultations
et décisions sont tracées dans l'historique privé de la mission.

### Documents personnels et téléchargements

L'entrée **Mes documents** du menu **Mon espace** donne accès aux documents
déjà établis, sans créer un autre dossier apprenant :

| Variante et compte | Documents accessibles |
|---|---|
| Secondaire, élève | Ses bulletins avec `publie=true`. |
| Secondaire, parent | Bulletins publiés des enfants dont le lien familial autorise le portail ; la révocation retire cet accès. |
| Supérieur, étudiant/doctorant | Ses relevés avec `signe=true`, transcripts et attestations avec un `signe_par` renseigné. |

Un compte actif doit appartenir à l'établissement demandé. Les lectures par
identifiant, historiques et téléchargements appliquent les mêmes restrictions
que les listes. Un compte apprenant marqué `is_staff` ne devient pas pour autant
gestionnaire de documents. Les gestionnaires continuent d'utiliser
**Bulletins** ou **Relevés de notes** pour consulter leurs documents, y compris
les brouillons, et l'historique, selon leurs droits et périmètres.

La recherche et la pagination sont serveur ; **Exporter la liste filtrée (CSV)**
reprend toutes les pages autorisées pour cette recherche. **Télécharger le PDF**
utilise la session authentifiée, affiche les refus/erreurs et trace le succès
dans l'historique du document avec l'acteur et la date. La réponse PDF utilise
`Cache-Control: private, no-store` ; aucun chemin de stockage n'est exposé comme
lien public. Un téléchargement ne réappose pas de signature et ne notifie pas
un titulaire de signature.

**Limites :** la validation administrative existante n'est pas une signature
cryptographique vérifiable. Les PDF ordinaires sont générés à la demande depuis
les synthèses enregistrées ; seules les versions explicitement apposées dans
le circuit ci-dessous sont archivées. Les relevés détaillés exhaustifs, les
diplômes dans cet espace, les exports de données XLSX/JSON et les gros exports
asynchrones restent à compléter. Le CSV est produit côté navigateur : seuls
ses appels de lecture ont la traçabilité technique, sans nouvel événement
d'audit métier d'export.

### Signatures approuvées et versions archivées

Le menu **Signatures** exige des habilitations explicites, attribuées depuis
l'administration des utilisateurs/groupes :

| Permission | Usage |
|---|---|
| `core.request_signature` | Demander une identité de signature personnelle et gérer ses mandats. |
| `core.approve_signature` | Approuver/refuser la demande d'une autre personne, suspendre/révoquer. |
| `core.use_signature` | Apposer une signature autorisée ; les droits de modification et périmètres du document restent nécessaires. |
| `core.revoke_documentarchive` | Révoquer une version accessible, sans effacer son PDF ni sa preuve. |

1. Le titulaire renseigne sa fonction, les types de documents et la période.
2. Une autre personne habilitée contrôle la demande dans **Validations
   indépendantes** et motive sa décision. L'auto-approbation est interdite,
   même à un super-administrateur.
3. La validation génère une clé Ed25519 ; sa partie privée est chiffrée avec
   `FIELD_ENCRYPTION_KEY` et n'est jamais renvoyée par l'API.
4. Dans **Documents archivés**, le titulaire choisit un document déjà publié
   ou administrativement validé et sa signature approuvée. Un autre opérateur
   doit également être habilité et posséder un mandat explicite, daté, non
   révoqué, accordé par le titulaire. Le titulaire peut suspendre/révoquer sa
   signature ; une réactivation nécessite un autre validateur.
5. Chaque apposition enregistre atomiquement le PDF, sa version, son SHA-256,
   le manifeste et la preuve détachée, l'opérateur et son éventuel mandat,
   l'événement et les notifications internes au titulaire et au bénéficiaire.
   Une notification impossible empêche l'apposition. Un rejeu de la même clé
   d'idempotence renvoie la même archive, sans nouvelle apposition.

Dans **Mes documents → Versions signées**, le bénéficiaire télécharge le PDF
archivé et sa preuve JSON. **Vérifier l'intégrité** contrôle la version conservée
ou compare un PDF téléversé (limite PDF commune, 25 Mo par défaut). Le serveur
utilise la clé approuvée connue de l'établissement, pas une clé fournie par le
visiteur. L'intégrité et la révocation sont affichées séparément : une version
révoquée demeure vérifiable et conservée. L'expiration d'une autorisation
interdit les nouvelles appositions, sans invalider rétroactivement les preuves.
Un téléchargement ne réappose pas de signature.

Les archives et révocations sont protégées contre modification/suppression
par l'ORM et par des déclencheurs PostgreSQL. Une correction produit une
nouvelle version ; les PDF binaires sont inclus dans la sauvegarde PostgreSQL.
Conserver aussi la clé de chiffrement dans la sauvegarde chiffrée et sécurisée :
sa perte bloque les nouvelles signatures utilisant les clés existantes.

**Portée de la preuve :** signature institutionnelle détachée d'un manifeste,
pas de PAdES incorporé au PDF, de certificat qualifié, d'horodatage de confiance
externe ni de conformité juridique automatique. La date est celle du serveur.
Pour une vérification hors ligne, l'empreinte de clé doit être obtenue par un
canal institutionnel de confiance ; le fichier JSON seul n'établit pas l'identité.
L'immutabilité applicative/base ne constitue pas un stockage WORM résistant
à un administrateur d'infrastructure. Conservation légale, signature qualifiée,
certification externe et politique de purge doivent être qualifiées séparément.

### Réclamations privées des apprenants

Dans **Mes réclamations**, un élève/étudiant/doctorant peut déposer une demande
sur un résultat, une inscription, des frais ou un autre sujet. Objet, motif
et référence du dossier concerné sont conservés avec un numéro `REC-…`.
Les demandes des parents pour leurs enfants ne sont pas encore prises en charge.

Après l'envoi, l'apprenant peut ajouter des **PDF privés** : dix pièces au plus,
25 Mo par fichier dans la configuration standard. Le serveur vérifie extension,
type MIME, taille et signature PDF ; ce contrôle **n'est pas une analyse
antivirus**. Les fichiers sont stockés sous `PRIVATE_EXAM_STORAGE_ROOT/reclamations`,
dans le volume de données privé déjà sauvegardé par le pack Docker. Ne pas
publier ce répertoire via un serveur de fichiers.

Deux habilitations Django, propres au tenant, organisent le traitement :

| Permission | Accès |
|---|---|
| `core.affecter_reclamation` | Recevoir les nouvelles demandes, consulter la file de l'établissement et affecter un agent. |
| `core.traiter_reclamation` | Consulter et traiter uniquement les demandes affectées à cet agent. |

Le super administrateur initial peut affecter un dossier à lui-même pour la
recette. En exploitation, utilisez des comptes nominatifs : attribuez ces
permissions explicitement, directement ou via un groupe. Les API existantes
`GET /api/v1/utilisateurs/permissions/` (suivre la pagination), les groupes
`/api/v1/utilisateurs/groupes/` et `PATCH /api/v1/utilisateurs/comptes/{id}/`
permettent cette administration depuis un compte habilité. Sélectionnez les
permissions par `app_label: core` et `codename`, pas par identifiants supposés.
Les listes `user_permissions` et `groups` d'un PATCH **remplacent** les listes
existantes : les lire et préserver leurs autres valeurs avant toute modification.
L'écran simplifié Utilisateurs n'est pas encore un éditeur complet d'habilitations.

Un coordinateur peut réaffecter un dossier ; l'ancien agent perd alors l'accès
s'il n'a pas aussi l'habilitation de coordination. Le demandeur ne peut pas
affecter ni décider son propre dossier, même s'il possède ces habilitations.
Les rôles usuels du personnel et `is_staff` seuls ne donnent pas accès à ce module.

Le parcours standard est **Soumise → En cours → Complément demandé ou Réponse
apportée → Clôturée**. Le demandeur peut répondre à une demande de complément,
clôturer une réponse ou déposer un recours motivé depuis une réponse/clôture.
Le recours rouvre le dossier et avertit le service ; les décisions précédentes
restent dans l'historique. Délais, relances et niveaux de recours configurables
ne sont pas encore implémentés. Une décision de réclamation ne modifie jamais
automatiquement les notes, inscriptions ou paiements.

Les notifications internes sont persistées dans la même transaction que les
changements. Elles ne contiennent pas le motif privé ; leur lien ouvre le dossier
après un nouveau contrôle d'accès. L'historique détaillé n'est pas exposé dans
les rapports globaux de workflow. Un téléchargement vérifie le tenant, le droit
sur la demande et le rattachement de la pièce à celle-ci.

Pour les intégrateurs, la base est `/api/v1/core/reclamations/` :

| Méthode et route relative | Données / résultat |
|---|---|
| `GET` / `POST` | Liste paginée filtrable par `statut` / dépôt avec `categorie`, `objet`, `description`, `reference_dossier` facultative. |
| `GET capacites/` | Droit de dépôt et agents affectables, uniquement pour les coordinateurs. |
| `GET {id}/` | Détail, historique, pièces, version courante et actions autorisées. |
| `POST {id}/affecter/` | `version`, `responsable` (identifiant d'un agent habilité). |
| `POST {id}/message/` | `version`, `message` non vide. |
| `POST {id}/transition/` | `version`, `message` motivant la transition, `statut` parmi `complement`, `resolue`, `cloturee`, `recours`. |
| `POST {id}/pieces/` | Multipart : `version`, `fichier` PDF. |
| `GET {id}/pieces/{piece_id}/telecharger/` | Pièce en téléchargement privé, jamais une URL publique. |

Chaque réponse de mutation renvoie la nouvelle version. Un conflit HTTP 409
impose de recharger le dossier et de relire les changements avant de réessayer.
Ni modification libre ni suppression du dossier ou de l'historique ne sont
exposées par ce parcours.

### Comptes et responsabilités

L'administrateur initial est un compte de secours privilégié, pas un compte
partagé de travail quotidien. Créez des comptes nominatifs et attribuez les
groupes/permissions métier depuis l'administration Django du tenant.
`is_staff` autorise l'administration Django ; ce n'est pas un rôle métier.
Testez avec les utilisateurs concernés les droits direction/scolarité,
enseignant, apprenant et famille avant l'ouverture.

Les API des comptes/groupes, notes et paiements ne déduisent plus une
habilitation métier du seul drapeau `is_staff`. Les permissions explicites,
les rôles métier historiques pris en charge et le superutilisateur restent
distincts. Les vues personnelles des notes et évaluations croisent
l'appartenance de l'utilisateur avec ses restrictions contextuelles :
un enseignant ne gagne pas accès à un autre périmètre parce qu'il est `staff`.
Les changements ne réattribuent pas automatiquement les permissions des
comptes existants.

#### Compte nominatif d'un partenaire

Dans les deux SIS, **Administration → Utilisateurs → Comptes → Ajouter**
propose le rôle **Partenaire** (`partenaire`). Créez un compte nominatif rattaché
à l'établissement, et non un administrateur renommé. L'API existante
`POST /api/v1/utilisateurs/comptes/` accepte ce même rôle. La création avec
un rôle différent du rôle apprenant par défaut, comme sa modification ultérieure,
reste réservée au superutilisateur par les validations existantes.

Ce libellé n'attribue ni groupe ni permission : le compte est non-staff et
non-superutilisateur par défaut, sans dossier élève/étudiant ou personnel créé
automatiquement. Les habilitations éventuellement nécessaires se donnent
explicitement par les groupes/permissions existants ; le rôle ne suffit pas
pour entrer dans un portail apprenant ou staff. La politique MFA reste inchangée.
Ne passez pas par l'import **Students**, qui crée des apprenants, ni par le
provisionnement LMS pour créer ce compte SIS.

Le champ `role` reste libre (100 caractères) : les rôles existants ou personnalisés
ne sont ni restreints ni renommés. Seuls son catalogue de libellés et les choix
du formulaire sont complétés ; aucune migration de schéma ou de données n'est
nécessaire. Les « profils institutionnels » des offres ne sont pas des profils
de compte.

Au secondaire, la lecture du répertoire des élèves exige `eleves.view_eleve`
pour les comptes sans accès personnel, partenaire compris. Ni `is_staff` ni
un rôle administratif ou personnalisé ne remplacent cette habilitation.
Les groupes Django existants permettent de l'attribuer et de la retirer ;
les périmètres `eleves` et `classes` continuent de restreindre les résultats.
Sans droit, liste et recherche du répertoire sont vides, les détails renvoient
404 et la collecte paginée utilisée pour l'export ne fournit aucun dossier.
L'accès personnel apprenant et les liens tuteur autorisés restent conservés,
ainsi que le filtrage par établissement. Ce contrôle de lecture ne modifie pas
les autorisations d'écriture/import ni les contrats des autres API.

Les POST `/api/v1/integration/sync/enroll/` et `sync/teaching/` exigent
désormais `integration.change_edxaccessintent` ou un superutilisateur ;
`is_staff` seul ne suffit pas et n'est pas requis pour ces deux routes.
La permission peut être limitée dans `attributs_acces.permission_scopes`,
par exemple avec un identifiant de mapping **fictif** :

```json
{
  "permission_scopes": {
    "integration.change_edxaccessintent": {
      "courses": [42],
      "kinds": ["enrollment"]
    }
  }
}
```

`courses` contient les identifiants numériques des associations de cours du
SIS, pas les clés `course-v1:…` du LMS. `kinds` accepte `enrollment` et
`teaching`. Une liste vide ou une contrainte inconnue refuse l'opération.
Ce contrôle précède toute création de décision/outbox ou requête au LMS.
Les autres opérations administratives d'intégration non migrées conservent
leur garde technique `staff` ; cette évolution ne constitue pas une
qualification complète des rôles ni du circuit des notes officielles.

Les écrans historiques complémentaires n'ont pas tous été réécrits :
des actions et contrats métier restent à qualifier, même lorsqu'une liste
se charge. La maquette supérieure est annuelle ; l'ancienne action
`maquettes/par_semestre/` signale explicitement ce périmètre au lieu de
prétendre manipuler des lignes de semestre inexistantes.

Les anciens uploads dans `MEDIA_ROOT` ne sont **pas publiés globalement en
production**. Les documents privés doivent passer par leurs endpoints autorisés.
Avant d'activer un ancien parcours photo/pièce jointe, vérifier son mécanisme
de téléchargement ; ne montez jamais tout `MEDIA_ROOT` en accès anonyme.

## Exploitation et restauration

Consultez [BACKUP_RESTORE.md](BACKUP_RESTORE.md) pour les scripts historiques et
la section ci-dessous pour les snapshots de cette distribution.

Créez un fichier contenant un secret de sauvegarde indépendant, avec permissions
`0600`, **hors du dépôt de sauvegardes**. Conservez-en une copie sécurisée :
sans lui, les snapshots sont irrécupérables.

```sh
python3 scripts/sis_backup.py \
  --repository /sauvegardes/chiffrees/sis \
  --password-file /chemin/protege/restic-password backup
python3 scripts/sis_backup.py \
  --repository /sauvegardes/chiffrees/sis \
  --password-file /chemin/protege/restic-password check
```

La sauvegarde arrête temporairement les API, workers et planificateurs, puis Redis.
Elle conserve les dumps PostgreSQL, **tout `/data`**, les deux stockages privés,
Redis et `.env` dans un dépôt Restic chiffré local. Elle redémarre les services
qui fonctionnaient avant l'opération, y compris si la sauvegarde échoue.
Prévoir une fenêtre de maintenance.

Les volumes Redis et fichiers doivent déjà exister : leur absence est bloquante,
elle n'est plus remplacée par une sauvegarde vide. Chaque dump est relu par
`pg_restore --list`. Le staging en clair est privé et supprimé après l'opération,
à côté de `.env` par défaut, jamais dans le répertoire temporaire système.
Prévoir assez d'espace, ou utiliser `--staging-dir /chemin/prive/staging`.
Le staging et `.env` doivent rester **hors** du dépôt chiffré, pour ne pas y
laisser des fichiers en clair susceptibles d'être répliqués avec les snapshots.
Les services initialement arrêtés ne sont pas démarrés par dépendance à la reprise.
Un arrêt brutal de l'hôte ne permet pas de garantir cette reprise : contrôler
les services et supprimer prudemment le staging abandonné après diagnostic.

Le manifeste chiffré conserve le projet source, l'horodatage, les identifiants
d'images déployées et les empreintes des clés d'authentification/chiffrement.
Il **ne contient pas les images elles-mêmes**, ni le code, ni le LMS.
Conserver aussi le commit, les images dans un registre maîtrisé ou des archives
privées et les éventuelles adaptations de déploiement.

```sh
python3 scripts/sis_backup.py \
  --repository /sauvegardes/chiffrees/sis \
  --password-file /chemin/protege/restic-password inspect --snapshot ID_SNAPSHOT
```

`inspect` n'affiche ni `.env` ni les clés. `check` relit les données chiffrées
mais ne remplace pas un exercice de restauration. Si le dépôt dépend d'un
montage, ajouter `--require-mount /sauvegardes` à **chaque** commande automatisée :
une absence du montage est alors bloquante avant création du dépôt.
Sans cette option, un chemin local valide reste accepté ; la copie hors machine
est toujours une responsabilité distincte.

`snapshots` liste les snapshots. `prune` applique explicitement la rétention
7 jours / 4 semaines / 12 mois. Rien n'est envoyé à un service tiers par ces outils.
Le dépôt doit ensuite être répliqué vers un stockage maîtrisé, indépendant de
la machine ; les sauvegardes du LMS, Studio et de leurs fichiers sont séparées.

Planifiez cette commande avec cron ou un timer système sous un compte
d'exploitation autorisé à utiliser Docker, en empêchant deux exécutions
simultanées, par exemple avec `flock`. Supervisez le code de retour et l'âge du
dernier snapshot ; un cron sans alerte n'est pas une supervision.
Fixez avec l'établissement la perte maximale acceptable (RPO), le délai de
reprise (RTO), la rétention et la fréquence des exercices de restauration.

### Planification avec systemd

Les modèles `deploy/sis-backup.service`, `deploy/sis-backup.timer` et
`deploy/backup.conf.example` évitent d'écrire un cron ad hoc. Ils ne sont
**jamais activés automatiquement** par l'installateur ou la recette.

Sur le serveur autorisé, créer un compte système `sis`, groupe principal `sis`,
et lui donner l'accès Docker. Cet accès équivaut pratiquement à des droits root :
réserver ce compte à l'exploitation. Préparer `/etc/lms-sis` et
`/srv/sis-backups`, accessibles uniquement à ce compte. Installer dans
`/etc/lms-sis/institution.env` la configuration réelle et dans
`/etc/lms-sis/restic-password` le secret indépendant, propriétaire `sis`,
permissions `0600`. Adapter les chemins de `backup.conf.example`, puis :

```sh
sudo install -o root -g sis -m 0640 deploy/backup.conf.example /etc/lms-sis/backup.conf
sudo install -m 0644 deploy/sis-backup.service deploy/sis-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start sis-backup.service
sudo systemctl status sis-backup.service
sudo journalctl -u sis-backup.service --since today
```

Vérifier le snapshot et sa restauration avant d'activer le calendrier :

```sh
sudo systemctl enable --now sis-backup.timer
sudo systemctl list-timers sis-backup.timer
```

Le timer démarre quotidiennement à 02:00, avec jusqu'à 15 minutes de décalage.
Il rattrape un déclenchement manqué après un arrêt. `flock` interdit deux
exécutions simultanées utilisant `/run/lms-sis-backup/backup.lock` ; employer ce
même verrou pour les autres automatisations. Une sauvegarde peut arrêter
temporairement les applications : convenir de l'horaire avec l'établissement.
Le service conserve ses erreurs dans le journal, mais **n'envoie pas d'alerte** :
brancher la supervision sur l'état d'échec et l'âge du dernier snapshot.
La vérification Restic, la rétention et la réplication hors machine restent
des opérations distinctes à planifier. Si le dépôt utilise un montage distant,
contrôler sa présence avant l'exécution pour éviter une sauvegarde locale
accidentelle à la place du stockage hors machine.

### Restaurer dans une installation isolée

La restauration automatisée refuse une base ou un volume non vide. Utilisez
une installation isolée et un **nouveau `COMPOSE_PROJECT_NAME`** :

```sh
python3 scripts/sis_backup.py \
  --repository /sauvegardes/chiffrees/sis \
  --password-file /chemin/protege/restic-password \
  recover-config --snapshot ID_SNAPSHOT --output /chemin/protege/restauration.env
```

Modifiez les domaines/ports et `COMPOSE_PROJECT_NAME` dans ce fichier, mais
conservez `FIELD_ENCRYPTION_KEY`, `DJANGO_SECRET_KEY` et `WEBHOOK_SECRET`.
`recover-config` affiche l'identifiant complet résolu : réutilisez **cet ID**,
pas un nouveau `latest`, pour la restauration.
Ne démarrez pas les applications et n'exécutez
pas `init` avant la restauration, car leurs bases doivent être vierges.

```sh
python3 scripts/sis_backup.py \
  --repository /sauvegardes/chiffrees/sis \
  --password-file /chemin/protege/restic-password \
  --env-file /chemin/protege/restauration.env \
  restore --snapshot ID_SNAPSHOT --confirm-empty-target
python3 scripts/sisctl.py --env-file /chemin/protege/restauration.env start --no-build
```

Avant ce démarrage, récupérer les images de l'inventaire et renseigner
`SIS_IMAGE`/`SIS_FRONTEND_IMAGE` avec leurs références immuables dans le fichier
restauré. `--no-build` évite de reconstruire arbitrairement la révision courante.
Isoler aussi les **sorties** LMS/SMTP/SMS/paiement et remplacer les destinations
externes par celles de recette autorisées avant de démarrer une copie de test.
Un nouveau nom de projet ne constitue pas un pare-feu : `start` lance aussi
les workers et Beat, qui peuvent rejouer les files restaurées. Ne pas rattacher
la copie au réseau LMS de production ni réémettre des opérations réelles.
Le nouveau format de sauvegarde (2) refuse le projet source et la divergence
des trois clés ; les snapshots historiques (format 1) restent lisibles mais
ne permettent que le contrôle de leur clé de chiffrement. Dans les deux cas,
les bases et volumes cibles doivent être vides.
Une erreur après le début du transfert peut laisser une cible partielle :
les applications restent arrêtées, ne contournez pas le refus « non vide ».
Diagnostiquer et recommencer dans un autre projet vide, sans effacer la source.
Ne jamais lancer une restauration vers les volumes d'un autre projet.

Si les domaines changent, ajoutez les nouveaux domaines aux tenants avant le
contrôle de santé ; `init` peut être utilisé **après** restauration avec les
mêmes identités et les nouveaux domaines. Vérifiez comptes, dossiers,
documents privés et files de tâches avant toute bascule DNS.

## Diagnostic et qualification

```sh
python3 scripts/sisctl.py --env-file /chemin/protege/institution.env doctor
```

`doctor` est en lecture seule et retourne un code non nul si un service attendu
manque, est arrêté ou échoue à sa sonde. Il couvre chaque variante sélectionnée,
PostgreSQL, Redis, API, workers, Beat, frontend et passerelle, sans afficher
l'environnement ni lire les journaux privés. La sonde Celery existante cible
le worker de **son conteneur** ; un autre worker vivant ne masque pas sa panne.
Un Beat dupliqué est refusé. Un processus Beat vivant ne prouve pas qu'une tâche
périodique s'exécute : surveiller également l'âge de l'outbox et qualifier une
tâche périodique contrôlée. La passerelle n'a pas de sonde de certificat :
contrôler le HTTPS public et son renouvellement séparément.

`SIS_WORKER_CONCURRENCY=1` permet de limiter chaque worker sur un pilote contraint
(défaut conservé : 2). Cela ne remplace pas un dimensionnement et ne réduit pas
les besoins de construction ou des autres services. Ne pas multiplier Beat.

`/health/` vérifie que le processus répond. `/ready/` vérifie PostgreSQL et Redis.
Ces chemins doivent être appelés avec le domaine d'un tenant initialisé :
un Host inconnu renvoie 404 par conception. Les conteneurs API utilisent
automatiquement le domaine configuré pour leurs sondes.

Les métriques `/metrics/` sont volontairement bloquées par le proxy public.
Collectez-les uniquement depuis un réseau d'administration avec le bon Host ;
voir [MONITORING.md](MONITORING.md). Surveillez aussi espace disque, erreurs SMTP,
échecs/outbox anciens, sauvegardes récentes et workers/Beat.

Pour une recette jetable sans comptes réels, avec Docker, Node et Chromium
Playwright disponibles :

```sh
python3 scripts/verify_installation.py \
  --mode dual \
  --verify-backup \
  --work-dir /chemin/vers/un-nouveau-dossier-de-recette
```

Le script génère uniquement des identités fictives, initialise les schémas deux
fois pour contrôler l'idempotence, exécute les parcours navigateur (y compris
la saisie des notes et les formulaires de vie scolaire) et contrôle le
redémarrage. Il supprime les volumes de **son projet jetable** à la fin.
L'option `--keep`, réservée au diagnostic, conserve ce projet : arrêtez-le et
supprimez ses volumes explicitement une fois l'analyse terminée.

Avec `--verify-backup`, la recette restaure aussi un snapshot dans un second
projet vide, compare comptes et secrets MFA déchiffrés, vérifie les fichiers
des trois racines de stockage et le refus d'écraser une base existante.
Les fichiers de recette locaux contiennent des secrets fictifs : gardez leur
dossier privé et supprimez-le après diagnostic.

## Mises à jour et retour arrière

1. Relever le commit utilisé, les identifiants d'images et les options de
   configuration. Lire les changements et refaire la recette sur une copie isolée.
2. Prendre un snapshot chiffré complet, vérifier sa restauration et arrêter
   les applications pendant la mise à jour, en gardant les bases accessibles
   au précontrôle (`sisctl stop` arrêterait aussi les bases). Conserver les
   anciennes images.
3. Avec la révision approuvée et **avant toute migration**, exécuter
   `python3 scripts/sisctl.py preflight` lorsque les bases de la distribution
   Compose sont accessibles. Cette vérification en lecture seule couvre toutes
   les variantes activées et leurs schémas de paiement déjà créés, sans démarrer
   de conteneur. Un échec de connexion est bloquant ; les doublons de références
   de carte validées/remboursées doivent être rapprochés manuellement sur la
   copie isolée, sans effacer de paiements. Refaire le contrôle après correction.
4. Installer la révision approuvée, conserver `.env` et ses clés, puis lancer :

   ```sh
   python3 scripts/sisctl.py --env-file /chemin/protege/institution.env update --confirm-backup
   python3 scripts/sisctl.py --env-file /chemin/protege/institution.env check
   ```

   `--confirm-backup` est une **attestation de l'opérateur**, pas une vérification
   automatique de son snapshot. La commande exige les bases et Redis existants
   en fonctionnement. Elle construit séquentiellement le backend partagé puis
   le frontend (ou utilise les images préparées avec `--no-build`), arrête les API,
   workers et Beat, refait le précontrôle des paiements puis applique
   `migrate_schemas --shared` et `--tenant` pour **tous les tenants des variantes
   actives**, collecte les fichiers statiques et exécute `manage.py check`.
   Elle ne redemande ni fichier institution ni mot de passe administrateur,
   ne reprovisionne aucun compte et ne modifie pas les règles métier par défaut.
   Une migration peut modifier ces règles : lire et qualifier les migrations
   avec les autres chantiers avant cette étape.
5. Si ces étapes réussissent, `update` redémarre la distribution sans reconstruire
   et exécute `doctor`. Contrôler ensuite les parcours et reprendre le service.
   Si une migration/prévalidation échoue, les écrivains restent arrêtés :
   ne lancer ni `start` automatique ni ancien code sur la base partiellement migrée.
   `init` reste destiné au provisionnement d'un établissement, pas à une mise à
   jour exhaustive des établissements déjà présents.

Ce précontrôle est ciblé sur `paiements.0004` : il ne prouve ni l'absence
d'autres conflits de migration ni la compatibilité des données existantes avec
toutes les nouvelles règles. Validez la mise à jour sur une restauration isolée ;
empêchez de nouvelles écritures entre le contrôle et la migration.

Après une migration incompatible, **ne redémarrez pas simplement l'ancien code
sur la nouvelle base**. Restaurer le snapshot complet dans un projet isolé avec
la version précédente, vérifier les données puis basculer le routage. Documenter
les écritures effectuées depuis le snapshot avant de décider du retour arrière.

### Désactivation réversible des groupes

La migration `utilisateurs.0006_group_lifecycle` des deux SIS ajoute l'état
`actif` des groupes de permissions. L'absence de ligne pour un ancien groupe
signifie **actif** : aucun membre ni droit configuré n'est supprimé ou recopié.
Appliquer la migration dans tous les schémas concernés, applications arrêtées,
avant de démarrer la nouvelle image. Une table manquante est une erreur de
migration, pas une raison de rétablir les anciens backends.

Les nouveaux backends `sis_common.group_backends.ActiveGroupModelBackend` et
`ActiveGroupObjectPermissionBackend` filtrent les groupes désactivés dans les
contrôles Django et les permissions objet Guardian. Ne pas ajouter les backends
standards en parallèle : ils réaccorderaient les droits désactivés. Les anciennes
sessions Django contenant l'ancien chemin de backend nécessitent une nouvelle
connexion ; prévenir les utilisateurs avant la bascule. Les droits sont recalculés
à chaque requête avec un utilisateur fraîchement chargé, sans changer le rôle
métier, `is_staff`, les permissions directes ou les autres groupes actifs.
Cela ne révoque pas des privilèges LMS attribués indépendamment.

La version de Guardian livrée ne reconnaît que le chemin exact de son backend
standard : `manage.py check` signale donc `guardian.W001` pour ce backend dérivé.
Ne pas appliquer sa suggestion d'ajouter le backend standard. Cet avertissement
ne remplace pas la qualification des droits modèle et objet décrite ci-dessous.

Les caches Django restent locaux à une instance utilisateur. Un traitement long
doit recharger cette instance avant une nouvelle décision d'accès. Les raccourcis
Guardian appelés directement, tels que `get_objects_for_user` ou
`ObjectPermissionChecker`, ne passent pas par ces backends : ne pas les introduire
comme substituts aux contrôles de l'application sans intégrer ce filtrage.

Le snapshot de capacités exclut également les noms des groupes Django désactivés,
pour ne pas les présenter aux écrans comme des capacités actives. Les listes
d'appartenance des comptes conservent leurs identifiants. Les groupes définis dans
la configuration académique restent calculés à partir de leurs propres conditions
(permissions et attributs) : un droit direct ou un autre groupe actif peut donc
continuer de les satisfaire.

Qualifier sur la copie isolée : groupe ancien actif, désactivation avec conservation
des membres/permissions, refus d'accès dans une session déjà ouverte, puis
réactivation et audit avant/après. **Un retour à une image antérieure ignore cet
état et peut réaccorder les droits des groupes désactivés**. Conserver en maintenance
l'ensemble données/image compatible jusqu'à validation d'une restauration et
d'une revue des révocations ; ne pas annuler cette migration pour contourner un refus.

### Dépendances applicatives

Le backend utilise Python 3.12, Django 5.2 LTS et `requirements.lock` avec
empreintes de tous les paquets. Pour une mise à jour de dépendances en développement :

```sh
uv pip compile --python-version 3.12 --generate-hashes \
  sis_secondaire/requirements/base.txt sis_superieur/requirements/base.txt \
  -o requirements.lock
```

Reconstruire et exécuter les tests des deux variantes. Les tests vérifient que
le runtime verrouillé correspond aux deux manifests. Le module tiers
`django-mfa2`, non utilisé par les parcours SIS, a été retiré ; le MFA TOTP SIS
reste dans `sis_common.mfa`. Aucun effacement de ses anciennes tables n'est effectué.

Pour le frontend, utiliser Node 22 avec npm 10 et `npm ci --legacy-peer-deps`.
AJV 8 est déclaré explicitement pour la compilation Webpack. Les overrides
Axios et brace-expansion corrigent des versions transitives anciennes sans
changer leur version majeure ; ils doivent rester couverts par la recette.
Le serveur de développement Webpack est remplacé par la version 5.2.6 et son
middleware 7.4.6 via des overrides ciblés. Leur démarrage et leur compilation
ont été contrôlés ; le serveur émet `Cross-Origin-Resource-Policy: same-origin`.
Ne pas retirer cet en-tête ni exposer le serveur de développement publiquement.
Les changements majeurs ESM/CommonJS des autres dépendances historiques ne
doivent pas être forcés globalement pour faire disparaître les alertes d'audit.

## Livraison et réserves avant production

La CI contrôle les fichiers modifiés avec des erreurs bloquantes, les suites
backend/frontend, les builds, les dépendances et les installations jetables.
Le lint de l'ensemble du frontend historique n'est pas encore propre :
le contrôle incrémental ne signifie pas que cette dette a disparu.
Des avertissements de typage OpenAPI subsistent ; les erreurs de génération du
schéma et la dérive des migrations, elles, doivent bloquer la recette.

Le scan Python verrouillé ne comporte actuellement aucune alerte connue.
Le frontend conserve des alertes amont non critiques, dont certaines de niveau
élevé, dans l'écosystème Open edX et les outils de construction. Le gate npm
bloque les critiques mais affiche les autres : il ne certifie pas une absence
de vulnérabilités. Réévaluer ces alertes avant toute exposition publique.

Une livraison publique doit identifier un commit revu, une version, les images
exactes et la procédure de retour arrière. Aucun tag, envoi d'image ou déploiement
public n'est effectué par les scripts de recette. Une archive pilote locale
contenant des modifications non commitées n'est pas une release homologuée.

Après création d'un tag approuvé, remplacer `sis-vX.Y.Z` ci-dessous par ce tag,
puis exécuter depuis la racine du dépôt :

```sh
git archive --format=tar.gz --prefix=LMS_SIS/ \
  --output=../sis-vX.Y.Z.tar.gz sis-vX.Y.Z sis_apps LICENSE
sha256sum ../sis-vX.Y.Z.tar.gz > ../sis-vX.Y.Z.tar.gz.sha256
```

Cette archive distribue les sources SIS, pas les images ni Open edX. Conserver
avec elle les identifiants des images qualifiées et les résultats de recette.
Ne jamais y ajouter `.env`, des fichiers d'établissement ou des sauvegardes.
Une version Tutor/Open edX
compatible avec ce fork reste à qualifier ; ne prenez pas arbitrairement la
dernière version de Tutor.

L'ouverture en production reste conditionnée à un serveur et des domaines
autorisés, au SSO et SMTP réels, aux alertes opérationnelles, aux sauvegardes
hors machine, à la validation des règles pédagogiques et à la recette de
l'établissement. Signaler les problèmes via le support configuré ou les issues
du dépôt, sans joindre de données d'élèves, de mots de passe, de `.env` ni de
documents confidentiels.
