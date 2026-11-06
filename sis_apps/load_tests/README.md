# SIS: qualification de 500 sessions HTTP authentifiées

Ce répertoire réutilise le lanceur HTTP **stdlib Python**, sans Locust, paquet
supplémentaire ni modification de l'application. Python 3.11+ est nécessaire.

**Aucune qualification de capacité n'est acquise par la présence du script ou
ses tests unitaires. Ne pas lancer la charge avant provisionnement de la cible
isolée et validation de la capacité de l'hôte.**

## Sécurité et limites de la preuve

- La cible est l'origine **API d'un SIS**, secondaire ou supérieur, pas le
  frontend, le LMS ou un point de terminaison SSO.
- `sis.validation.localhost` et les ports `58623`, `59080`, `59082` sont refusés,
  même avec un alias de nom d'hôte. Le port `55285` n'est pas une autorisation :
  une fixture arrêtée doit être provisionnée et vérifiée avant tout lancement.
- L'origine doit être déclarée à l'identique dans le seed et dans
  `--acknowledge-isolated-target`. Les déclarations `isolated: true` et
  `synthetic: true` sont obligatoires. Cette attestation ne prouve pas l'isolation :
  vérifier DNS/proxy, base, caches, stockage, tâches et intégrations sortantes.
  Ne jamais pointer un alias de test vers les services de l'utilisateur.
- HTTPS vérifié est obligatoire hors noms loopback/`.localhost`.
  Les redirections et les proxies implicites sont désactivés. Les scénarios ne
  peuvent envoyer que des chemins `/api/v1/` sur l'origine attestée.
- Chaque compte s'authentifie réellement par `/api/v1/auth/session/`, avec son
  propre cookie jar et son CSRF renouvelé après login. `/comptes/me/` vérifie
  identifiant, nom, rôle, établissement et activité. Un cookie de session
  `sessionid` unique est requis ; son empreinte seule distingue les sessions,
  sans compter les cookies auxiliaires. Un cookie de session partagé ou un
  compte réutilisé invalide la campagne.
- **500 sessions authentifiées concurrentes ≠ 500 navigateurs, 500 pages
  rendues ou 500 sockets TCP constamment ouvertes.** Le rapport distingue le
  pic de sessions et le pic de requêtes HTTP en vol. L'outil urllib ne simule
  pas le moteur de rendu, JavaScript, WebSocket ni le pooling d'un navigateur.
  Playwright doit qualifier séparément les formulaires, boutons et parcours UI.
- Les scénarios du seed sont la seule couverture revendiquée, pas l'intégralité
  du cahier fonctionnel. Pas de fallback simulé lorsqu'une API manque.
- Aucun corps de réponse, cookie, mot de passe ou nom d'utilisateur n'est
  journalisé. Les résultats utilisent les indices utilisateurs, les rôles et
  des noms d'étapes non sensibles. Le seed est un secret local, mode `0600`,
  à conserver hors Git et à supprimer après destruction de la fixture.

## Préparer une fixture réellement synthétique

