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
