# Suivi des stages pratiques

Ce module suit les heures réellement effectuées, les compétences observées en
situation professionnelle et les seuils d'un programme pratique. Il concerne
le secondaire professionnel et le supérieur. Ce guide décrit le fonctionnement ;
il ne constitue pas une attestation de recette institutionnelle ou de production.

Il complète des **conventions existantes**. Il ne remplace pas les circuits
d'offres, candidatures, signatures, recrutement ou soutenance, et ne publie
automatiquement ni note officielle, ni crédit, ni diplôme.

## Préparer l'établissement

Activer `sis.practical_training`, désactivé par défaut, dans la configuration
des modules. Les dépendances `core.identity` et `core.notifications` doivent
rester actives. Attribuer ensuite les permissions aux comptes ou groupes
administrables, puis ouvrir **Stages pratiques**.

| Permission | Usage |
| --- | --- |
| `stages.gerer_suivi_pratique` | Gérer les programmes, ouvrir et clôturer les dossiers, annuler administrativement et révoquer un accès partenaire. |
| `stages.consulter_suivi_pratique` | Consulter les dossiers auxquels le compte est effectivement rattaché. |
| `stages.saisir_heures_pratiques` | Saisir et soumettre des heures sur un dossier auquel le compte est rattaché. |
| `stages.valider_heures_pratiques` | Décider des heures en tant que tuteur effectivement affecté. |
| `stages.evaluer_competences_pratiques` | Évaluer les compétences en tant que tuteur effectivement affecté. |

Un droit de gestion n'autorise pas à valider des heures sans affectation et droit
de validation. L'apprenant ne peut valider ses propres heures ; le tuteur qui a
saisi une ligne ne peut pas valider cette même ligne. Le rôle, `is_staff` et le
portail choisi ne donnent aucun droit implicite. Même un super-utilisateur
doit être local au tenant et respecter les affectations et ces séparations.

Les restrictions facultatives de `permission_scopes` acceptent
`etablissement_id`, `programme_id` et `dossier_id`, sous forme de listes non vides
d'entiers strictement positifs. Sans restriction, ou avec `{}`, une permission
effective s'applique dans le tenant courant, pas dans les autres établissements.
Une restriction fournie invalide, inconnue ou mal typée refuse l'accès.
Une portée limitée à un objet ne peut être ignorée pour en créer un nouveau.

## Conventions et acteurs préalables

Une convention sélectionnable doit être complète, avec date de signature
complète, dates et missions cohérentes, apprenant actif, inscription admissible
dans le cursus concerné et tuteur interne actif. L'année d'inscription doit
couvrir la période. Les conventions historiques incohérentes ne sont pas
corrigées automatiquement.

Au secondaire, le cursus est une classe et l'inscription scolaire correspondante.
Au supérieur, il s'agit d'une formation et d'une inscription administrative
validée ; l'offre et la convention doivent désigner la même formation/entreprise.
Le tuteur interne vient de la convention, pas d'un identifiant libre saisi dans
le formulaire.

Au supérieur, l'éventuel partenaire authentifié est le compte du contact
d'entreprise associé à la convention. Au secondaire, le gestionnaire choisit
explicitement un compte local admissible pour ce dossier. Le nom, le téléphone
ou l'adresse électronique historique du tuteur ne créent jamais une identité.
Une affectation partenaire ne donne pas elle-même de permission.

Si le sélecteur est vide, vérifier ces prérequis dans les modules institutionnels
et l'administration des conventions. Le suivi pratique ne crée pas de convention
ou d'inscription de substitution.

Avant l'ouverture, l'écran indique séparément les habilitations actuelles du
tuteur pour valider les heures et évaluer les compétences. Un tuteur disposant
d'un seul de ces droits reste admissible, mais ne peut pas réaliser seul le
parcours complet. L'avertissement ne crée aucun droit et ne remplace pas le
contrôle des acteurs effectivement affectés à chaque décision.

## Programme et ouverture du dossier

1. Créer un programme pratique lié à une classe ou formation, avec un code,
   un titre, un nombre de minutes requises et les compétences attendues.
2. Publier le programme lorsque ses exigences sont complètes. Chaque compétence
   possède un code stable et un libellé ; toutes doivent être acquises.
3. Sélectionner une convention admissible pour la révision publiée, vérifier
   ses acteurs et sa période, puis ouvrir son dossier pratique.

Une révision publiée est immuable. Pour changer les exigences, créer une nouvelle
révision explicite ; les dossiers existants gardent leur révision et leur
instantané. Archiver une révision empêche les nouvelles ouvertures sur celle-ci
sans réécrire les dossiers engagés.

Une offre académique courante devenue invalide ne doit pas rendre les révisions
historiques illisibles ni empêcher leur archivage. Dans cette situation, la
projection du cursus ne renvoie pas d'offre courante exploitable (`offre: null`) ;
les révisions conservent leur `offre_source` publiée. Une nouvelle publication et
les nouvelles ouvertures restent soumises à la validation de l'offre courante.

Les exigences pratiques sont distinctes de la notation académique : une formation
à notation chiffrée peut garder ce mode tout en utilisant ce programme pratique.
Les heures planifiées de la convention ne sont jamais des heures effectuées.
Les anciens rapports ou évaluations ne deviennent pas des acquisitions validées.

## Saisie, décisions et corrections des heures

Saisir une date, un début, une fin, une pause en minutes entières, une activité
et, si nécessaire, un PDF justificatif privé. La ligne est d'abord un brouillon ;
son auteur la soumet, puis un tuteur habilité la valide ou la rejette.
Seules les lignes **validées** alimentent les minutes accomplies du rapport.

