# Enquêtes institutionnelles nominatives — incrément borné 10.12

## Portée

Module commun aux SIS secondaire et supérieur, **désactivé par défaut** :
`sis.surveys`. Activation par l'administration des modules existante ; aucune
activation, attribution de droits ou modification de compte lors de la migration.
Il dépend de `core.identity` et `core.notifications` (audit existant).

La publication rend l'enquête disponible dans le portail interne des comptes
explicitement sélectionnés. Aucun courriel, appel externe, lien public, formulaire
invité ou mécanisme d'anonymisation n'est ajouté. La politique **nominative** est
affichée dans l'interface et retournée par l'API ; les gestionnaires voient
l'identité et les réponses. Les répondants ne voient que leur propre réponse.

Tous les comptes actifs rattachés au tenant courant peuvent être sélectionnés,
indépendamment du rôle et de `is_staff`. Cela inclut les apprenants, enseignants,
parents et partenaires authentifiés. Le profil natif `partenaire` / « Partenaire »
est proposé dans les deux SIS et le formulaire administratif. Il ne crée aucun
groupe, permission, affiliation scolaire ou compte LMS ; `is_staff` et
`is_superuser` restent faux lors de sa création ordinaire. Les rôles personnalisés
existants restent acceptés. Aucun accès invité ou partenaire non authentifié
n'est ajouté.

Limites : 1–20 questions obligatoires, texte libre de 2 000 caractères ou choix
unique parmi 2–10 options distinctes de 120 caractères ; 1–200 destinataires.
Pas de questionnaire conditionnel, question facultative, choix multiple, pièce
jointe, réponse modifiable, réouverture, export, anonymat ou campagne automatisée.
L'analyse comprend les réponses nominatives et les comptages des choix, pas une
analyse statistique avancée. L'exigence10.12 est vérifiée uniquement dans ce
périmètre nominatif déclaré ; ce n'est pas une validation globale du programme.

## Accès et parcours

- Permission Django administrable :
  `core.gerer_enquete_institutionnelle`, portée ABAC acceptée
  `etablissement_id`. Une portée inconnue ou non satisfaite refuse la gestion.
  Aucun accès déduit d'un rôle ou de `is_staff`. Le superutilisateur suit la
  convention existante, mais doit également appartenir au tenant actif.
- UI commune : `/{secondaire|superieur}/portail-enquetes`, accessible par
  « Mes enquêtes institutionnelles » dans la navigation lorsque le module est
  explicitement actif. La vue gestion exige une capacité serveur supplémentaire.
- Les répondants utilisent exclusivement le sous-portail `portail/enquetes`,
  y compris les non-staff/parents ; aucune permission de gestion ou permission
  du portail staff n'est requise ni attribuée. La sélection nominative constitue
  l'autorisation propre à ce sous-portail, sans élargir les portails académiques.
- Un brouillon est invisible aux destinataires. La publication fige questionnaire,
  description, titre et sélection. Seule la révocation d'un destinataire reste
  possible. La fermeture interdit les nouvelles réponses mais permet de relire
  sa réponse, tant que l'accès n'est pas révoqué.
- Révocation de destinataire, compte désactivé/déplacé, retrait de permission,
  module désactivé ou mauvais contexte tenant : contrôlés à chaque requête.
  Une révocation ne détruit pas les réponses historiques. Les résultats
  gestionnaires excluent les comptes déplacés vers un autre établissement.
- Les écrans masquent les données précédentes pendant la revalidation et après
  erreur. Une commande en échec ne conserve pas de formulaire/résultat périmé ;
  le rechargement relit l'état serveur, sans nouvelle soumission automatique.

## Contrats API

Préfixe `/api/v1/`, identifiant d'enquête UUID. Toutes les routes exigent une
session authentifiée active, un établissement actif, le schéma tenant courant
et l'activation du module.

### Gestion habilitée : `core/enquetes/`

