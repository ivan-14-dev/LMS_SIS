# Rectifier un bulletin calculé publié

## Périmètre et prérequis

Ce circuit concerne les **bulletins secondaires issus de `preparer`**, calculés
à partir de notes numériques et déjà publiés. Il ne modifie jamais la ligne du
bulletin original, ses notes figées, sa décision, ses dates ou sa validation.
Chaque rectification crée une nouvelle ligne, avec son propre identifiant PDF.
La migration secondaire `notes.0008_bulletin_rectifications` est nécessaire.

L'existant universitaire a été examiné avant cette extension : les moyennes
ECUE/UE ne sont pas un registre de versions de bulletins ; le workflow des
examens dispose de vérification, validation, publication et réouverture,
avec groupes et fenêtre de correction configurables. Cette réouverture
travaille sur la même ligne et n'est donc pas réutilisée comme mécanisme
d'archivage de versions immuables. Aucun circuit d'examen n'est modifié ici.
Les événements de workflow, permissions, visibilité, calcul et contrôle
financier déjà présents sont réutilisés, sans nouvelle politique nationale.

## Parcours gestionnaire

1. Corriger les notes sources par leur circuit autorisé, lorsque nécessaire.
   Une rectification peut aussi porter uniquement sur une décision ou
   appréciation humaine : il n'est pas obligatoire de changer une note.
2. Dans **Documents → Bulletin → Vérifier le bulletin**, consulter l'original,
   saisir un **motif de rectification** puis choisir **Créer une rectification**.
3. Le nouveau brouillon affiche le bulletin qu'il rectifie et son numéro de
   révision. Notes et coefficients sont recalculés depuis les sources courantes.
   Décision, appréciation, validation, signature et publication repartent à vide.
4. Vérifier les sources, saisir l'appréciation/décision et choisir **Valider
   après vérification**, puis **Publier le bulletin**. Tout changement de source
   entre ces étapes impose un recalcul et une nouvelle validation humaine.
5. Après publication, la famille voit les deux versions. La fiche de l'original
   indique sa rectification publiée ; la nouvelle version référence l'original.
   Le PDF rectificatif mentionne révision, référence précédente, motif et date
   de validation. Les révisions publiées restent consultables ; aucun écrasement.

Il faut les permissions explicites `notes.view_bulletin`,
`notes.change_bulletin` et `notes.add_bulletin`, dans les périmètres classe,
année et période concernés. Un rôle de direction seul ne suffit pas.
La validation et publication conservent leurs contrôles explicites ; le contrôle
financier configuré s'applique également à la nouvelle publication.
La validation humaine est renouvelée, mais aucun deuxième acteur distinct
n'est imposé par ce protocole.

## Contrat API et reprises

Les deux routes montées `/api/v1/bulletins/` et `/api/v1/notes/bulletins/`
exposent la même action :

```http
POST /api/v1/bulletins/42/rectifier/
Content-Type: application/json

{
  "version": "2026-11-09T15:00:00Z",
  "motif": "Erreur de transcription corrigée après vérification.",
  "cle_idempotence": "c99be92c-bfcc-4c86-a4fa-2a194da04f58"
}
```

`version` est exactement le `updated_at` renvoyé pour le bulletin publié.
La réponse `201` contient le nouveau brouillon. Une reprise avec la même clé
UUID, le même original, la même version et le même motif renvoie `200` et
la version déjà créée, sans nouvel événement ni nouvelle création, même
si elle a ensuite été validée/publiée. La clé est limitée à cet original ;
elle n'est pas une clé globale inter-bulletins. Elle n'est pas exposée aux lecteurs.
Le client conserve la clé après une erreur réseau tant que le motif est inchangé.

Un seul successeur est autorisé par version. Une demande différente sur un
original déjà rectifié retourne `409` : retrouver le brouillon dans la liste
ou consulter la rectification publiée, plutôt que créer une branche.
Une troisième version doit rectifier la deuxième après sa publication.
Un motif vide, une clé absente/invalide, un brouillon ou un bulletin historique
non calculé donnent `400`. Une version périmée ou une source occupée donne `409`.
Les verrous de bulletin et sources sont `NOWAIT` : aucun calcul n'attend
un rédacteur concurrent. Les modifications génériques et la suppression
d'un brouillon rectificatif sont refusées pour conserver sa provenance.

Le détail expose `revision`, `rectifie`, `motif_rectification`,
`rectification_demandee_par` et `rectification_publiee`.
La liste expose les références et la révision. `rectification_publiee` reste
nul tant que le successeur n'est pas publié. L'événement de création n'est
enregistré que sur le brouillon privé ; l'historique original ne signale la
rectification qu'à sa publication. Les permissions famille et les liens
tuteur autorisés restent ceux de `visible_bulletins`, y compris pour le PDF.

## Validation centrale

Commandes à exécuter **uniquement dans le runner PostgreSQL/Redis isolé du
superviseur**, avec les variables d'environnement de ce runner :

```sh
cd sis_apps/sis_secondaire
python manage.py makemigrations notes --check --dry-run
python manage.py test apps.notes.tests.test_bulletin_calculation \
  apps.notes.tests.test_bulletin_visibility apps.notes.tests.test_api --noinput
```

Les tests `BulletinConcurrencyTests` ouvrent réellement une seconde connexion
PostgreSQL et vérifient le refus immédiat des verrous sur l'original et une
évaluation, sans version partielle, puis la reprise idempotente.

```sh
cd sis_apps/frontend-app-sis
NODE_OPTIONS=--max-old-space-size=768 npm test -- --runInBand --coverage=false \
  --watch=false --runTestsByPath src/documents/SchoolBulletinWorkflow.test.jsx
```

La migration donne la révision 1 aux bulletins existants et conserve leurs
identifiants. Après création de révisions, revenir à l'ancienne contrainte
unique élève/période n'est plus possible sans traitement des données :
ne pas supprimer les rectifications pour forcer un retour arrière.

## Limites conservées

- Absence, non-rendu, triche ou note manquante restent bloquants ; aucune
  conversion implicite en zéro. Aucune politique configurée de substitution
  n'a été identifiée dans le protocole de calcul utilisé.
- Compétences, parcours individuels, compensation, rang, crédits, passage,
  redoublement, diplôme et décision de jury ne sont pas calculés ici.
- Aucun circuit de rectification d'examens ou de résultats universitaires
  n'est annoncé livré par ce changement.
- Les données académiques du PDF restent celles de la version ; le moteur
  génère encore le PDF à la demande avec l'identité actuelle de l'établissement.
  Ce n'est pas un stockage binaire immuable ni une signature cryptographique.
- Un brouillon rectificatif n'est pas annulable/supprimable par cette API ;
  il peut être recalculé, puis validé et publié, sans modifier son motif initial.
- Rien n'est déployé par ces changements. Les validations exécutées sont
  rapportées séparément des sélecteurs ci-dessus.
