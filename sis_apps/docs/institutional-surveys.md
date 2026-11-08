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
parents et tout profil déjà configuré dans l'établissement. Les modèles existants
ne définissent pas de rôle partenaire natif : cet incrément ne crée ni rôle,
ni compte partenaire, ni accès pour des partenaires externes non authentifiés.
Il ne constitue donc pas une recette des quatre publics effectivement présents.

Limites : 1–20 questions obligatoires, texte libre de 2 000 caractères ou choix
unique parmi 2–10 options distinctes de 120 caractères ; 1–200 destinataires.
Pas de questionnaire conditionnel, question facultative, choix multiple, pièce
jointe, réponse modifiable, réouverture, export, anonymat ou campagne automatisée.
L'analyse comprend les réponses nominatives et les comptages des choix, pas une
analyse statistique avancée. Aucune promotion de statut de recette.

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

**10.12 reste partielle.** Restent le quatrième public partenaire authentifié
et la sauvegarde/restauration indépendante du nouvel incrément. Le clonage
de préparation et la recréation ne remplacent pas cette restauration.
SMTP, export, anonymat non annoncé et statistiques avancées ne sont pas
ajoutés aux critères de réception existants. Pas de pilote institutionnel,
déploiement partagé, nouvelle charge500, contrôle des séquences post-UI ou
validation globale des F-lots. Les suites ciblées ne valent pas suite intégrale.
