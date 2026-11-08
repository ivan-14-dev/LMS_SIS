# Agenda institutionnel — utilisation et contrat

Contrat identique dans les SIS secondaire et supérieur, sous
`/api/v1/core/evenements/`. Ce document décrit l'interface et le contrat, pas une
attestation de recette navigateur ni une qualification de l'image finale.

## Utilisation dans les portails

Après activation du module et attribution des droits ci-dessous, ouvrir
**Événements institutionnels** : `/secondaire/evenements` ou
`/superieur/evenements`. L'entrée est disponible dans les portails Staff et
Étudiant selon les permissions effectives ; le portail seul n'accorde aucun droit.

Le gestionnaire choisit une période d'agenda, puis crée un événement en renseignant
son type, ses horaires, une salle existante, l'effectif total et les participants.
La présence d'une salle dans le sélecteur ne garantit pas sa disponibilité :
le serveur vérifie les conflits lors de l'enregistrement. Le participant invité
et habilité consulte ses événements, sans accès à la liste nominative des invités
ni aux commandes de gestion.

**Vérifier le décalage UTC de chaque borne.** L'interface affiche séparément
l'heure locale et le décalage `±HH:MM` ; elle ne recalcule pas automatiquement
ce décalage lors d'un changement de date ou d'heure d'été. Pour la France
métropolitaine, utiliser `+01:00` en hiver et `+02:00` en été. Les deux bornes
peuvent avoir des décalages différents.

Ouvrir un événement pour modifier son horaire, sa salle ou ses invitations.
Retirer une personne de la sélection retire son invitation. L'annulation demande
confirmation, libère la salle et reste définitive. Pour lire les notifications
internes, ouvrir **Notifications internes**, puis **Notifications récentes**
dans le centre de workflows. Aucun courriel ni SMS n'est envoyé par ce module.

Si une modification concurrente rend la version obsolète, le formulaire conserve
le brouillon sans le renvoyer automatiquement. Relire la version serveur, comparer
les horaires et **toute la liste des invitations**, puis confirmer explicitement.
Si le résultat d'une commande est incertain, fermer le formulaire et actualiser
l'agenda avant une nouvelle opération ; ne pas supposer que la première a échoué.

## Activation et habilitations

Le module administrable `sis.events` est **désactivé par défaut**. Son activation
ne donne aucun droit et ne change aucun compte, groupe, rôle ou paramètre MFA.

- `core.gerer_evenement_institutionnel` : créer, consulter et organiser les
  événements dans le périmètre explicitement attribué.
- `core.consulter_evenement_institutionnel` : consulter seulement les événements
  auxquels le compte possède une invitation non retirée. Ce droit seul ne donne
  accès ni aux sélecteurs ni à la liste nominative des invités.

Les contrôles utilisent le tenant et le schéma courants et un compte actif,
rechargé à chaque requête. Aucun accès implicite par rôle ou `is_staff`.
Le super-utilisateur conserve la sémantique du moteur de permissions existant,
mais doit lui aussi appartenir au tenant courant.

Les deux permissions acceptent les portées ABAC `etablissement_id` (entier),
`evenement_id` (UUID canonique sous forme de chaîne) et `salle_id` (entier).
Une portée inconnue ou mal typée refuse l'accès ; les chaînes numériques ne sont
pas converties en identifiants entiers. La création nécessite un droit applicable
sans identifiant d'événement ni de salle préexistants dans le contexte :
utiliser un droit global au tenant pour créer, puis un droit limité pour
organiser un événement existant. Les restrictions sont appliquées aux listes,
détails, mutations, capacités et notifications. Changer de salle nécessite
également l'autorisation sur la destination.

Retirer une invitation, un droit ou désactiver son groupe rend le retrait
opposable dès la prochaine requête, sans reconnexion. L'historique d'invitation
est conservé, mais les notifications liées ne sont plus visibles. Les événements
sont exclus des historiques/exports de workflow généraux. Aucun export autonome
de l'agenda n'est exposé.

## Parcours et API

Types : `conference`, `examen`, `reunion`, `ceremonie`, `activite`.
Statuts : `planifie`, `annule`. La création réserve immédiatement la salle ;
il n'existe pas de brouillon ni de workflow générique. L'annulation libère la
réservation, conserve l'historique et est définitive.

### Commandes

`POST /api/v1/core/evenements/`, réponse **201** :

```json
{
  "titre": "Conférence institutionnelle",
  "description": "Accueil des participants",
  "type": "conference",
  "salle": 12,
  "debut": "2027-03-08T10:00:00+01:00",
  "fin": "2027-03-08T11:00:00+01:00",
  "effectif": 20,
  "participants": [31, 32]
}
```

