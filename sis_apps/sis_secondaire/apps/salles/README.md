# Inventaire des équipements des salles

L'API existante `/api/v1/salles/` expose aussi `/api/v1/salles/equipements/`
(`GET`, `POST`) et `/api/v1/salles/equipements/{id}/` (`GET`, `PATCH`, `PUT`,
`DELETE`). Un équipement a un `identifiant` unique dans son établissement, un
`nom` et une `salle` facultative. Pour l'affecter, le déplacer ou le retirer,
envoyer par exemple `{"salle": 12}` ou `{"salle": null}` en `PATCH`. La liste
accepte `?salle=12` ainsi que la recherche par nom ou identifiant.

La lecture exige une authentification ; l'écriture exige le statut
administrateur, comme pour les salles. L'établissement provient du tenant
de la requête ; les équipements et les salles d'un autre établissement ne
sont pas accessibles ou affectables. Ce registre est distinct du champ
historique `Salle.equipements` (liste descriptive) : il ne modifie ni les
capacités ni les créneaux, et ne gère pas les achats ou la maintenance.

## Désactivation réversible des équipements

Le champ `actif` vaut `true` par défaut, y compris pour les équipements déjà
enregistrés. `PATCH {"actif": false}` désactive l'équipement et libère son
affectation actuelle (`salle: null`), sans supprimer sa fiche ni son identifiant.
Une création ou modification combinant `actif: false` et une salle non nulle
est refusée, comme toute affectation d'un équipement déjà inactif.
`PATCH {"actif": true}` permet ensuite de l'affecter à nouveau ; une réactivation
et une nouvelle salle peuvent aussi être envoyées dans la même requête.
La réactivation seule ne restaure jamais automatiquement l'ancienne salle.
La liste conserve les équipements inactifs ; `?actif=false` permet de les filtrer.

Les créations et changements d'état ou de salle effectués par cette API alimentent
le journal `WorkflowEvent` existant, avec l'acteur, le tenant et les états
`avant`/`apres` (activité, identifiant, code et nom de salle). Les modifications
verrouillent la fiche et l'audit est enregistré dans la même transaction.
Une répétition sans changement ne crée pas de nouvel événement. Aucun historique
antérieur à cette évolution n'est reconstitué ; les écritures hors API ne sont
pas auditées ici. Une contrainte de base interdit néanmoins l'association
« inactif avec salle ».

Il s'agit d'une désactivation réversible, pas d'une réforme comptable : ce registre
n'a toujours ni quantités, ni entrées/sorties, ni journal de mouvements de stock,
ni couverture des sept familles de stock.

## Indisponibilité des salles

`/api/v1/salles/indisponibilites/` (`GET`, `POST`) et
`/api/v1/salles/indisponibilites/{id}/` (`GET`, `PATCH`, `PUT`, `DELETE`)
enregistrent une salle, `date_debut`, `date_fin` et un `motif` facultatif.
Les deux dates sont **incluses** et couvrent des **journées entières** ; pour
un seul jour, renseigner la même date deux fois. La liste accepte `?salle=id`.
La lecture exige un compte authentifié de l'établissement ; seules les
personnes administratrices de cet établissement peuvent modifier les plages.
Les créneaux actifs qui se recoupent sont refusés à la création ou à la
modification ; réciproquement, une plage ne peut recouvrir un créneau actif.
Les créneaux ponctuels utilisent `date_specifique` et les créneaux récurrents
le jour de la semaine dans les bornes de l'année scolaire. Faute de référence
calendaire pour les semaines alternées 1/2, toute occurrence possible est
considérée occupée. Les écritures API verrouillent la salle pour éviter les
réservations concurrentes ; les écritures directes en base ne passent pas par
ce contrôle. Aucune opération de maintenance ni modification des créneaux
historiques n'est effectuée.
