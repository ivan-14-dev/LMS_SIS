# Recette native bornée — stages pratiques

**Statut : recette préparée, non exécutée par cette livraison.** Le guide
[practical-training.md](practical-training.md) fait foi pour le contrat.
Les résultats backend/frontend antérieurs ne qualifient pas les correctifs de
cette livraison, ni le parcours navigateur. Une démonstration de bulletins ne
qualifie pas les stages.

## 1. Isolation et conditions d'arrêt

Exécution réservée au superviseur, après autorisation de ressources. Ne pas
réutiliser, relancer, réensemencer ou nettoyer les anciennes piles/preuves de
qualification ; ne pas utiliser la démo courante comme terrain de test.

Avant toute écriture, consigner dans un répertoire privé **nouveau**, sous le
projet d'intégration :

- SHA testé, variantes, configuration effective et nom unique du passage ;
- origines frontend/API, noms des deux bases de recette et bases de test,
  schémas/tenants, identifiants des comptes synthétiques, stockage PDF privé ;
- propriétaire et réservation explicite de ces ressources ; aucune référence
  vers une base, un volume, un tenant ou un stockage d'ancienne qualification ;
- empreinte et inventaire des données préexistantes de la nouvelle baseline.

Ne pas inscrire de mots de passe, cookies ou jetons dans un document committé.
Les captures et traces restent privées ; masquer les secrets des échanges.
Ne pas employer de données personnelles réelles.

Une seule variante et un seul runner à la fois, un navigateur avec des
contextes de comptes séparés, sans charge parallèle. Limite proposée :
15 minutes par suite ciblée et 30 minutes de parcours natif par variante.
Sur dépassement, erreur 5xx, migration inattendue, mauvais tenant ou tentative
vers une origine non réservée : arrêter **ce passage**, conserver l'état et
les diagnostics, ne pas réinitialiser ni réessayer automatiquement.
Le démarrage, l'arrêt et la construction des services sont hors de cette recette.

## 2. Porte technique préalable

Dans les environnements backend déjà préparés par le superviseur :

1. Relire le plan des migrations de `stages`. Cette livraison ajoute
   `0003_practical_training` au secondaire et `0002_practical_training` au
   supérieur, sans conversion des conventions, anciens rapports ou notes.
2. Appliquer les migrations uniquement sur la baseline isolée réservée.
   Comparer l'inventaire avant/après des tables historiques et des fichiers.
   Aucun ancien rapport ne doit devenir une heure ou une compétence acquise.
3. Exécuter séquentiellement les suites ci-dessous sur des bases **de test**
   distinctes de la baseline native. `FastTenantTestCase` crée/utilise un schéma
   `fast_test` et effectue des nettoyages : ne jamais pointer les tests vers
   les données de recette natives ou anciennes preuves.
4. Les tests de pièces emploient un stockage éphémère. Le superviseur fournit
   `TMPDIR` vers un sous-répertoire privé réservé **dans le projet**, jamais
   `/tmp`. Les environnements et dépendances doivent déjà exister.

Depuis `sis_apps/sis_secondaire`, puis séparément `sis_apps/sis_superieur`,
avec les réglages PostgreSQL/tenant du runner réservé :

```sh
python manage.py showmigrations stages --plan
python manage.py makemigrations stages --check --dry-run
python manage.py test \
  sis_common.tests.test_practical_training \
  sis_common.tests.test_practical_access \
  sis_common.tests.test_practical_hours \
  sis_common.tests.test_practical_evidence \
  apps.stages.tests.test_practical \
  --noinput --parallel 1
```

Les quatre suites communes ne sont **pas** importées par le dernier sélecteur.
Pour cibler seulement la régression backend de cette passe, remplacer les cinq
sélecteurs par :

```text
sis_common.tests.test_practical_training.PracticalTrainingTests.test_malformed_live_offering_preserves_programme_reads_revision_and_archival
```

Depuis `sis_apps/frontend-app-sis`, après autorisation du superviseur :

```sh
npm test -- --watch=false --runInBand --coverage=false --runTestsByPath \
  src/practical/PracticalTrainingPage.test.jsx \
  src/components/layout/navigation.practical.test.js \
  src/App.test.jsx
```

Ces tests utilisent des réponses HTTP simulées ; ils ne sont pas une preuve
native. Les nouvelles régressions frontend portent sur les habilitations
partielles du tuteur et l'affichage des blocages non structurels du dossier.
Enregistrer commande, code retour et bilan de chaque variante ; ne pas
extrapoler des anciens décomptes.