Les heures utilisent le fuseau de l'établissement enregistré à l'ouverture,
pas celui du navigateur. Il s'agit de minutes d'horloge locale, pas d'un calcul
de paie ou de temps légal. Une présence ne peut être future, hors convention,
de durée nulle, inversée ou entièrement absorbée par la pause.

Une ligne reste dans une journée. Pour une présence de 22 h à 2 h, saisir
22:00–24:00 puis 00:00–02:00 le lendemain. Les intervalles touchant un changement
d'heure ambigu sont refusés ; utiliser des intervalles locaux non ambigus.
Un changement du fuseau de l'établissement ne réinterprète pas les lignes déjà
enregistrées et bloque les nouvelles commandes métier sur le dossier concerné,
sans empêcher la révocation d'un accès partenaire.

Les blocages de fuseau, de cursus ou d'acteur sont affichés même lorsque les
liaisons structurelles sont toujours valides. Une absence de bouton d'écriture
ne signifie pas que les données historiques ont été perdues.

Les doublons et chevauchements sont refusés pour le même apprenant, y compris
entre dossiers. Une pause ne crée pas un créneau disponible à l'intérieur d'une
ligne : saisir des intervalles distincts pour des activités séparées.

Le contenu et la pièce d'une ligne ne sont pas écrasés. Une correction crée un
remplacement avec motif ; l'original et les décisions restent dans l'historique.
Une ligne soumise doit d'abord être annulée, une ligne validée doit d'abord être
invalidée par un tuteur habilité. Une pièce ancienne n'est pas recopiée
implicitement sur son remplacement.

## Compétences, rapport et clôture

Le tuteur habilité choisit une compétence du programme, indique si elle est
acquise, décrit la situation professionnelle et date son observation.
Une nouvelle évaluation de cette compétence exige un motif et conserve
l'évaluation précédente avec sa pièce éventuelle.

Le rapport présente les minutes requises, validées et restantes, les autres
états séparément, les compétences acquises et les critères encore manquants.
La dernière révision d'évaluation de chaque compétence fait foi ; les
réévaluations ne multiplient pas les acquisitions.

La clôture réussie est refusée tant que les seuils ne sont pas atteints.
L'annulation administrative est une décision différente, avec motif :
elle ne signifie pas réussite. Ces deux opérations annulent les brouillons
et lignes soumises encore en attente, sans effacer les heures déjà validées.
Les faits métier d'un dossier clos ou annulé ne sont plus modifiables.

## Accès partenaire, pièces et conservation

L'accès accordé par une affectation partenaire est limité à son dossier et
à la période de la convention. Les droits, comptes, affectations et paramètres
du module sont contrôlés de nouveau à chaque requête et téléchargement.

Le gestionnaire peut révoquer cet accès **même après clôture ou annulation**,
avec version et motif. Cette opération modifie uniquement les informations
d'accès, la version et l'audit, pas les heures, compétences, pièces ou décisions
de clôture. Elle ne retire pas un éventuel droit de gestion accordé séparément :
pour retirer aussi ce droit administratif, le révoquer dans les habilitations.

Les PDF sont privés, attachés à leur version d'origine et téléchargés par
une route authentifiée, jamais par une URL publique de stockage.
Conserver ensemble les bases, le stockage privé et les clés cryptographiques
nécessaires aux données historiques. La migration ne déplace pas les anciens
CV ou rapports, ne déduit aucun partenaire de leur contenu et ne rejoue
aucune donnée métier.

Le module n'annonce pas d'envoi de notification, email, SMS ou invitation
externe. Les événements privés ne sont pas rendus accessibles par le
workflow ou la bibliothèque génériques.

## API et conflits

La base est `/api/v1/stages/pratique/`. Les collections principales sont
`programmes/` et `dossiers/`, avec sélecteurs paginés, révisions et historiques.
Sous un dossier : `heures/`, `evaluations/`, `rapport/`,
`competences/{code}/evaluer/`, `clore/`, `annuler/` et `partenaire/revoquer/`.
Le rapport est **JSON** ; aucun certificat ou rapport PDF généré n'est proposé.

Les commandes sont des POST explicites avec version, sans PUT/PATCH/DELETE
générique. Les actions sur les heures et évaluations utilisent la version
globale du dossier. Les créations utilisent la version initiale `0`.
Un envoi multipart contient `payload` (objet JSON encodé en texte) et,
facultativement, un unique `fichier` PDF.

Après un conflit 409, relire le dossier, son rapport et l'historique, puis
confirmer volontairement un nouvel envoi. Ne pas rejouer automatiquement
une écriture ou un upload avec une version actualisée. Un refus d'accès
ne doit pas être interprété comme une liste vide ou un succès.

## Limites du parcours et recette

L'offre de stage et sa candidature existent dans le circuit historique du
supérieur ; au secondaire, le point d'entrée de ce lot est la convention.
Les signatures complètes sont un **prérequis**, pas une signature électronique
réalisée par ce module. Le champ historique `note_soutenance` du secondaire ne
constitue ni une planification de jury ni une soutenance gérée par le suivi
pratique. Le supérieur n'expose pas de route de soutenance dans cette API.
La clôture pratique ne se substitue donc pas à une soutenance institutionnelle.

L'archivage décrit ici est celui d'une révision de programme et la conservation
immuable des dossiers terminés : aucun export d'archivage probant, calendrier de
purge ou certificat PDF n'est généré. Les politiques institutionnelles de
conservation et de soutenance restent à traiter séparément.

La [recette native bornée](practical-training-native-recipe.md) détaille les
prérequis, les commandes de tests ciblées et les résultats à relever par le
superviseur dans un environnement distinct. Sa rédaction ne vaut pas exécution
ni qualification.
