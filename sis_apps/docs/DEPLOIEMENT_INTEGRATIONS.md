# Déploiement des intégrations LMS/SIS

## Raccordement explicite et diagnostic du contrat

L'authentification locale du SIS fonctionne **sans LMS actif** et ne constitue
pas une connexion Open edX. Les quatre paramètres `EDX_LMS_URL`,
`EDX_CMS_URL`, `EDX_OAUTH_CLIENT_ID`, `EDX_OAUTH_CLIENT_SECRET` doivent être
fournis par l'exploitant autorisé. Aucun secret n'est affiché dans le diagnostic.

Le provisioning n'utilise **pas** un hypothétique `POST` natif sur
`/api/user/v1/accounts`. Il requiert l'extension livrée dans
`sis_apps/deploy/openedx/sis-provisioning`, installée et migrée dans LMS et
Studio. Son contrat est `/api/sis/v1/` :

| Opération | Contrat et protection |
|---|---|
| Identité | `POST accounts/<username>/`, puis `PATCH` avec l'identifiant LMS existant ; identité opaque stable, propriété du compte de service, aucun mot de passe ni privilège global transmis. |
| Cours | `POST/PATCH courses/<course_key>/` côté Studio ; identifiant stable SIS/SIS-U, cours géré explicitement, version de demande préservée au rejeu. |
| Inscription/retrait | `POST courses/<course_key>/enrollments/<username>/` ; décision booléenne et `requested_at` identique au rejeu. |
| Enseignant | Même contrat via `teaching/<username>/` ; droits limités au cours, jamais `is_staff` global. |
| Publication | Révision Studio examinée + confirmation humaine + UUID d'opération ; aucune publication implicite en créant un cours. |
| Diagnostic | `GET capabilities/` authentifié dans LMS et Studio : contrat `sis-provisioning/v1` et permissions réellement détenues par ce service. |

Le diagnostic SIS `GET /api/v1/integration/health/` retourne explicitement
`configured=false`, `available=false` et les **noms** des paramètres manquants
sans appeler le LMS incomplet. Si configuré, un heartbeat ne suffit pas :
les capacités comptes/inscriptions/enseignants côté LMS et cours/publication
côté Studio doivent être confirmées. Une extension ancienne sans endpoint
`capabilities/`, un refus, une redirection, une réponse incompatible ou une
panne restent indisponibles. L'opérateur doit mettre à jour l'extension
dans une intervention autorisée ; le SIS ne crée ni compte staff ni permission
pour faire passer le diagnostic.

`available=true` n'est pas une preuve de cours publié, de livraison webhook,
de SSO, de visioconférence ou d'un autre standard pédagogique. Le champ
`webhook_status` reste `unverified` ; chaque fournisseur non configuré reste
indisponible. La page d'intégration affiche cette distinction.

## Reprise après coupure et reçus tardifs

Les demandes utilisateur et cours sont maintenant enregistrées dans
l'outbox **avant** l'appel distant, comme les intentions d'accès. Un arrêt
du worker après l'écriture distante mais avant sa confirmation locale laisse
la même demande récupérable. Après dix minutes, le publisher récupère les
réservations interrompues ; il conserve identité, version et paramètres.
Les erreurs réseau, HTTP 408/429/5xx et configuration manquante restent en
attente avec backoff (maximum 320 secondes), même au-delà de cinq essais.
Les conflits de droits/validation sont conservés en `dead`, sans contournement.
Un worker tardif ne peut pas écraser le résultat d'une réservation plus récente.

La commande « Demander le traitement » ne fait que mettre en file le
publisher du tenant courant : elle ne transforme pas un événement en succès.
Après correction d'un conflit permanent, soumettre une **nouvelle décision
explicite**, conserver l'ancien événement et vérifier le reçu. Ne pas supprimer
les marqueurs de propriété ni remettre arbitrairement un événement `dead` en
attente.

Les webhooks d'identité ne créent plus d'association par égalité avec le
username local ; seule une association LMS existante peut être confirmée, sans
changer son identifiant distant ni réactiver un compte révoqué. Une publication
distante ne réactive pas un mapping de cours. Une inscription tardive ne peut
pas annuler une décision de retrait ou une suspension scolaire. Le publisher
recherche aussi les apprenants sortants/suspendus et les inscriptions annuelles
non validées, puis recontrôle la situation avant d'émettre un retrait. Une
reprise de scolarité exige un nouvel octroi explicite ; elle ne restaure pas
automatiquement les droits.

## Qualification nécessitant un vrai LMS autorisé

Les tests HTTP simulés et les tests PostgreSQL ne clôturent pas F06–F09/N2.
Sur un environnement dédié, avec URL et compte de service autorisés, vérifier :

1. Installation/migrations de l'extension sur la version Tutor/Open edX visée,
   JWT non restreint, permissions minimales, endpoints LMS et Studio ; refus
   pour utilisateur ordinaire et service propriétaire différent.
2. Création et mise à jour d'une identité synthétique, cours stable,
   inscription et rôle enseignant sur **ce seul cours** ; aucun staff global.
3. Consultation/édition dans Studio, révision examinée, publication, accès
   apprenant et remise réelle. Les contenus/quiz/visio/SCORM/xAPI/LTI ne sont pas
   qualifiés par le seul test de provisioning.
4. Réponse HTTP perdue et coupure du worker, puis reprise outbox sans compte,
   cours ou inscription supplémentaire ; suspension/retrait effectivement
   visibles dans le LMS et refus d'un webhook tardif.
