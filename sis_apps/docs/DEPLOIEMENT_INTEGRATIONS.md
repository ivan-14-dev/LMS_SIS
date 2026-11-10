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

### Réseau de transport et prérequis de publication

Sur un hôte multi-projets, ne pas raccorder les API SIS directement au réseau
interne complet de Tutor. Des alias génériques comme `redis` ou `api-secondaire`
peuvent alors désigner un service d'un autre projet. Prévoir un réseau de
transport séparé, partagé uniquement par la passerelle Open edX et les clients
SIS, avec les noms LMS/Studio comme alias de la passerelle. Les bases et brokers
restent sur leurs réseaux propres. Vérifier la résolution DNS depuis les API
et workers, pas seulement depuis l'hôte.

Pour les callbacks, raccorder aussi le worker LMS et la passerelle SIS à ce
réseau de transport, en conservant le réseau natif du worker pour son broker.
Ne pas y exposer Redis ou les bases. La chaîne TLS doit être vérifiable depuis
le worker ; une CA privée approuvée peut compléter son bundle via
`REQUESTS_CA_BUNDLE`. Ne pas remplacer cette confiance par `verify=False`.

Avant publication, le cours doit contenir au moins une unité Studio. Un refus
pour cours vide peut conserver l'UUID d'opération et sa révision, sans version
publiée. Après ajout de contenu, relire la révision et soumettre une **nouvelle
confirmation avec un nouvel UUID**. Ne pas supprimer l'ancienne intention,
réutiliser son UUID avec une autre révision ou retirer la garde sur les unités.

La création garde `catalog_visibility=none`. La publication ne décide pas à la
place de l'auteur des dates et de la visibilité : vérifier ces paramètres dans
Studio avant l'accès apprenant. Sur la version qualifiée, le MFE refuse aussi
les métadonnées d'un cours invisible à son apprenant inscrit. Le choix explicite
`about` rend ces métadonnées accessibles sans référencer le cours au catalogue ;
la politique de visibilité et d'inscription appartient à l'établissement.

Le [bilan SSO et notes du 10 novembre](RESTE_A_FAIRE_ET_VALIDATION.md#sso-et-notes-signées--qualification-du-10-novembre-2026)
décrit le parcours réel navigateur, activité notée, callbacks TLS signés,
reprise et approbation dans les deux variantes. Cette recette locale ne vaut
ni DNS/TLS de production ni réception institutionnelle.

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

Construire l'image avec le
[Dockerfile livré](INSTALLATION_ETABLISSEMENT.md#provisionner-les-comptes-sis-dans-open-edx)
et le contexte racine du dépôt. Installer le plugin Tutor
`deploy/tutor/tutor-sis-sso` **0.2.0 ou ultérieur**, puis activer `sis_sso`.
Dans le `config.yml` privé de la racine Tutor autorisée, déclarer les cibles :

```yaml
SIS_GRADE_WEBHOOK_TARGETS:
  - url: https://sis.example.org/api/v1/integration/webhook/lms/
    secret: VALEUR_A_REMPLACER_DANS_LA_CONFIGURATION_PRIVEE
    course_ids:
      - course-v1:Organisation+Cours+Session
```

Le secret doit correspondre à **`WEBHOOK_SECRET` du service API SIS récepteur**,
pas à un champ métier de l'établissement. Ne pas transmettre ce secret dans
un argument de commande, le dépôt, un ticket ou une capture. Limiter les droits
du fichier de configuration et inclure la configuration et la wheel du plugin
dans la sauvegarde chiffrée.

Sauvegarder et examiner le rendu avant `tutor config save`, préserver les
overrides opérateur puis recréer LMS et ses workers avec la nouvelle image.
Une liste non vide active `ENABLE_COURSE_ASSESSMENT_GRADE_CHANGE_SIGNAL`,
définit les cibles et installe le receiver Django s'il manque. Une liste vide
n'écrase pas une configuration native préexistante. Vérifier la tâche
`openedx.core.djangoapps.sis_grade_webhooks.tasks.publish_assessment_grade`
dans le worker ; un heartbeat ou une tâche sans cible n'est pas une livraison.

Les URL du plugin doivent être HTTPS, sans credentials ni fragment.
`course_ids` est facultatif mais **vivement recommandé** : absent ou vide,
la cible reçoit tous les cours. Préparer mappings utilisateur/cours/sous-section,
évaluation et barème, inscription active et dossier/habilitations de l'enseignant.
Une réception crée une proposition, jamais automatiquement une note officielle.
La décision exige notamment `notes.view_evaluation`, `notes.view_note`,
`notes.change_note` et le périmètre pédagogique approprié.

Surveiller erreurs et reprises Celery : le producteur natif a cinq reprises,
contrairement à l'outbox durable de provisioning décrite plus haut. Après leur
épuisement, ne pas annoncer un succès ni inventer un événement : conserver
l'incident et demander explicitement un recalcul natif du résultat déjà
enregistré après correction. Vérifier ensuite la proposition et sa décision.
Un recalcul émet un nouvel événement ; il ne remplace pas une note SIS existante.

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
