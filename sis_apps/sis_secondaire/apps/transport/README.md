# Trajets scolaires ponctuels

`/api/v1/transport/trajets-scolaires/` gère les trajets datés avec une ligne,
un véhicule et des instants `depart_at`/`arrivee_at`. Lecture et écriture
reprennent exactement la permission des autres ressources transport. Les
créneaux sont des intervalles `[départ, arrivée)` : deux trajets consécutifs
peuvent partager un véhicule, mais deux créneaux qui se croisent ne le peuvent
pas, même sur des lignes différentes. PostgreSQL applique cette règle via une
contrainte d'exclusion et l'extension `btree_gist` installée dans `public`
(la migration nécessite les droits d'installation de cette extension).

Ces affectations ne modifient **ni** `Vehicule.ligne` (affectation habituelle),
**ni** le calcul historique des places d'inscription par ligne. Aucun conducteur
identifiable n'est actuellement modélisé : `Vehicule.chauffeur` est un libellé
libre. Un contrôle des conflits de conducteur exige une identité pérenne
référencée par chaque trajet, ainsi qu'une décision métier sur le partage et
les autorisations de gestion de cette identité. Les horaires des arrêts restent
des modèles non datés, sans pointage de passagers ou service réalisé.