## 3. Jeu natif minimal réservé

Préparer les objets institutionnels **avant** le parcours pratique par les
outils administratifs existants, sans lancer un ancien script de seed :

- un tenant actif par variante, fuseau connu, module `sis.practical_training`
  activé avec ses dépendances `core.identity` et `core.notifications` ;
- une classe/formation locale et une année couvrant la période ; une inscription
  scolaire admissible ou une inscription administrative validée au supérieur ;
- un apprenant actif, un gestionnaire, un tuteur interne, un partenaire et un
  compte témoin non affecté, tous distincts et locaux ;
- deux conventions complètes et signées du même apprenant, missions non vides,
  période incluant hier et aujourd'hui. Au supérieur : une offre distincte par
  convention (relation un-à-un), même formation/entreprise que la convention,
  enseignant-tuteur et contact d'entreprise actif lié au partenaire ;
- un petit vrai PDF synthétique, validable et sans information personnelle ;
  relever sa taille et son SHA256.

Permissions minimales (sans super-utilisateur, rôle ou `is_staff` de secours) :

| Compte | Permissions pratiques |
| --- | --- |
| Gestionnaire | `gerer_suivi_pratique` |
| Apprenant | `consulter_suivi_pratique`, `saisir_heures_pratiques` |
| Tuteur | `consulter_suivi_pratique`, `valider_heures_pratiques`, `evaluer_competences_pratiques` |
| Partenaire | `consulter_suivi_pratique` |
| Témoin non affecté | `consulter_suivi_pratique` |

Tous ces noms sont préfixés par `stages.`. Les droits de gestion des conventions
historiques sont séparés ; ne pas les déduire de ces permissions.
Au secondaire, sélectionner explicitement le partenaire à l'ouverture ;
au supérieur, contrôler le compte du contact affiché.

Pour la preuve d'habilitation partielle, préparer d'abord le tuteur avec seulement
le droit d'évaluation, constater l'avertissement dans le sélecteur, puis faire
ajouter son droit de validation par l'administrateur avant le parcours complet.
Cela ne doit ni modifier la convention, ni créer un nouveau compte.

## 4. Parcours navigateur, sans simulation d'API

Utiliser le vrai formulaire de connexion et la navigation native
`/{variante}/stages-pratiques`. Les labels de connexion peuvent contenir
l'astérisque MUI : dans Playwright, utiliser
`getByLabel(/^Identifiant/)` et `getByLabel(/^Mot de passe/)`, puis le bouton
réel du formulaire. Pas de `force_authenticate`, interception de réponses,
injection de jeton ou modification de base pendant les gestes métier.
L'URL, le compte et le tenant doivent être vérifiés après chaque connexion.