Le titre est limité à 200 caractères, la description à 5 000 et les participants
à 200 comptes actifs distincts du tenant. La liste peut être vide. L'effectif
total déclaré doit être positif, inclure tous les invités et rester inférieur ou
égal à la capacité de la salle ; l'organisateur n'est pas ajouté implicitement.
Les personnes sans compte peuvent être comptées dans l'effectif, sans invitation
ni visibilité dans le SIS. Les dates ISO 8601 exigent un fuseau explicite.
La durée est strictement positive et limitée à sept jours.
Ces bornes et celles du calendrier sont comparées en UTC, y compris lorsque
les heures affichées reculent au changement d'heure.
Une réponse de commande peut conserver le décalage fourni, tandis qu'une
relecture exprime le même instant en UTC (`Z`). Les clients doivent comparer
les instants, pas l'égalité textuelle des dates ; la relecture fait foi pour
la version et l'état enregistrés.

`POST {id}/modifier/`, réponse **200** : même corps **complet**, augmenté de
`"version": 1`. Cette commande sert à modifier l'horaire, la salle et/ou les
invités atomiquement. La liste remplace la sélection active ; les absents sont
révoqués et un compte réinvité réactive son invitation.

`POST {id}/annuler/`, réponse **200** : `{"version": 2}`.

Chaque mutation réussie incrémente la version (création : 1). Une version
obsolète ou la modification/annulation d'un événement annulé retourne **409**
avec `detail`. `PUT`, `PATCH` et `DELETE` ne sont pas exposés (**405** après les
gardes). Les champs inconnus, notamment `statut`, sont refusés (**400**).

### Lectures et sélecteurs

| Route GET | Réponse |
|---|---|
| `?debut=...&fin=...` | Calendrier filtré, intervalle obligatoire d'au plus 93 jours ; événements recoupant `[debut, fin[`, annulés compris. |
| `{id}/` | Détail autorisé ; objet invisible : **404**. |
| `capacites/` | `can_create`, `can_manage`, `can_consult`, `types`, `statuts`, `notifications: "internes"`. |
| `salles/` | Catalogue existant minimal : `id`, `code`, `nom`, `capacite`. Ce n'est **pas** une assertion de disponibilité. |
| `participants/?q=...` | Recherche de 2 à 100 caractères sur nom/prénom/identifiant, réponses minimales `id`, `nom`, sans courriel ni rôle. |

Les collections sont paginées : `count`, `next`, `previous`, `results` ;
`page` et `page_size` (50 par défaut, au plus 100). L'ordre de l'agenda est
`debut`, puis `id`. Un gestionnaire limité à un événement fournit
`evenement_id={uuid}` aux sélecteurs ; sans cet argument, le droit de création
est requis. Les sélecteurs ne nécessitent aucun droit administratif global sur
les utilisateurs ou les salles.

Chaque événement retourné contient : `id` UUID, `titre`, `description`, `type`,
`statut`, `debut`, `fin`, `salle` (objet minimal), `effectif`, `version`,
`can_manage`. Le détail ajoute `participants: [{"id": 31, "nom": "..."}]`
uniquement pour les gestionnaires autorisés. La liste n'expose jamais les invités.
`can_manage` de `capacites/` signifie qu'au moins un événement actuellement
existant est gérable ; `can_create` permet d'ouvrir un agenda encore vide.

Erreurs de domaine **400** : `effectif` (capacité ou effectif insuffisant),
`salle` (conflit ou disponibilité incertaine), `participants` (compte étranger,
inactif, dupliqué ou liste invalide), `debut`/`fin` (date ou durée), `detail`
(champs inconnus). Salle inconnue/étrangère : **404**. Permission/tenant/module :
**403** ; authentification absente : **401/403**, selon l'authentificateur.
Les erreurs techniques ne sont pas converties en succès.

## Occupation des salles

Les événements utilisent les salles **existantes** : `salles.Salle` au secondaire,
`emplois_du_temps.Salle` au supérieur. Aucun catalogue supplémentaire n'est créé.
L'événement constitue sa réservation, sans recopier une réservation historique.
Deux intervalles se recoupent si `debut < autre_fin` et `fin > autre_debut` ;
les bornes contiguës sont donc admises. Les heures historiques sans fuseau sont
interprétées dans le fuseau configuré du SIS (`Europe/Paris` actuellement).
Les comparaisons d'instants et les durées en minutes des épreuves/soutenances
s'effectuent en UTC : une durée physique ne varie pas au changement d'heure.
Les jours et récurrences restent locaux. Une plage dont l'heure de fin est
inférieure ou égale à celle de début finit le lendemain ; les occurrences
hebdomadaires commencées la veille sont également vérifiées.

Les anciennes heures sans décalage ne permettent pas de distinguer les deux
occurrences d'une heure répétée, ni de résoudre une heure inexistante. Par
prudence, les deux interprétations de décalage sont contrôlées. Pour une épreuve,
chacune conserve exactement sa durée en minutes ; aucun enregistrement historique
n'est corrigé ou prolongé. Il peut donc subsister un refus conservateur autour
de ces heures ambiguës.

