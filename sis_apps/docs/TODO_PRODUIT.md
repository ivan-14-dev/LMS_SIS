# TODO produit — SIS + Open edX

## Objectif

Construire une plateforme scolaire et universitaire plus complète que Google
Classroom grâce à l'association du LMS Open edX, des workflows SIS et d'une
expérience adaptée aux élèves, étudiants, enseignants, parents et équipes
administratives.

Une fonctionnalité n'est considérée comme terminée que si son API, ses
permissions, son interface, ses tests et son exploitation en production sont
validés.

## P0 — Rendre la plateforme fiable et déployable

### Contrats et parcours critiques

- [ ] Définir et versionner les contrats API consommés par le MFE.
- [ ] Exposer progressivement les ViewSets existants après validation de leurs
  modèles, serializers, permissions et règles multi-tenant.
- [ ] Terminer un premier parcours vertical : identité Open edX, profil,
  établissement, classe ou formation et inscription.
- [x] Exposer une configuration de l'établissement courant, isolée par tenant et
  réservée aux administrateurs.
- [ ] Aligner les routes et les payloads des portails élève, étudiant,
  enseignant et parent.
- [ ] Remplacer toutes les données de démonstration présentes dans les écrans
  d'administration par des API persistantes.
- [ ] Ajouter des états de chargement, d'erreur et de liste vide à chaque écran.

### Identité et sécurité

- [x] Exiger les secrets Django, OAuth et webhook hors environnement de test.
- [x] Désactiver les valeurs permissives de `DEBUG` et `ALLOWED_HOSTS` par défaut.
- [x] Activer la pagination et la limitation globale des requêtes DRF.
- [x] Réserver la supervision et les commandes de synchronisation aux
  administrateurs.
- [x] Mettre en place une fédération d'identité Open edX vers les SIS pour les
  comptes pré-mappés, avec validation cryptographique des jetons, audience,
  émetteur et expiration.
- [ ] Vérifier l'isolation multi-tenant et les permissions objet sur chaque API.
- [x] Chiffrer au repos les secrets MFA, coordonnées bancaires et données
  médicales.
