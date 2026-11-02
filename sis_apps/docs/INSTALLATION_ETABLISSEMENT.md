# Installer le SIS d'un établissement

## Périmètre et limites

Cette distribution Compose installe les SIS, leur interface, PostgreSQL, Redis,
les workers, le planificateur et le proxy HTTPS. Elle **n'installe pas Open edX** :
le LMS et Studio doivent déjà fonctionner et être administrés séparément.
La compatibilité d'une version Tutor avec ce fork doit être qualifiée avant
d'en faire une distribution complète LMS + SIS.

Les variantes sont `secondaire`, `superieur` et `dual`. En mode dual, chaque SIS
possède sa base, ses fichiers et ses sessions. Un compte administrateur dans un
SIS ne donne pas automatiquement accès à l'autre.

Ne considérez pas une installation locale comme une homologation de production :
SMTP/SMS, SSO réel, règles pédagogiques, sauvegarde hors machine, capacité,
protection des données et recette par les utilisateurs restent à valider sur
l'infrastructure de l'établissement.

## Préparer le serveur

- Linux avec Docker Engine, le plugin Docker Compose et Python 3.
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
- Un client OAuth confidentiel SIS dans Open edX, son secret, l'audience, l'issuer
  exact et le **JWKS public** RSA/RS512. Ne copiez jamais la clé privée du LMS.

Depuis la racine du dépôt :

```sh
cd sis_apps
python3 scripts/sisctl.py configure \
  --mode secondaire \
  --domain ecole.example \
  --lms-url https://lms.ecole.example \
  --cms-url https://studio.ecole.example \
  --oauth-client-id sis-integration \
  --audience openedx \
  --jwks /chemin/protege/lms-public-jwks.json
```

L'issuer par défaut est `LMS_URL/oauth2` ; utilisez `--issuer` s'il diffère.
Le secret OAuth est demandé sans affichage. Les autres secrets sont générés
aléatoirement dans `.env`, avec des permissions `0600`. Une configuration
existante n'est jamais écrasée.
Utilisez le secret généré par Open edX, sur une seule ligne, sans apostrophe
ni `$` initial ; l'installateur refuse ces formes plutôt que de produire une
valeur interprétée différemment par les lecteurs de `.env`.

Pour un test sur cette machine uniquement, ajoutez `--local`, utilisez un domaine
comme `ecole.localhost`, et des URL locales adaptées. Ce mode active DEBUG et HTTP
sur `127.0.0.1:8080` : **ne l'exposez pas à un réseau public**.

### Choisir la connexion

Par défaut, l'interface utilise l'authentification Open edX (`SIS_AUTH_MODE=lms`).
Ajoutez `--auth-mode local` lors de la configuration pour utiliser les comptes SIS
locaux avec session HTTP-only, CSRF et MFA. Ce choix n'active aucune donnée fictive
et ne désactive pas les permissions des API.

Le MFA SIS local ne protège pas une connexion fédérée : celle-ci doit être
protégée par le LMS ou son fournisseur d'identité. Les utilisateurs importés
reçoivent un mot de passe inutilisable ; ils doivent utiliser la récupération
par email ou être associés explicitement à une identité Open edX.

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

```sh
python3 scripts/sisctl.py init \
  --variant secondaire \
  --institution /chemin/protege/institution-secondaire.json
python3 scripts/sisctl.py start
python3 scripts/sisctl.py status
python3 scripts/sisctl.py check
```

L'initialisation applique les migrations versionnées, crée le schéma et le
domaine, crée l'administrateur et collecte les fichiers statiques. Elle peut être
relancée : elle ne réinitialise pas un mot de passe existant et refuse de
réattribuer un domaine ou une identité déjà associés à un autre établissement.

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

### Comptes et responsabilités

L'administrateur initial est un compte de secours privilégié, pas un compte
partagé de travail quotidien. Créez des comptes nominatifs et attribuez les
groupes/permissions métier depuis l'administration Django du tenant.
`is_staff` autorise l'administration Django ; ce n'est pas un rôle métier.
Testez avec les utilisateurs concernés les droits direction/scolarité,
enseignant, apprenant et famille avant l'ouverture.

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
conservez `FIELD_ENCRYPTION_KEY`. Ne démarrez pas les applications et n'exécutez
pas `init` avant la restauration, car leurs bases doivent être vierges.

```sh
python3 scripts/sis_backup.py \
  --repository /sauvegardes/chiffrees/sis \
  --password-file /chemin/protege/restic-password \
  --env-file /chemin/protege/restauration.env \
  restore --snapshot ID_SNAPSHOT --confirm-empty-target
python3 scripts/sisctl.py --env-file /chemin/protege/restauration.env start
```

Si les domaines changent, ajoutez les nouveaux domaines aux tenants avant le
contrôle de santé ; `init` peut être utilisé **après** restauration avec les
mêmes identités et les nouveaux domaines. Vérifiez comptes, dossiers,
documents privés et files de tâches avant toute bascule DNS.

## Diagnostic et qualification

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
   les applications pendant la mise à jour. Conserver les anciennes images.
3. Installer la révision approuvée, conserver `.env` et ses clés, puis relancer
   `init` pour chaque variante avec le même fichier établissement : les migrations
   partagées et locataires sont appliquées, sans remplacer les mots de passe.
4. Lancer `start`, puis `check`, contrôler les parcours et reprendre le service.

Après une migration incompatible, **ne redémarrez pas simplement l'ancien code
sur la nouvelle base**. Restaurer le snapshot complet dans un projet isolé avec
la version précédente, vérifier les données puis basculer le routage. Documenter
les écritures effectuées depuis le snapshot avant de décider du retour arrière.

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