Le parent/opérateur prépare la base ; le lanceur ne crée aucun compte et ne
modifie jamais les déploiements. `seed.example.json` est **volontairement
inexécutable** (isolation non attestée, mots de passe vides, IDs d'exemple).

Préparer exactement 500 comptes différents pour `--users 500`, avec les vrais
`user_id`, `tenant_id`, rôles et mots de passe de la fixture. Deux rôles au
minimum sont requis à 500 ; la distribution réelle apparaît dans les résultats
par utilisateur et par étape. Exemple de mélange à valider métier :
300 apprenants, 150 enseignants, 50 agents habilités. Les profils parents,
comptables, bibliothécaires, etc. nécessitent leurs propres étapes et fixtures ;
ne pas les assimiler artificiellement à des administrateurs.

Les comptes locaux synthétiques utilisés ici n'ont pas de MFA activé.
Ce n'est pas une qualification MFA/JWT/SSO et aucune protection de production
ne doit être désactivée pour ce test.

Pour les deux scénarios fournis, créer en amont :

1. **Enseignant / agent habilité :** une note continue modifiable distincte par
   utilisateur, rattachée à son affectation, avec apprenant, classe/formation,
   évaluation et période ouverte. L'API réelle
   `/api/v1/notes/notes/{id}/` lit puis modifie l'appréciation ; un GET immédiat
   et un GET final vérifient l'ID et le texte unique de l'itération.
2. **Apprenant :** sa propre réclamation synthétique, module `sis.complaints`
   actif, état autorisant les échanges. GET puis
   `/api/v1/core/reclamations/{uuid}/message/` avec sa version courante.
   Vérifier après écriture l'ID, la version retournée et le dernier message
   persisté (`historique.-1.message`). Les historiques et notifications
   générés sont de vraies écritures, pas des réponses inventées.

Le seed peut définir d'autres scénarios métier à partir des API existantes :

- `scenarios.<nom>.roles` : rôles autorisés explicitement ; `steps` : 1–12
  étapes. Chaque scénario a au moins une lecture positive ; une campagne a
  au moins une écriture vérifiée. Un rôle naturellement en lecture seule n'a
  pas besoin de permissions artificielles.
- Étape : `name` slug non sensible unique, `path`, `method` (`GET` par défaut,
  `POST`, `PATCH`, `PUT`), `status` exact (`200` par défaut), `json` éventuel,
  `equals` (chemin JSON pointé → valeur), `capture` (variable → chemin JSON).
- Variables `{{user_id}}`, `{{tenant_id}}`, `{{role}}`, `{{username}}`,
  `{{run_id}}`, `{{iteration}}` et `accounts[].variables`.
  Un placeholder occupant toute la valeur conserve son type numérique.
  Les captures ne peuvent pas remplacer l'identité ni les variables de fixture.
  `equals` ne fait aucune conversion implicite : un Decimal sérialisé par
  Django est souvent une chaîne (`"12.00"`), pas un nombre.
- Chaque écriture a un `verify: {path, equals}` : GET du même enregistrement,
  assertion de `id` et d'au moins un champ persisté. Les ressources d'écriture
  sont déclarées dans `owned_resources`, avec un ID numérique ou UUID ;
  elles ne peuvent pas être partagées entre utilisateurs. Les actions sont
  possibles sous ce chemin de détail. Pas de création sur une collection, de
  suppression de données ou de callback vers un autre service dans ce runner.
- Un refus attendu est une étape **GET** distincte avec
  `"negative": true, "status": 403` (ou `404` selon le contrat réel).
  Un 200 inattendu sur cette étape échoue. Les 401, 429, 5xx et tous les
  autres statuts inattendus sont des erreurs, jamais ignorées ni retentées.
  N'ajouter un cas négatif qu'après vérification du contrat d'autorisation.

Conserver les protections/throttles de la cible choisie. Un 429 mesure une
limite réelle de cette configuration ; il ne valide pas 500 utilisateurs.
Ne pas désactiver les limites en cours de campagne ni ralentir implicitement
la charge pour transformer un échec en succès. Documenter toute configuration
de qualification différente de celle d'exploitation.

## Validation sans réseau, puis lancement autorisé

Depuis la racine `LMS_SIS` :

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest sis_apps.load_tests.test_sessions -v

# Fichiers préparés par l'opérateur, sous le projet et hors Git.
chmod 600 qualification/seed-500.json
python3 sis_apps/load_tests/run.py sessions \
  --target https://isolated-sis.example.invalid \
  --acknowledge-isolated-target https://isolated-sis.example.invalid \
  --seed qualification/seed-500.json --users 500 \
  --output qualification/seed-validation.json --validate-only
```

Le domaine `.invalid` doit être remplacé par la vraie origine isolée **dans
les deux options et le seed**. `--validate-only` ne contacte aucun service et
ne génère aucune session ; son rapport ne contient jamais `passed: true`
comme résultat de charge. Le dossier de sortie doit déjà exister et le fichier
de sortie être nouveau : impossible d'écraser le seed ou des preuves antérieures.

**Exemple réservé à l'exécution ultérieure autorisée**, après validation des
ressources ; ne pas l'exécuter sur l'environnement utilisateur :

```bash
python3 sis_apps/load_tests/run.py sessions \
  --target https://isolated-sis.example.invalid \
  --acknowledge-isolated-target https://isolated-sis.example.invalid \
  --seed qualification/seed-500.json \
  --users 500 --ramp-seconds 120 --duration-seconds 120 \
  --startup-timeout-seconds 120 --cleanup-timeout-seconds 30 \
  --think-seconds 2 --timeout 5 --max-p95-ms 2000 \
  --output qualification/sessions-500.json
```

Le ramp lance les **500 authentifications distinctes**. Aucun scénario métier
ne démarre avant que tout le groupe soit authentifié. Un échec de login annule
le départ groupé et déconnecte les comptes déjà connectés. La durée de 120 s
est le plateau après authentification complète, pas la rampe. Les étapes
s'exécutent en boucle avec un temps de réflexion fixe entre cycles. Aucun
rééchantillonnage de comptes, retry silencieux ou réduction de concurrence.

Les bornes CLI : 1–500 utilisateurs, rampe 0–7200 s (minimum 30 s à 500),
plateau 1–900 s, délai d'authentification après rampe 1–180 s, nettoyage 1–120 s,
timeout réseau 0,1–30 s, réflexion 0,1–30 s. À la fin du plateau, un couple
écriture/relecture en cours peut terminer pendant au plus deux timeouts ;
les nouvelles étapes cessent. Un contrôle final relit chaque dernière
écriture tentée, puis déconnexion et vérification de déconnexion.
Le timeout urllib borne les opérations réseau, pas un adversaire envoyant
lentement un flux infini : prévoir aussi une limite murale externe.

La limite de rampe de deux heures permet de conserver la politique réelle
d'authentification sans exiger 500 logins simultanés. Mesurer les requêtes
effectivement soumises au throttle anonyme dans un smoke test avant de choisir
la rampe. À un login anonyme par utilisateur et 10/minute par source, une
rampe explicite de 3600 s espace les comptes d'environ 7,21 s (8–9/minute).
Ce calcul ne remplace pas la mesure des endpoints CSRF, login et logout.
Le temps de préparation n'est jamais inclus dans les 120 s de plateau.
Avec trois requêtes métier par cycle et un plafond utilisateur de 100/minute,
une réflexion explicite de 3 s laisse une marge pour l'authentification,
l'intégrité et le nettoyage ; toute modification doit figurer dans le rapport.
Adapter également le timeout mural externe (par exemple 4000 s pour cette
rampe), sans modifier les seuils de réussite après observation des résultats.

### Ressources de l'hôte

500 workers = jusqu'à 500 threads HTTP ; pas 500 processus de navigateur.
Les corps de réponse sont bornés à 2 MiB. Les latences sont agrégées en
histogrammes de millisecondes, pas conservées requête par requête.
L'hôte partagé observé dispose d'environ 14 GiB de RAM, 6,8 GiB disponibles
mais presque 4 GiB de swap occupés : **cela ne suffit pas à autoriser une
charge de 500** à côté du SIS/LMS utilisateur et d'autres bases.

Préférer une machine de qualification séparée. Si une exécution partagée est
autorisée après mesure, limiter **le générateur et la fixture séparément**,
surveiller CPU/RAM/swap, connexions PostgreSQL, Redis et files Celery.
Exemple de plafond optionnel du générateur Linux/systemd (délégation cgroup
nécessaire, à vérifier par l'opérateur), préfixant la commande précédente :

```bash
systemd-run --user --scope \
  -p MemoryHigh=1G -p MemoryMax=2G -p CPUQuota=150% -p TasksMax=600 \
  timeout --signal=TERM --kill-after=10s 420s \
  python3 sis_apps/load_tests/run.py sessions ...options-explicites-ci-dessus...
```

Ces limites sont des plafonds, pas une promesse de faisabilité. Un OOM, une
limite de threads, un timeout global ou un rapport incomplet invalide le test.
Ne jamais appeler une campagne à 20/50/100 utilisateurs une preuve de 500.
Un smoke test à petite échelle exige son propre seed et son propre rapport.

### Ingress TLS de la fixture jetable

`fixture-nginx.conf` est réservé à `sis-load-d0c25c75`, à l'origine
`https://load-secondaire.localhost:60031`. Il reprend les en-têtes de sécurité
du Nginx frontend, mais sert uniquement de proxy TLS asynchrone :

- Nginx `1.27-alpine`, un worker, 2048 connexions, 0,5 CPU / 128 MiB ;
- certificat/CA existants vérifiés, TLS 1.2/1.3, aucun listener HTTP ;
- publication **127.0.0.1:60031 → proxy:8443** uniquement ;
- API HTTP privée, Gunicorn `gthread`, **4 workers × 8 threads**, 4 CPU / 2 GiB ;
- PostgreSQL 2 CPU / 1 GiB, `max_connections=64` pour les 32 threads et la
  maintenance ; `shared_buffers=96MB`, `work_mem=2MB` inchangés ;
- Redis 0,25 CPU / 128 MiB, aucune éviction ni modification des throttles ;
- générateur 1 CPU / 1 GiB, swap interdit, 600 tâches au maximum.

Les plafonds fixture passent donc de 1,625 à **3,25 GiB**, hors générateur :
c'est une nouvelle architecture matérielle de qualification, pas une amélioration
mesurée à matériel constant. Ne pas utiliser les résultats de deux workers
synchrones HTTPS directs comme qualification de cette architecture.

L'API est uniquement sur le réseau interne dédié. Le proxy utilise
`172.24.0.10` sur ce réseau et seul lui rejoint le bridge d'ingress dédié.
Activer `TRUST_PROXY=true` dans **cette fixture** et utiliser
`--forwarded-allow-ips 172.24.0.10` côté Gunicorn. Nginx impose l'hôte canonique,
écrase `X-Forwarded-Proto`, `X-Forwarded-For` et `X-Real-IP`, supprime `Forwarded`
et `X-Forwarded-Host` ; aucune adresse fournie par le client n'est ajoutée.
Les répertoires PID/logs/buffers `/runtime` doivent être accessibles à l'UID
non privilégié ; racine et configurations montées en lecture seule.
Ne pas réexécuter le provisionnement initial en redémarrant une base déjà seedée.

`cleanup_fixture_sessions.py` est une opération **ponctuelle explicitement
autorisée**, pas un nettoyage automatique du runner. Elle exige le seed privé,
le rapport rouge, le postmortem conservé et
`--acknowledge-delete-218-synthetic-sessions`. Elle refuse tout écart avec les
218 propriétaires identifiés, revérifie leurs identités en base, verrouille
les lignes et ne supprime que leurs sessions dans une transaction. Sauvegarder
la base synthétique auparavant ; conserver les rapports d'origine.

Diagnostic court, à exécuter seulement après autorisation et contrôle mémoire :

```bash
systemd-run --user --scope --quiet \
  -p MemoryMax=1G -p MemorySwapMax=0 -p CPUQuota=100% -p TasksMax=600 \
  timeout --signal=INT --kill-after=10s 45s \
  python3 sis_apps/load_tests/tls_probe.py \
  --target https://load-secondaire.localhost:60031 \
  --acknowledge-isolated-target https://load-secondaire.localhost:60031 \
  --seed qualification/seed-500.json --ca-file qualification/tls/ca.crt \
  --connections 500 --timeout 5 --max-p95-ms 2000 \
  --output qualification/tls-500.json
```

Le diagnostic ouvre simultanément 500 connexions vers la publication IPv4
explicite, vérifie CA/SNI, puis conserve les sockets jusqu'au résultat du groupe.
Il n'envoie **aucune requête HTTP**, n'authentifie personne et ne qualifie ni
l'API ni l'UI. Les erreurs et le p95 dépassé restent des échecs. Conserver toute
tentative échouée sous son propre nom ; ne jamais écraser un rapport.
Un smoke distinct avec de vrais comptes et écritures/relectures doit ensuite
réussir. Une nouvelle campagne 500 exige une autorisation distincte, de nouveaux
fichiers de résultat et une capture préalable des empreintes/limites.

### Diagnostic court du générateur

`transport_diagnostic.py` est limité à **32 clients × 4 GET CSRF**, sans login,
écriture métier ni passage à 500. Il utilise les vrais `Client`, cookie jars et
contextes urllib, vérifie la même CA via `SSL_CERT_FILE`/`--ca-file`, et distingue
construction du client/contexte, connexion DNS/TCP/TLS, attente des en-têtes,
temps CPU du thread et départ du groupe. Les timers ajoutent une instrumentation :
ne pas présenter ce diagnostic comme une campagne métier.

Le Nginx de fixture expose un identifiant opaque `X-SIS-Load-Request-ID` et
journalise les temps upstream/connect/header avec ce même identifiant. Cela
permet des comparaisons **requête par requête** ; soustraire deux p95 indépendants
ne mesure pas une file d'attente. Les requêtes annulées (`499` au proxy) sont
censurées, pas des réponses applicatives réussies reçues par le client.

Les versions observées Python **3.14.4 et 3.12.16** construisent déjà un contexte
vérifié par opener/utilisateur, réutilisé entre requêtes. Il n'y a donc pas de
correction « contexte recréé par requête » démontrée pour ces campagnes.
En revanche urllib impose `Connection: close` : chaque requête refait TCP/TLS.
Ce coût réel, le quota CPU du générateur et l'attente upstream doivent être
mesurés séparément ; ils ne suffisent pas à établir un défaut applicatif.
Les cookies et contextes ne sont jamais partagés entre utilisateurs.

```bash
SSL_CERT_FILE="$PWD/qualification/tls/ca.crt" \
systemd-run --user --scope --quiet \
  -p MemoryMax=1G -p MemorySwapMax=0 -p CPUQuota=100% -p TasksMax=600 \
  env SSL_CERT_FILE="$PWD/qualification/tls/ca.crt" \
  timeout --signal=INT --kill-after=10s 60s \
  python3 sis_apps/load_tests/transport_diagnostic.py \
  --target https://load-secondaire.localhost:60031 \
  --acknowledge-isolated-target https://load-secondaire.localhost:60031 \
  --seed qualification/seed-500.json --ca-file qualification/tls/ca.crt \
  --clients 32 --requests-per-client 4 --timeout 5 --max-p95-ms 2000 \
  --output qualification/transport-1cpu.json
```

Toute comparaison autorisée à 2 CPU garde les mêmes requêtes, timeout, CA, seuil
et plafonds serveur, et produit un autre fichier. Elle ne requalifie jamais 500.
Un petit smoke authentifié distinct doit conserver les vrais throttles,
écritures/relectures et vérifications de logout.

## Lire le résultat

Code retour : `0` campagne réussie (ou validation hors ligne explicitement
identifiée), `1` qualification échouée, `2` configuration refusée.

Le JSON contient les seuils/configuration, cible et ID d'environnement, ID de
campagne, durée, nombre total/pic de sessions authentifiées, durée réelle du
groupe complet, pic des requêtes en vol, cycles terminés par utilisateur,
requêtes/s, statuts, erreurs, refus négatifs attendus et latences moyenne,
p50/p95/p99/max, globalement et par rôle/étape/phase. Les quantiles sont
arrondis vers le haut à la milliseconde.

Le schéma de rapport **v2** distingue `checks_failed` (une assertion sur un
état confirmé échoue) et `checks_indeterminate` (transport, réponse illisible
ou écriture sans réponse confirmée). Une écriture en timeout n'est jamais
présumée validée : son état attendu ne permet pas d'affirmer une corruption.
Les deux catégories empêchent la qualification. Les sous-types de transport
et l'étape HTTP sont désormais conservés sans texte d'exception ni secret ;
les anciens rapports v1 restent inchangés et ne permettent pas de reconstruire
rétroactivement TCP/TLS/attente d'en-têtes.

Pour une écriture dont le reçu a expiré, la relecture finale vérifie toujours
l'ID de la ressource et compare maintenant **tous** les champs attendus.
`data_integrity.unconfirmed_matches` compte les relectures correspondant aux
champs demandés ; `unconfirmed_differs` compte celles qui ne correspondent pas.
Une différence ne prouve pas une corruption : l'écriture a pu ne jamais être
appliquée. Une relecture indisponible ne figure dans aucun des deux compteurs.
Ces observations restent dans `checks_indeterminate` et ne rendent jamais le
passage vert : le reçu HTTP initial reste manquant. Les 262 écritures incertaines
du précédent 500 ne sont **pas** reclassées rétroactivement par ces compteurs.
Un nouveau résultat exige une campagne isolée distinctement autorisée, une
fixture et des preuves neuves ; la validation hors ligne ne démontre aucune
capacité serveur.

Les utilisateurs sortis prématurément d'un scénario attendent la fin des
requêtes métier de tous les autres avant les vérifications finales et logout.
Cela sépare la mesure métier du trafic de diagnostic ; le départ prématuré
reste un échec, et ne compte pas comme un plateau complet de 500 utilisateurs.
Cette barrière ne réduit ni les 500 utilisateurs ni la concurrence des contrôles
finaux, et n'allonge aucun timeout ou budget de latence.

`passed` exige :

1. tous les utilisateurs réellement authentifiés et maintenus sur le plateau ;
2. au moins un cycle métier complet par utilisateur ;
3. **zéro erreur inattendue**, y compris authentification, autorisation,
   throttling, JSON invalide, assertion, réseau et nettoyage ;
4. relectures finales cohérentes et déconnexion effective de chaque session ;
5. p95 HTTP du plateau inférieur au budget demandé.

La déconnexion est prouvée par `DELETE /api/v1/auth/session/`, puis par le
**401 explicitement attendu** de `/api/v1/utilisateurs/comptes/me/`. Un 200 à
cette dernière étape échoue. Cette vérification d'accès refusé s'exécute avant
le throttle dans DRF et évite de consommer 500 accès anonymes à un endpoint
public lors du nettoyage ; elle ne désactive ni ne contourne une protection.
Le smoke initial doit mesurer cette distinction : le GET public
`auth/session/` consomme, lui, le quota anonyme. Les GET CSRF sont des vues
Django distinctes, à vérifier sur la cible réelle.

L'intégrité vérifiée est celle des identités et des champs explicitement
assertés des ressources possédées ; ce n'est pas un audit de toute la base,
des totaux financiers ou des tâches asynchrones. Une comparaison indépendante
avant/après de la base et des files reste nécessaire selon les scénarios.
Les modifications synthétiques restent présentes pour cette comparaison ;
restaurer/détruire ensuite la fixture, sans nettoyage destructif automatique.

## Anciens tests d'endpoint

`run.py exam-list` et `run.py grade-webhook` restent disponibles, maintenant
soumis aux mêmes `--seed` et `--acknowledge-isolated-target`. Le seed peut ne
contenir que `environment` pour ces modes ; le jeton/secret synthétique reste
fourni par `SIS_LOAD_BEARER_TOKEN` / `SIS_LOAD_WEBHOOK_SECRET`. Les commandes
anciennes sans attestation sont donc volontairement refusées.
Ces modes réutilisent un secret/jeton, ne vérifient pas l'intégrité métier,
et ne prouvent **jamais** 500 utilisateurs authentifiés distincts.

## Provisionnement jetable explicitement autorisé

Les scripts `prepare_fixture.py`, `provision_fixture.py`, `observe_fixture.py`
et `diagnose_fixture.py`
sont réservés à la fixture nommée `sis-load-d0c25c75`. Le premier génère des
secrets neufs, une CA privée et un certificat HTTPS pour
`load-secondaire.localhost`, sans démarrer de service. L'opérateur démarre
uniquement ses nouveaux conteneurs sur son réseau Docker interne dédié, avec
le code `sis_apps` courant monté en lecture seule ; aucune donnée existante,
aucun réseau LMS/SIS utilisateur, aucun worker ni beat n'est réutilisé.
Si Docker ne publie pas les ports d'un réseau interne, ajouter uniquement
un second bridge neuf préfixé `sis-load-d0c25c75-`, réservé à l'API, avec
masquerading et communication inter-conteneurs désactivés ; publier HTTPS
sur `127.0.0.1` seulement. PostgreSQL et Redis restent exclusivement sur
le réseau interne, sans aucun port publié. Ne pas raccorder un réseau existant.

Le provisionneur refuse tout autre nom de base/hôte/contexte et tout tenant
déjà présent. Il utilise les vraies migrations, le validateur de mots de
passe et Argon2, avec `DEBUG=false` et les throttles d'origine. Il crée
300 élèves et inscriptions validées, 150 enseignants et affectations,
50 agents de direction, 200 notes distinctes et 300 réclamations privées.
Le compte anonyme système de Guardian reste intact et **n'est pas** l'un
des 500 comptes du seed. Les seeds de 500 utilisateurs et de smoke à deux
utilisateurs sont privés (`0600`).

L'observateur lit uniquement cette base et son cache pour enregistrer les
comptes synthétiques, inscriptions, écritures persistées, sessions restantes
et compteurs réels des throttles. Il ne révèle aucun secret. Ses observations
avant/après complètent les assertions HTTP, sans prétendre auditer tous les
modules ou transactions métier. Les fichiers de sortie doivent être nouveaux.

`diagnose_fixture.py` confronte un rapport terminé et son seed aux enregistrements
possédés, versions/historiques, dernières itérations persistées et sessions
restantes dans une transaction PostgreSQL **READ ONLY / REPEATABLE READ**.
Il ne répare ni ne supprime rien, et ne transforme jamais une campagne échouée
en succès. Les erreurs de délai et de déconnexion restent des échecs même
si les écritures confirmées se révèlent cohérentes après coup.
