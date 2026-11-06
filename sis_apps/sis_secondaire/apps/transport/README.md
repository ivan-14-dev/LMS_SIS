# Trajets scolaires ponctuels

`/api/v1/transport/trajets-scolaires/` gère les trajets datés avec une ligne,
un véhicule et des instants `depart_at`/`arrivee_at`. Lecture et écriture
reprennent exactement la permission des autres ressources transport. Les
créneaux sont des intervalles `[départ, arrivée)` : deux trajets consécutifs
peuvent partager un véhicule, mais deux créneaux qui se croisent ne le peuvent
pas, même sur des lignes différentes. PostgreSQL applique cette règle via une
contrainte d'exclusion et l'extension `btree_gist` installée dans `public`
(la migration nécessite les droits d'installation de cette extension).

`/api/v1/transport/chauffeurs/` expose le CRUD des identités de conducteurs
(`id`, `nom`, `telephone`). Le référentiel réside dans le schéma de chaque
établissement ; il n'est pas partagé entre établissements. Le compte doit
appartenir au locataire courant. Pour protéger les coordonnées du personnel,
la lecture exige `transport.view_chauffeur` ou l'autorisation de gestion
existante du module transport ; un élève sans habilitation reçoit une erreur
403, y compris sur le détail. Les écritures restent réservées aux gestionnaires
transport : le seul droit de lecture ne les autorise pas. Deux homonymes
peuvent avoir des identités distinctes ; changer un nom ne change pas l'identité.

Un trajet peut référencer un `chauffeur` par son identifiant, ou laisser cette
référence à `null`. PostgreSQL interdit les créneaux qui se croisent pour une
même identité, même avec des véhicules et lignes différents. Les créneaux
adjacents restent permis. Créations et modifications renvoient une erreur 400
sur `chauffeur` en cas de conflit. Un conducteur encore référencé ne peut pas
être supprimé (400) ; aucune suppression ne détache silencieusement les trajets.

La migration `0003` ajoute le référentiel vide, la référence facultative et une
contrainte d'exclusion limitée aux références non nulles. Elle réutilise
`btree_gist` installé par `0002` et doit être appliquée aux schémas locataires
avant de déployer le code API. Aucun rapprochement automatique des noms ni
aucune identité ne sont créés pour les données antérieures. Les anciens clients
peuvent toujours omettre `chauffeur` ; les trajets existants restent sans
référence tant qu'une affectation explicite n'est pas faite.

Ces affectations ne modifient **ni** `Vehicule.ligne` (affectation habituelle),
**ni** les libellés libres `Vehicule.chauffeur` et `telephone_chauffeur`,
**ni** le calcul historique des places d'inscription par ligne. Le contrôle
des conducteurs ne couvre que les trajets datés portant une référence :
les textes libres et les horaires non datés des arrêts restent inchangés,
sans pointage de passagers ou service réalisé.