| Méthode et suffixe | Contrat |
|---|---|
| `GET /` | Liste paginée des enquêtes du tenant. |
| `POST /` | Crée un brouillon ; retourne le détail, HTTP 201. |
| `GET candidats/?q=...&page=1&page_size=20` | Recherche de 2–100 caractères ; comptes actifs locaux, tous profils ; `id`, `nom`, `profil` seulement. |
| `GET {id}/` | Détail avec `version`, questionnaire et destinataires ; `revoked_at` pour chaque destinataire. |
| `POST {id}/configurer/` | Remplacement du brouillon uniquement, commande complète et version courante. |
| `POST {id}/publier/` | `{ "version": N }` ; revalide les comptes actifs locaux. |
| `POST {id}/fermer/` | `{ "version": N }` ; publication → fermeture définitive. |
| `POST {id}/revoquer/` | `{ "version": N, "destinataire": user_id }` ; après publication, accès définitivement retiré. |
| `GET {id}/resultats/` | `politique`, `information`, `destinataires`, `reponses_recues`, `choix` et `reponses` nominatives. |

Commande complète de création/configuration :

```json
{
  "titre": "Avis sur les services",
  "description": "Enquête interne",
  "politique": "nominative",
  "questionnaire": [
    {"id": "avis", "libelle": "Votre avis", "type": "texte", "choix": []},
    {"id": "accueil", "libelle": "Accueil", "type": "choix", "choix": ["Bien", "À améliorer"]}
  ],
  "destinataires": [11, 12]
}
```

La configuration ajoute `version`. Identifiants de question distincts,
alphanumériques/`_`/`-`, commençant par une lettre, longueur maximale 40.
Titre 200 caractères, description 3 000. Aucun champ inconnu accepté.
Liste et candidats paginés (50 par défaut, plafond 100).
Les résultats sont bornés par les 200 destinataires et 20 questions ;
le dénominateur inclut les comptes locaux révoqués/inactifs sélectionnés.

### Répondant : `portail/enquetes/`

| Méthode et suffixe | Contrat |
|---|---|
| `GET capacites/` | `can_manage`, `politique`, `information` ; pas de données de destinataires. |
| `GET /` | Liste paginée des seules enquêtes publiées/fermées explicitement adressées au compte. |
| `GET {id}/` | Questionnaire, `ma_reponse` ou `null`, `peut_repondre` ; jamais les autres destinataires/réponses. |
| `POST {id}/repondre/` | `{ "politique": "nominative", "reponses": { "avis": "...", "accueil": "Bien" } }` ; HTTP 201. |

Toutes les questions, et seulement celles-ci, doivent être renseignées.
Pas d'API générique de modification/suppression. Refus : 400 pour entrée invalide,
403 pour absence d'habilitation/module/tenant, 404 pour objet hors périmètre,
409 pour version périmée, transition interdite, fermeture ou réponse déjà reçue.
Les doublons ne remplacent jamais une réponse existante.

## Persistance et audit

Bases communes `sis_common/survey_models.py`, commandes strictes
`survey_serializers.py`, API commune `surveys.py`.

Dans **chaque variante**, `core/0013_institutional_surveys.py` dépend de
`0012_project_competencies` et du modèle utilisateur interchangeable. Trois tables :

- `core_institutionalsurvey` : UUID, établissement protégé, créateur protégé,
  titre/description, politique nominative, questionnaire JSON, statut, version,
  dates ; contraintes de politique et de statut.
- `core_surveyrecipient` : enquête et utilisateur protégés, date de révocation ;
  contrainte unique `(enquete, utilisateur)` `survey_unique_recipient`.
- `core_surveyresponse` : relation `OneToOneField` protégée vers le destinataire
  (unicité DB), réponses JSON, date de réception.

Aucun changement aux tables de comptes, MFA ou attributions de droits.
Publication, configuration, fermeture, révocation et réponse sont atomiques.
Les commandes d'une enquête partagent un verrou `SELECT FOR UPDATE` sur son
enregistrement ; les réponses sont en plus contraintes par l'unicité DB.
Un conflit concurrent retourne une erreur explicite. L'audit est dans la même
transaction : son échec annule l'écriture.