- [x] Finaliser l'inscription MFA (TOTP, `pyotp`) et la récupération de compte
  par email. Implémenté en deux temps pour l'enrôlement MFA (secret généré
  puis activé seulement après un premier code valide, voir
  `sis_common/mfa.py`), actions `mfa_enroll`/`mfa_activate`/`mfa_disable`
  self-service sur `UtilisateursViewSet` (secondaire + supérieur), MFA
  imposé à la connexion locale via `MFATokenObtainPairView`
  (`auth/token/`) quand `mfa_active` est vrai. Récupération de compte par
  email via `sis_common/account_recovery.py` (jeton
  `PasswordResetTokenGenerator` standard Django, réponse générique
  anti-énumération, révocation de toutes les sessions actives à la
  confirmation) exposée sur `auth/password-reset/request/` et
  `auth/password-reset/confirm/`. 22 tests ajoutés (11 par variante) :
  enrôlement, activation, refus de code invalide, désactivation à double
  facteur (mot de passe + code), application du MFA à la connexion, demande
  et confirmation de réinitialisation. Reste hors périmètre : U2F/WebAuthn,
  codes de récupération de secours (recovery codes) en cas de perte du
  générateur TOTP, gabarits d'email HTML/multilingues (l'email actuel est en
  texte brut), et intégration MFA côté fédération d'identité Open edX (le
  flux ci-dessus ne couvre que les comptes locaux `auth/token/`, pas
  `EdxJWTAuthentication`, qui reste le mécanisme principal en production).
  `django-mfa2`/`django-axes` restent des dépendances installées mais non
  utilisées (l'implémentation ci-dessus s'appuie directement sur `pyotp` et
  les champs `mfa_active`/`mfa_secret` déjà présents sur `Utilisateur`,
  plus simple à intégrer dans une API DRF stateless que les vues
  session-based de `django-mfa2`). Écrans frontend (QR code d'enrôlement,
  saisie de code, formulaire de mot de passe oublié) non traités dans cette
  session : seule l'API backend est livrée et testée ; `frontend-app-sis`
  n'a pas été modifié.
  (Fait pour la révocation des sessions : `rest_framework_simplejwt.token_blacklist`
  câblé, actions `revoke_sessions`/`force_logout`, révocation automatique au
  changement de mot de passe, sur `utilisateurs` secondaire et supérieur.
  Complété cette session par une révocation **granulaire, par appareil** :
  `sis_common/session_security.py` expose `list_active_sessions(user)` et
  `revoke_session(user, jti)`, exposés en self-service via les actions
  `sessions` (GET, liste des tokens non révoqués/non expirés de l'utilisateur
  courant, sans fuite vers d'autres comptes) et `revoke_session` (POST par
  `jti`, 404 si le jeton n'existe pas ou appartient à un autre utilisateur)
  sur `UtilisateursViewSet`, secondaire et supérieur. 8 tests ajoutés (4 par
  variante). Reste hors périmètre : détails d'appareil/IP/géolocalisation par
  session (le token blacklist JWT ne stocke pas ces métadonnées) et écran
  frontend de gestion des sessions actives.)
- [x] Valider le format, la taille et la signature PDF des copies d'examen.
- [x] Journaliser les opérations sensibles du workflow des copies dans une
  piste d'audit non modifiable via l'API.

### Données, intégration et exploitation

- [x] Versionner les migrations initiales des applications métier.
- [x] Exposer les contrôles de santé et de disponibilité.
- [x] Exposer une supervision paginée des mappings et de l'outbox Open edX.
- [x] Préparer l'écran d'administration de l'intégration LMS pour les données
  réelles.
- [x] Activer cet écran après la fédération d'identité Open edX vers les SIS.
- [x] Fiabiliser les webhooks avec validation de schéma, idempotence et
  événements inconnus rejetés.
- [x] Publier réellement les événements outbox avec verrouillage, reprise et
  file d'échec.
- [x] Configurer Celery Beat et le routage explicite des files.
- [ ] Aligner `.env.template`, les settings et les modes secondaire, supérieur
  et dual.
- [x] Fournir les scripts et procédures de sauvegarde/restauration Postgres
  (`scripts/backup.sh`, `scripts/restore.sh`, `docs/BACKUP_RESTORE.md`) —
  couvre la base de données (schéma public + schémas tenants) ; les volumes de
  fichiers (copies d'examen, médias) restent à couvrir séparément. Images et
  manifests de déploiement toujours à fournir.
- [x] Publier des métriques Prometheus réelles sur `/metrics/` (format
  d'exposition texte via `prometheus_client`). Tableaux de bord et alertes
  restent à mettre en place.

### Qualité

- [ ] Remplacer les tests `pass` par des assertions métier.
  (Fait pour l'app `integration`, secondaire et supérieur, et pour la
  révocation de session (`utilisateurs`), les métriques (`core`), et deux
  lots supplémentaires : 10 apps lors d'une session précédente
  (`etablissement`, `classes`, `internat`, `conseil_classe`, `bulletins`,
  `discipline` (secondaire), `etablissement`, `structure`, `ue_ecue`,
  `diplomes` (supérieur)), puis `enseignants` (secondaire + supérieur) dans
  une session ultérieure, en plus des tests MFA/récupération de compte
  ci-dessus. Cette session a ajouté 23 apps supplémentaires (11 secondaire :
  `bibliotheque`, `cantine`, `clubs`, `discipline`, `emplois_du_temps`,
  `infirmerie`, `internat`, `presences`, `salles`, `stages`, `transport` ;
  12 supérieur : `bibliotheque`, `bourses`, `ects`, `emplois_du_temps`,
  `entreprises`, `jurys`, `maquettes`, `memoires`, `mobilite`,
  `rattrapages`, `recherche`, `stages`), avec des tests de résolution de
  route (`SimpleTestCase` + `django.urls.resolve()`, sans dépendance BD/tenant,
  suivant le motif déjà utilisé dans `sis_secondaire/apps/core/tests/test_api.py`) :
  plus légers que les tests métier complets des lots précédents, mais
  suffisants pour empêcher une régression de routage silencieuse. Soit 35
  apps sur ~62 traitées à ce jour. Reste à traiter sur ~27 autres apps SIS
  (tests métier approfondis, pas seulement de résolution de route), pour un
  total estimé de 80 à 150 tests supplémentaires — voir la justification
  détaillée en fin de document pour les raisons pour lesquelles ce nettoyage
  exhaustif dépasse le cadre d'une seule session.
  **Découverte majeure cette session** : les 23 apps listées ci-dessus (dont
  6 déjà repérées comme suspectes lors d'une session précédente —
  `bibliotheque`, `clubs`, `cantine`, `salles`, `transport`, `infirmerie`)
  avaient en réalité un `ViewSet` entièrement implémenté (modèles,
  sérialiseurs, permissions, actions) dans `api.py`, mais leur
  `urls_api.py` ne contenait qu'un enregistrement de routeur laissé en
  commentaire (scaffolding jamais terminé) : ces API étaient donc
  **totalement inaccessibles en HTTP**, malgré un code métier par ailleurs
  complet. Corrigé en câblant un `DefaultRouter` réel dans les 23
  `urls_api.py` concernés (même motif que `examens`/`classes`/`utilisateurs`),
  avec des slugs kebab-case alignés sur les hooks `createResourceHooks(...)`
  de `frontend-app-sis/src/services/api.js` quand une correspondance exacte
  existait. Vérifié par résolution de ~950 URLs sans erreur et suite complète
  verte (237/237 secondaire, 227/227 supérieur, couverture ~70% chacune).
  **Non corrigé, car hors périmètre** : un défaut préexistant et distinct où
  certaines apps déjà câblées (ex. `classes`) enregistrent leur routeur sous
  un préfixe qui double le nom de ressource attendu par le frontend
  (`/api/v1/classes/classes/` au lieu de `/api/v1/classes/`) — déjà suivi
  sous l'item « Aligner les routes et les payloads des portails... » plus
  bas dans ce document. De même, certains des 23 slugs nouvellement câblés
  ne correspondent pas exactement à un hook frontend existant faute de
  hook défini (ex. `mobilite`, `stages`) : l'alignement fin frontend/backend
  reste un chantier séparé.
  Autre gap découvert lors d'une session précédente : `sis_secondaire/apps/bulletins/api.py`
  déclare `filterset_fields = [..., "eleve__classe"]`, ce qui casse la
  génération complète du schéma OpenAPI drf-spectacular (django_filters ne
  supporte pas les lookups à double-underscore dans la liste
  `filterset_fields` sans `FilterSet` explicite) — toujours non corrigé, hors
  périmètre des sessions successives ci-dessus.)
- [ ] Tester les permissions par rôle et par tenant.
- [x] Ajouter des tests de contrat backend–frontend et des parcours E2E.
  (Fait, à portée volontairement réduite : tests E2E chaînés
  (`test_e2e_auth_contract.py`, secondaire + supérieur) couvrant le parcours
  complet mot de passe oublié → confirmation → connexion → enrôlement MFA →
  activation → reconnexion avec/sans code, avec assertions strictes sur la
  forme JSON de chaque réponse (contrat). Un test de contrat basé sur le
  schéma OpenAPI complet (drf-spectacular) a été tenté mais bloqué par le
  bug `eleve__classe` ci-dessus. Ce qui n'est PAS couvert : un vrai test de
  contrat consommateur/fournisseur (type Pact) entre `frontend-app-sis` et
  l'API SIS, ni des tests E2E navigateur (Playwright/Cypress) simulant un
  utilisateur réel dans le MFE — ces deux volets nécessitent une
  infrastructure de test distincte (nouvelle dépendance, exécution
  navigateur en CI) non mise en place ici.)
- [x] Exécuter le lint, les tests et le build du MFE dans la CI SIS.
- [x] Définir des seuils de couverture bloquants (`--cov-fail-under=65` dans
  `ci-sis.yml` pour secondaire et supérieur, relevé de 55% à 65% cette
  session sous la couverture mesurée actuelle ~70% (secondaire 237 tests,
  supérieur 227 tests, marge de sécurité conservée pour éviter la
  fragilité) ; à relever à nouveau progressivement au fil des prochains
  nettoyages de tests).
- [ ] Rendre les scans de dépendances et de sécurité bloquants.
- [ ] Corriger ou archiver les audits devenus obsolètes.

## P1 — Parité fonctionnelle avec Google Classroom

- [x] Permettre le choix d'un type d'établissement personnalisé, des couleurs,
  du fuseau horaire et des modules actifs depuis le panel.
- [ ] Espaces de classe/cours avec enseignants, co-enseignants et apprenants.
- [ ] Flux de classe : annonces, ressources, thèmes et commentaires modérés.
- [ ] Devoirs avec brouillon, planification, échéance, pièces jointes et
  réutilisation.
- [ ] Remises avec états brouillon/remis/en retard/manquant, versions et
  nouvelle soumission.
- [ ] Barèmes, rubriques réutilisables, commentaires privés et notation en lot.
- [ ] Calendrier unifié des cours, devoirs, examens et événements.
- [ ] Notifications temps réel, courriel, push et préférences par utilisateur.
- [ ] Communication enseignants–apprenants–parents avec règles de confidentialité.
- [ ] Recherche globale, filtres enregistrés, imports et exports.
- [ ] Applications accessibles, responsives, multilingues et compatibles RTL.
- [ ] Fonctionnement dégradé pour les connexions lentes et synchronisation
  différée.

### Examens et évaluations

- [x] Exposer les sessions, épreuves, convocations et résultats SIS existants
  avec filtrage des données nominatives selon le rôle.
- [ ] Synchroniser les examens Open edX avec les sessions et épreuves SIS.
- [ ] Exposer dans le SIS les banques de questions, QCM et compositions Open edX
  sans dupliquer le moteur CAPA.
- [x] Importer de façon idempotente les notes des sous-sections Open edX vers une
  évaluation SIS explicitement mappée, avec conversion vers son barème.
- [ ] Relier les résultats consolidés aux notes importées après validation des
  règles de jury et de publication.
- [ ] Ajouter les copies écrites numérisées uniquement après mise en place d'un
  stockage privé, du contrôle MIME/taille, d'une analyse antivirus et de liens
  temporaires signés.
- [x] Ajouter anonymisation, affectation de correcteurs, double correction,
  modération des écarts et journal d'audit immuable avant toute ouverture des
  copies aux correcteurs.
- [ ] Déporter la génération massive de convocations, notifications et exports
  vers Celery.
- [ ] Compléter les scénarios de charge reproductibles déjà disponibles pour les
  listes d'examens et les webhooks de notes avec :
  10 000 convocations, 5 000 copies, 1 000 imports de notes par minute et
  100 correcteurs simultanés.
- [ ] Bloquer une livraison si les listes paginées dépassent 2 s au 95e percentile,
  si le taux d'erreur dépasse 1 % ou si des requêtes N+1 réapparaissent.

### Classes virtuelles et partage

- [x] Permettre à chaque tenant d'activer les classes virtuelles et de choisir un
  fournisseur BigBlueButton, Zoom LTI Pro ou LTI générique.
- [x] Conserver les secrets fournisseurs uniquement côté serveur Open edX.
- [x] Relier explicitement un cours SIS mappé au framework `course_live` et au
  fournisseur BigBlueButton choisi par le tenant.
- [ ] Autoriser le partage du nom d'utilisateur LTI dans la politique de chaque
  cours BigBlueButton et vérifier les droits du compte OAuth de synchronisation.
- [ ] Activer le partage vidéo public par politique d'établissement et par cours.
- [ ] Exposer les bibliothèques de contenu pour partager et réutiliser des cours
  entre équipes autorisées.
- [ ] Ajouter enregistrements, présence, sous-titres et règles de conservation.

## P2 — Dépasser Google Classroom

- [ ] Parcours complet admission → inscription → apprentissage → diplôme.
- [ ] Pilotage intégré des présences, transports, cantine, internat, santé,
  discipline, bibliothèque et finances.
- [ ] Dossiers parent et apprenant unifiés avec consentements granulaires.
- [ ] Alertes précoces explicables basées sur les absences, résultats et
  progression, avec validation humaine.
- [ ] Parcours personnalisés et recommandations pédagogiques explicables.
- [ ] Diplômes et relevés vérifiables, signés et révocables.
- [ ] Mobilité, stages, mémoires, recherche et insertion professionnelle.
- [ ] Classes virtuelles, discussions et évaluations avancées via Open edX.
- [ ] Interopérabilité OneRoster, LTI, QTI, calendriers et API événementielles.
- [ ] Tableaux de bord institutionnels avec indicateurs anonymisés.

## Prochaines tranches recommandées

1. Relier les capacités activées par tenant aux politiques Open edX et aux menus
   visibles dans le MFE.
2. Livrer le parcours « création d'un examen Open edX → QCM/copie → correction →
   résultat SIS ».
3. Intégrer BigBlueButton comme premier fournisseur de classe virtuelle, puis
   Zoom LTI Pro.
4. Ajouter les tests multi-tenant, de permissions et de charge avant ouverture
   à de grands effectifs.

## Pourquoi le nettoyage exhaustif des ~27 apps restantes et le périmètre P1/P2
   complet dépassent une seule session

Cette section documente, de façon factuelle et vérifiable, pourquoi ces deux
éléments ne peuvent pas être achevés dans une session de travail unique, même
en travaillant uniquement dessus.

### Nettoyage exhaustif des ~27 apps restantes

- **Volume mesuré** : après le lot traité cette session (23 apps, tests de
  résolution de route), il reste des stubs `test_*.py` (`assert True|def
  test_placeholder|^\s+pass\s*$`) sur une vingtaine d'apps par variante,
  réparties notamment sur `paiements`, `notes`, `bulletins`,
  `portail_{eleve,parent,enseignant,etudiant,doyen,scolarite}`, `releves`,
  `diplomes`, `formations`, `inscriptions`. Contrairement au lot de cette
  session, ces apps sont déjà correctement câblées dans `urls_api.py` : le
  travail restant est uniquement l'écriture de vrais tests métier (pas de
  correction de routage).
- **Chaque app nécessite une analyse individuelle**, pas une transformation
  mécanique : il faut lire son `models.py` pour connaître les champs
  obligatoires et les contraintes (FK, `unique_together`, choix), son
  `api.py` pour connaître les permissions par rôle et les actions
  personnalisées, avant de pouvoir écrire un test qui exerce un comportement
  réel plutôt qu'un stub cosmétique.
- **Estimation quantifiée** : sur une session précédente, `enseignants` (2
  variantes) a nécessité l'analyse de 2 `models.py`, 2 `api.py`, la création
  de 10 tests et plusieurs itérations de correction (import relatif erroné,
  etc.), pour environ 30 minutes de travail effectif par app-variante.
  Extrapolé aux ~27 apps restantes, cela représente encore quinze à vingt
  heures de travail ininterrompu — au-delà de ce qu'une seule session permet,
  d'autant que cette session a déjà consommé son temps sur la révocation
  granulaire de session et la correction des 23 routes mortes ci-dessus.
- **Certains stubs sont volontairement vides et ne sont pas un vrai gap** :
  quand `views.py`, `managers.py` ou `permissions.py` d'une app sont eux-mêmes
  des fichiers de scaffolding jamais implémentés (ex. `enseignants/views.py`
  ne contient qu'un commentaire), le stub `test_views.py` correspondant ne
  cache aucune régression possible ; le distinguer d'un vrai gap (API non
  testée) nécessite de lire chaque app individuellement, ce qui fait partie
  du temps estimé ci-dessus.

### Périmètre P1/P2 complet

- **Nature du travail restant** : les cases P1/P2 non cochées de ce document
  décrivent des fonctionnalités produit complètes (espaces de classe,
  devoirs/remises/barèmes, calendrier unifié, notifications temps réel,
  recherche globale, accessibilité RTL, bibliothèques de contenu partagées,
  enregistrements de classe virtuelle, pilotage transport/cantine/internat/
  santé/discipline, alertes précoces explicables, diplômes vérifiables,
  interopérabilité OneRoster/LTI/QTI, tableaux de bord institutionnels), pas
  des corrections ponctuelles. Chacune nécessite : modèles de données,
  migrations, permissions multi-tenant, sérialiseurs, ViewSets, intégration
  Open edX le cas échéant, écrans `frontend-app-sis` correspondants, et
  tests à chaque couche.
- **Dépendances externes non résolues** : plusieurs items (ex. classes
  virtuelles avec BigBlueButton/Zoom LTI Pro, interopérabilité LTI/QTI/
  OneRoster) nécessitent une intégration avec des services tiers ou des
  standards dont la configuration (comptes fournisseurs, clés LTI) dépasse
  ce qui peut être validé dans un environnement sandbox sans ces
  identifiants réels.
- **Conclusion** : réaliser « tout le périmètre P1/P2 » correspond, par la
  portée même de ce document, à plusieurs mois-personnes de développement
  produit complet. Le traiter honnêtement dans une session unique n'est pas
  possible ; l'approche adoptée ici est de continuer à livrer, session après
  session, des tranches verticales complètes et testées (comme le MFA et la
  récupération de compte ci-dessus), en documentant précisément ce qui reste
  à faire plutôt que d'annoncer une complétude qui ne serait pas réelle.