5. Signal de note détaillée signé (configuration ci-dessous), mapping
   sous-section → évaluation, proposition unique en rejeu, validation humaine ;
   ni note corrigée ni période close écrasée par une réception tardive.
6. Livraison webhook avec panne du destinataire/broker, navigateur par rôle,
   TLS/domaines, stockage, sauvegarde/restauration dans un projet distinct.

Aucun de ces appels mutateurs réels, déploiement, redémarrage, restauration ou
test navigateur LMS n'a été exécuté dans la passe du 9 novembre 2026.

## BigBlueButton

Configurer côté LMS les variables `BIG_BLUE_BUTTON_GLOBAL_URL`,
`BIG_BLUE_BUTTON_GLOBAL_KEY` et `BIG_BLUE_BUTTON_GLOBAL_SECRET`. Ne jamais
enregistrer ces secrets dans un établissement SIS ni les transmettre au
navigateur.

Dans le cours Open edX :

1. activer l'application avancée `big_blue_button` ;
2. autoriser le partage du nom d'utilisateur LTI ;
3. depuis le panel SIS, activer les classes virtuelles, sélectionner
   `bigbluebutton`, puis lancer la synchronisation du cours mappé ;
4. vérifier la création et l'accès à une réunion avec un compte enseignant et
   un compte apprenant.

Les enregistrements et leur durée de conservation doivent être configurés sur
le serveur BigBlueButton selon la politique de l'établissement.

## Reprise d'un provisionnement de cours Studio

Le service de provisionnement doit conserver sa permission
`sis_provisioning.provision_courses`, l'autorisation de créer des cours dans
l'organisation et les droits d'auteur sur le cours concerné. Ces droits sont
distincts des permissions du compte dans le SIS.

Après une interruption de création, rejouer la même requête sur
`/api/sis/v1/courses/<course_key>/` ne doit pas réattribuer des droits Studio
révoqués. Si le cours existe mais que son initialisation est inachevée, la
reprise vérifie de nouveau les droits d'auteur avant toute réinitialisation ;
leur absence entraîne un refus HTTP 403.

L'opérateur doit vérifier le compte de service, le cours et la décision
d'habilitation. Si la reprise est autorisée, il rétablit explicitement les
droits nécessaires dans Studio avant de rejouer la requête. Si la révocation
est intentionnelle, conserver le refus. Ne pas supprimer le cours, modifier
son marqueur de propriété ou forcer `ManagedCourse.initialized` pour contourner
ce contrôle. La liaison explicite d'un cours historique est un autre parcours,
pas un moyen de terminer cette initialisation.

## Notes détaillées Open edX

Activer le signal dans la configuration LMS :

```yaml
FEATURES:
  ENABLE_COURSE_ASSESSMENT_GRADE_CHANGE_SIGNAL: true
```

Déclarer les destinations dans les tokens LMS. Le secret doit correspondre au
secret webhook du tenant SIS :

```yaml
SIS_GRADE_WEBHOOK_TARGETS:
  - url: https://sis.example.org/api/v1/integration/webhook/lms/
    secret: valeur-fournie-par-le-gestionnaire-de-secrets
    course_ids:
      - course-v1:Organisation+Cours+Session
```

`course_ids` est facultatif. Sans ce champ, la destination reçoit tous les
cours. Hors mode debug, les URL non HTTPS sont ignorées. Redémarrer LMS et les
workers Celery après modification, puis contrôler les retries et la file
d'échec. Le mapping cours, utilisateur et sous-section vers évaluation doit
exister dans le tenant avant l'import.

## Copies écrites

Définir `PRIVATE_EXAM_STORAGE_ROOT` sur un volume non servi par le proxy web et
`EXAM_COPY_MAX_SIZE` selon la capacité retenue. Le téléchargement doit
exclusivement passer par l'API authentifiée ; aucune route `/media/` ne doit
exposer ce volume.

Sauvegarder et chiffrer ce volume séparément, limiter ses permissions au
processus SIS et tester régulièrement une restauration. Le contrôle antivirus
est requis avant une ouverture à des fichiers provenant directement
d'utilisateurs non fiables.

Le parcours d'exploitation est : candidat présent, dépôt PDF, affectation
anonyme d'un ou deux correcteurs, soumission de toutes les corrections,
modération, puis publication du résultat. Une note de modération différente de
la moyenne exige un motif.

## Tests de charge

Exécuter uniquement sur une plateforme de test isolée avec des données
synthétiques. Le script ne requiert aucune dépendance supplémentaire.

```bash
export SIS_LOAD_BEARER_TOKEN='jeton-de-test'
python sis_apps/load_tests/run.py exam-list \
  --url https://sis-test.example.org/api/v1/examens/convocations/ \
  --requests 10000 --concurrency 100 --max-p95-ms 2000

export SIS_LOAD_WEBHOOK_SECRET='secret-de-test'
python sis_apps/load_tests/run.py grade-webhook \
  --url https://sis-test.example.org/api/v1/integration/webhook/lms/ \
  --requests 1000 --concurrency 20 --max-p95-ms 1000
```

Une campagne échoue si le succès descend sous 99 % ou si le p95 dépasse le
seuil fourni. Surveiller simultanément PostgreSQL, Redis, les workers Celery,
la mémoire et la profondeur des files. Les 5 000 copies doivent utiliser des
PDF synthétiques sans données personnelles et être supprimées après le test.
