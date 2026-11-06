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