Événements `enquete_cree`, `enquete_configuree`, `enquete_publiee`,
`enquete_fermee`, `enquete_destinataire_revoque`, `enquete_reponse_recue`.
Pas de contenu de réponse/questionnaire dans les événements. Le modèle
`institutionalsurvey` est exclu des vues/exportations d'audit génériques via
`PRIVATE_WORKFLOW_MODELS`. Aucun envoi de notification/courriel automatique.

## Qualification exécutée — lot34

Qualification parent sur PostgreSQL/Redis et services **isolés**, sans remplacer
les services partagés :

- 24 tests backend réussis dans **chaque SIS**, avec
  `makemigrations --check --dry-run` conforme. Le premier essai scolaire
  avait 12 erreurs : la méthode `detail` était masquée par un attribut DRF.
  Elle a été renommée `serialize_detail`, puis l'image reconstruite et les
  deux suites entièrement réexécutées. Le résultat rouge est conservé.
- Black120, isort profil black et flake8 sur les 15 fichiers Python produit ;
  ESLint ciblé ; 107 tests Jest sur six suites. Les passages auteur/parent
  recouvrants ne sont pas additionnés.
- Nouveau build frontend réussi avec trois avertissements webpack de taille.
  176 sources et 23 fichiers servis par HTTP rapprochés par empreintes.
- Migration0013 réellement appliquée sur des copies peuplées des restaurations33 :
  cinq schémas par SIS, 579 tables scolaires et 630 universitaires.
  Anciens comptes, MFA/TOTP réel, droits et fichiers préservés.
  La fixture ajoute huit comptes par SIS, active explicitement le module
  et ne crée aucune enquête.
- Chromium réel dans chaque SIS : six acteurs UI, sept commandes UI,
  24 contrôles API, huit rejeux inter-Host refusés401 et huit captures.
  Cycle nominatif, trois publics, résultats/comptages, doublons,
  non-destinataire, révocation et fermeture ; second tenant par API native.
- API et proxy réellement recréés : toutes les tables, les 32/29 entrées
  des volumes et le MFA sont exactement comparés **avant** nouvelle connexion.
  Puis huit vrais logins et 64 contrôles métier GET par SIS
  (216 requêtes HTTP au total par parcours de réouverture), sans écriture métier.
- Vérification exhaustive après les deux fenêtres de connexion : anciens
  comptes/droits/données intacts ; seul `last_login` des nouveaux acteurs est
  normalisé. Une session et un log de connexion exactement par acteur et
  fenêtre ; aucune extension de la fenêtre d'écriture métier originale.
  Seules les six tables d'authentification attendues changent à la réouverture.
  Les anciens octets des fichiers sont conservés ; seul `logs/sis.log` s'enrichit.

Le premier parcours scolaire a échoué **avant toute commande d'enquête** :
le banc conservait une requête de l'ancien document après rechargement.
La correction retire ces requêtes au commit d'un vrai document, jamais lors
d'une navigation SPA. Le diagnostic n'est pas compté comme recette.
La base, le volume et les artefacts rouges sont conservés séparément ; le
parcours final part d'une nouvelle copie33 remigrée et préparée.
Un premier refus du lanceur Bash et un nginx500 dû aux permissions du bundle
généré sont également conservés ; seuls les modes des fichiers publics ont
été corrigés, sans changement de contenu.

Commandes backend ciblées, dans chaque variante avec la configuration de test
isolée et `PYTHONPATH` contenant `sis_apps` :

```sh
# Répertoire de la variante ; PYTHONPATH contient le répertoire sis_apps.
python manage.py makemigrations --check --dry-run
python manage.py test \
  sis_common.tests.test_survey_commands \
  sis_common.tests.test_surveys \
  sis_common.tests.test_module_registry \
  sis_common.tests.test_modules \
  --noinput
```

