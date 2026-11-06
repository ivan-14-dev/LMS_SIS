# Consentement alumni

`/api/v1/diplomes/alumni/consentement/` est réservé au compte étudiant de
l'établissement courant. `GET` retourne son éligibilité, son consentement actif,
sa révision et les dates du consentement/retrait ; aucune coordonnée n'est
publiée ni acceptée. Une délivrance doit être signée, munie d'un QR, obtenue
dans cet établissement et non révoquée pour établir l'éligibilité. Le statut
déclaré de l'étudiant ne suffit pas.

`POST` exige `{"consentement": true, "revision": 0}` (la révision courante
obtenue avec `GET`). `DELETE` exige `{"revision": 1}` pour retirer l'accord,
même si le diplôme a été révoqué depuis. Un retrait ne supprime pas sa trace.
Les révisions obsolètes renvoient 409, sauf le rejeu immédiat de la même
opération. Après retrait, seul un nouvel accord à la révision courante peut
réactiver le consentement. Les réponses privées ne doivent pas être mises
en cache.

La scolarité peut révoquer une délivrance signée via
`POST /api/v1/diplomes/{id}/revoquer/` ; la signature et son horodatage restent
conservés, mais la vérification et l'éligibilité alumni deviennent invalides.
Avant signature, la scolarité peut corriger une délivrance ; après signature,
ses données ne peuvent plus être modifiées par l'API CRUD, y compris après
révocation. La révocation passe exclusivement par l'action dédiée.
Ce consentement ne constitue pas un annuaire public ni un suivi d'emploi.