| Étape | Acteur et geste | Attendu observable |
| --- | --- | --- |
| N1 | Gestionnaire : créer `natif-<passage>`, 120 minutes, compétence `securite`, puis publier | Brouillon puis révision 1 publiée ; bouton de configuration retiré ; historique de publication |
| N2 | Ouvrir le sélecteur, choisir convention 1, vérifier missions, dates, inscription, tuteur et ses deux habilitations | Ni convention inventée ni heures prévisionnelles comptabilisées ; avertissement si tuteur partiellement habilité |
| N3 | Après habilitations complètes, ouvrir D1 avec partenaire ; ouvrir D2 avec convention 2 | Deux dossiers distincts, bilan initial à zéro, même révision publiée figée |
| N4 | Apprenant : dans D1, hier 09:00–11:00, pause 0, activité concrète, PDF ; confirmer | Brouillon de 120 min, zéro minute validée ; preuve téléchargeable, horloge institutionnelle affichée |
| N5 | Apprenant : essayer la même plage dans D2 | Conflit de chevauchement, aucune nouvelle ligne/version/décision ; aucun renvoi automatique |
| N6 | Apprenant : soumettre la ligne D1 ; tuteur : rejeter avec motif | Soumise puis rejetée, bilan validé toujours à zéro ; décisions horodatées |
| N7 | Apprenant : remplacer la ligne rejetée, motif, même plage, sans nouvelle pièce ; soumettre | Nouvelle ligne liée à l'original ; l'ancienne preuve reste sur l'original, pas sur le remplacement |
| N8 | Tuteur : valider le remplacement | 120 min validées, compétence encore manquante ; apprenant/gestionnaire non affecté n'ont aucun bouton de validation |
| N9 | Tuteur : évaluer non acquise, puis réévaluer acquise avec contexte et motif | Deux évaluations conservées, seule la dernière effective ; seuils atteints sans clôture implicite |
| N10 | Apprenant : ajouter un brouillon distinct 12:00–12:15 dans D1 | 15 min brouillon séparées, toujours 120 min validées |
| N11 | Gestionnaire : créer révision 2 à 240 min, publier, puis l'archiver avec motif | Révisions conservées ; nouvelles ouvertures indisponibles ; D1/D2 gardent révision 1 et 120 min |
| N12 | Gestionnaire : clôturer D1 avec succès | Dossier clos, 120 min validées, brouillon de 15 min annulé et conservé, aucune écriture métier proposée |
| N13 | Gestionnaire : annuler D2 avec motif | Dossier annulé, pas de réussite ; motif et acteur présents |
| N14 | Partenaire : consulter D1 et télécharger l'ancienne preuve ; gestionnaire : révoquer après clôture | Heures/compétences/clôture inchangées ; nouvelle version et audit de révocation seulement |
| N15 | Partenaire : actualiser D1/tenter l'ancien téléchargement ; témoin : ouvrir le lien D1 | Refus réel, contenu privé masqué, aucun PDF vide présenté comme succès ; gestionnaire conserve sa lecture |
| N16 | Gestionnaire : recharger D1, historique des heures/évaluations et programme | État persistant identique, anciennes preuves disponibles au compte encore habilité, aucune note/crédit/diplôme publié |

Les formulaires pratiques utilisent leurs labels visibles (par exemple
`/^Date locale du travail/`, `/^Activité professionnelle réalisée/`) et le bouton
`Confirmer — …`. Pour les décisions, limiter les sélecteurs au formulaire actif
ou à l'article de l'heure pour éviter de cliquer une autre ligne.

Noter l'identifiant et la version de chaque objet après succès. Pour N5 et les
refus N15, joindre la réponse réelle expurgée et une relecture autorisée montrant
l'absence de mutation. Une capture de bouton masqué seule ne prouve pas le refus
serveur ; les régressions backend couvrent aussi les tentatives HTTP directes.
La preuve N14 compare les octets téléchargés à leur SHA256, pas seulement le nom.

## 5. Cas bornés complémentaires

Après N16, sur ces seuls objets isolés :

- **Conflit volontaire** : sur un dossier encore ouvert réservé à ce cas, ouvrir
  le même formulaire dans deux contextes autorisés ; une première commande
  avance la version. La seconde reçoit 409, conserve texte/pièce et demande
  confirmation après relecture. Ne pas rejouer automatiquement. Si aucun
  dossier ouvert n'est réservé, reporter ce cas sans rouvrir D1/D2.
- **Blocage non structurel** : le superviseur change temporairement le fuseau du
  seul tenant de recette sur un dossier ouvert réservé. Le contexte bloquant
  doit être affiché et les écritures métier retirées, sans perdre l'historique.
  Remettre le fuseau initial uniquement par la même administration ; ne pas
  modifier une ligne historique. Les tests automatisés couvrent aussi acteur
  et cursus inactifs.
- **Offre académique devenue invalide** : couvert par la régression backend
  ciblée. Ne pas introduire volontairement du JSON invalide dans une base native
  via SQL pour prétendre à un parcours utilisateur. La lecture/révision/archivage
  restent disponibles ; la publication reste refusée.

## 6. Périmètre non qualifié par cette recette

L'amont offre/candidature/convention est un prérequis institutionnel séparé.
Au secondaire, la signature historique est une progression de statut, pas une
signature électronique probante. Au supérieur, cette API ne fournit pas de
commande de signature ni de soutenance. Le secondaire conserve son champ
historique `note_soutenance`, sans jury/calendrier dans le module pratique.
Aucune soutenance, publication académique, notification externe, génération de
certificat, purge ou archivage probant n'est attesté par N1–N16.

La validation finale doit donc séparer : tests techniques exécutés, migrations
additives vérifiées, parcours natif observé par variante, et limites externes.
Une seule variante réussie, un login réussi ou une recette seulement rédigée ne
permettent pas d'annoncer le lot « qualifié ». Conserver les preuves du passage
sans les écraser lors d'un passage ultérieur.