`InstitutionalSurveyTests` couvre le cycle, les refus/tenants, droits administrables,
révocation, immutabilité, contraintes et audit atomique.
`SurveyConcurrencyTests` est transactionnel PostgreSQL : deux réponses simultanées,
fermeture/réponse et révocation/réponse.

**Au cutoff du lot34, 10.12 reste partielle.** Restent le quatrième public partenaire authentifié
et la sauvegarde/restauration indépendante du nouvel incrément. Le clonage
de préparation et la recréation ne remplacent pas cette restauration.
SMTP, export, anonymat non annoncé et statistiques avancées ne sont pas
ajoutés aux critères de réception existants. Pas de pilote institutionnel,
déploiement partagé, nouvelle charge500, contrôle des séquences post-UI ou
validation globale des F-lots. Les suites ciblées ne valent pas suite intégrale.

## Qualification exécutée — lot35

Le quatrième public **Partenaire authentifié** est maintenant exercé dans les
deux SIS, sans groupe, permission, affiliation académique ou compte LMS implicite.
La lecture scolaire des élèves exige une habilitation explicite hors accès
personnel apprenant/tuteur ; un élève non superutilisateur reste limité à son
dossier en lecture même avec `is_staff` ou la permission de modèle. Cette
correction ne prétend pas protéger universellement toutes les autres API.