Sources prises en compte :

| Secondaire | Supérieur |
|---|---|
| Événements institutionnels planifiés | Événements institutionnels planifiés |
| `IndisponibiliteSalle` : jours entiers, bornes inclusives | Salles marquées `disponible=False` |
| `Creneau` actif, date spécifique ou jour de semaine pendant l'année scolaire | `CreneauCours`, jour de semaine pendant les dates du semestre |
| `Contrainte` de type `indispo_salle` (jour/heures, sinon journée entière) | `Reservation` confirmée (les demandes en attente ne réservent pas) |
| Épreuves : salle principale et salles de convocations, date et durée | Épreuves : lieu et salles de convocations, date et durée |
| Séances de club via `Club.salle`, études surveillées d'internat | Jurys non annulés (journée entière : aucune durée dans le modèle) |
| | Soutenances non annulées, date et durée |
| | Réservations des salles de travail de bibliothèque |

Les alternances de semaines/fréquences historiques ne possèdent pas de repère
commun daté fiable. **Par prudence, le jour hebdomadaire est occupé pendant toute
la période**, même si une alternance aurait pu libérer cette semaine.

Les lieux historiques libres sont rapprochés par égalité, après trim et sans
casse, avec code, nom ou représentation de la salle. Les noms ambigus occupent
toutes les salles correspondantes. Un lieu non vide **non résolu occupe toutes
les salles pendant son intervalle** : il ne permet jamais d'annoncer une salle
libre par omission. Cela concerne aussi le catalogue préexistant des salles de
travail de bibliothèque, sans lien structurel avec les salles de cours.
Un lieu vide ne désigne aucune salle. Les conseils de classe/discipline sans
champ de salle ne constituent pas une réservation de salle.

Ce choix conservateur peut refuser un créneau réellement disponible. L'opérateur
doit alors corriger le libellé historique vers une référence existante ou choisir
un autre créneau ; le système n'invente aucune correspondance. Aucun ancien
événement, rôle ou historique n'est réécrit automatiquement.

Au supérieur, le contrôle historique
`GET /api/v1/edt/salles/{id}/disponibilite/?date=...&heure_debut=...&heure_fin=...`
réutilise ces mêmes sources pour son booléen `disponible`. Il ne retourne aucun
détail d'événement privé ; sa liste historique `conflits` reste limitée aux
réservations confirmées.

## Atomicité, notifications et limites

L'ordre commun est : verrou consultatif du schéma, puis verrous de lignes
(objet, salle et parents académiques). Les transactions HTTP historiques et
les serializers prenant des verrous de lignes acquièrent ce verrou consultatif
avant ces lignes, même lorsque `sis.events` est désactivé. Les parents partagés
sont bornés au tenant dans ces API ; une sauvegarde ORM transférant un parent
entre tenants conserve l'acquisition des schémas concernés dans l'ordre trié.
Tout appelant ORM ajoutant ses propres verrous doit respecter ce même ordre
avant de sauvegarder un modèle protégé ; `save()` ne peut pas réordonner des
verrous déjà acquis par un appelant externe.

Un verrou transactionnel PostgreSQL commun, propre au schéma, sérialise les
créations, changements de salle/horaire et écritures des sources d'occupation.
Les sauvegardes des sources et de leurs parents temporels/lieux sont protégées
pour ne pas déplacer indirectement un événement réservé. Les verrous de salles
historiques concernés restent des verrous non-clés, compatibles avec les clés
étrangères du nouvel agenda.
La suppression ordinaire d'une salle/bâtiment est aussi contrôlée lorsqu'elle
rendrait un lieu historique non résolu et donc incompatible avec une réservation.

La transaction de commande comprend événement, invitations, audit
`WorkflowEvent` et notifications `WorkflowNotification`. Échec de conflit,
capacité, audit ou notification : **aucune écriture partielle**. Les modifications
parallèles du même événement sont également protégées par sa version.

Les notifications sont **internes uniquement**, sans promesse SMTP. Tous les
invités actifs restants reçoivent une notification générique lors d'une création,
modification ou annulation. Aucun titre privé, horaire ou liste nominative n'est
recopié dans son texte ; sa lecture réapplique les permissions et invitations
actuelles. Aucun système parallèle de notifications n'est ajouté.

Le verrou couvre les commandes HTTP et les sauvegardes ORM ordinaires des sources
intégrées. Les imports externes, `QuerySet.update`, `bulk_create` et SQL directs
ne constituent pas des commandes de réservation et ne bénéficient pas de ce
contrôle universel. Il ne s'agit pas d'une contrainte SQL d'exclusion entre tous
les domaines. Les anciens conflits entre sources spécialisées, indépendants du
nouvel agenda, ne sont ni réparés ni normalisés par ce lot.