- Backend scolaire : 112 tests réussis, puis trois tests de la classe affectée
  réexécutés sur l'image finale ; **pas 115 tests distincts**. Backend supérieur :
  76 tests réussis sur l'image finale. Le premier passage supérieur avait une
  erreur de nom de modèle dans un nouveau test (`Enseignant` au lieu
  d'`EnseignantChercheur`), corrigée sans changement de code applicatif entre
  les deux images. Les neuf couches de base/dépendances et la configuration
  d'image sont identiques ; les 1 507 autres fichiers Python sont inchangés.
  Les contrôles de divergence des migrations sont conformes.
- 143 tests Jest sur cinq suites, ESLint ciblé et nouveau build frontend ;
  trois avertissements webpack de taille conservés. Les 176 sources et
  23 fichiers servis sont rapprochés par empreintes. L'absence initiale de
  `fedx-scripts` a été résolue en réutilisant les dépendances existantes après
  comparaison des lockfiles ; aucun test n'avait démarré lors de ce refus.
  Les résultats auteur/parent recouvrants et les essais rouges restent distincts.
- isort et flake8 complets conformes sur les sept fichiers Python modifiés.
  Les lignes modifiées sont conformes à Black ; deux fichiers scolaires gardent
  des écarts de formatage historiques hors des lignes changées. Aucun Black
  global conforme n'est prétendu sur ces deux fichiers.
- Copies des sources34 finales : cinq schémas, 579/630 tables, anciens comptes,
  droits, MFA/TOTP, flags et fichiers intacts. Aucune migration nouvelle.
  Dix comptes ajoutés par SIS, aucune enquête créée par la fixture,
  aucun ancien flag ou compte modifié.
- Chromium réel dans **chaque SIS** : sept acteurs UI, huit commandes UI,
  41 contrôles API, 14 rejeux inter-Host refusés401 et neuf captures.
  Les quatre publics répondent dans le tenant principal ; apprenant et partenaire
  répondent aussi dans le second tenant. Résultats 4/4 puis 2/2,
  confidentialité des réponses, doublons, non-destinataire, révocation du
  partenaire et fermeture contrôlés. Les anciennes enquêtes34 restent intactes.
- API/proxy réellement recréés. Avant nouvelle connexion : égalité de toutes
  les tables, des **523/574 séquences**, des 32/29 entrées de volume et du MFA.
  Puis dix vrais logins par SIS : **86 GET métier/288 requêtes HTTP scolaires**
  et **84 GET/282 requêtes HTTP universitaires**, sans retry ni écriture métier.
  Les deux GET supplémentaires scolaires refusent au partenaire la liste et
  la recherche d'élèves sur une base principale réellement peuplée.
- Après réouverture, contrôle exhaustif des données et des deux fenêtres
  d'authentification : une session et un log par acteur et fenêtre,
  soit 14/14 dans le tenant principal et 6/6 dans le pair. Seules six tables
  d'authentification changent ; anciens comptes/droits/MFA, métier et octets
  des fichiers conservés. Seul `logs/sis.log` reçoit des octets supplémentaires.

**Au cutoff35,10.12 restait partielle : la sauvegarde/restauration indépendante
de ce nouvel incrément restait à démontrer.** Le clonage et la recréation ne la remplacent pas.
Les séquences sont comparées à travers la recréation, pas avant/après les
commandes métier qui les font légitimement avancer. Aucun déploiement partagé,
pilote institutionnel, nouvelle charge500 ou achèvement global n'est annoncé.

## Qualification exécutée — lot36

La restauration indépendante complète maintenant la règle commune :
**seule10.12 est promue vérifiée**, sans modification de ses deux critères
propres ni ajout de SMTP, export ou anonymat non annoncé.

L'image35 et le bundle35 restent strictement identiques au produit publié.
Les tests backend/Jest et les parcours Chromium35 ne sont pas recomptés :
aucun nouveau code, schéma, build ou parcours Chromium36.

Sauvegardes réellement exécutées par `pg_dump` au format custom et archives
complètes des volumes ; `pg_restore` transactionnel dans de nouvelles bases
`template0` et extraction dans de nouveaux volumes vides. Avant tout login,
les deux restaurations sont comparées aux sources35 avant/après sauvegarde :
**579/630 tables,523/574 séquences,32/29 entrées de volume**, tous les octets,
modes et propriétaires,51/50 comptes et leurs droits/MFA. Un compte MFA actif
par SIS passe un vrai contrôle TOTP ; aucune connexion utilisateur n'est
effectuée par ces sondes.

Chaque SIS reçoit ensuite deux parcours HTTP natifs sur deux tenants peuplés,
avant puis après recréation réelle de l'API et du proxy. **Dix logins par
parcours**,86 GET métier/288 requêtes HTTP scolaires,84 GET/282 requêtes
universitaires ; zéro retry, aucune commande métier. Les quatre publics,
réponses et résultats privés, révocation, fermeture et refus restent conformes.
Les tables, séquences, fichiers et MFA sont exactement conservés à travers
la recréation avant toute nouvelle connexion.

Après chaque parcours, les anciennes données et permissions sont vérifiées
par empreintes complètes. Seuls les dix `last_login` et les nouvelles lignes
de sessions/logs validées sont admis ; les deux séquences de logs avancent
du nombre exact de connexions. Les premières sessions/logs36 sont comparés
intégralement après le second parcours, y compris leurs autres colonnes.
Les anciens octets/modes/propriétaires restent intacts ; seul `logs/sis.log`
s'enrichit. Les services de qualification ont ensuite été arrêtés.

Les refus initiaux restent rouges et conservés : incompatibilité du pilote de
journalisation Docker avant Python, puis garde PostgreSQL refusant des connexions
avant création de la base universitaire. La restauration scolaire partielle
de cette deuxième tentative n'est ni qualifiée ni réutilisée. Le backend exact
du refus n'a pas été capturé : autovacuum n'est pas une cause prouvée.
La tentativev3 utilise de nouvelles bases/volumes et exige toujours zéro
connexion avant les opérations protégées ; elle n'a nécessité aucune attente.

Preuve parent : `wave36-parent-qualification.json`,297 artefacts hachés,
cutoff **8 novembre2026 à02:45:18.778303 UTC**. L'import documentaire ajoute
ce rapport, soit298 artefacts, et préserve53 updates historiques et93 autres
exigences. Le registre passe à **4/94 exigences vérifiées**.
Qualification locale sur le même cluster privé, pas une mesure RTO de production,
un déploiement partagé, un pilote institutionnel ou une clôture des F-lots.
