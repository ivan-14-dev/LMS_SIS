# Bibliothèque numérique — guide opérateur du lot37

## Portée et limites

Les SIS **secondaire et supérieur** réutilisent leur catalogue `Livre` et leurs
modèles `Exemplaire`, `Emprunt` et `Reservation`. Aucun second catalogue n'est
créé. La consultation porte sur un fichier local privé ; la circulation reste
celle des exemplaires du catalogue. Télécharger un PDF ne crée pas un prêt.

La licence est une **déclaration du gestionnaire habilité**, accompagnée d'une
référence interne. Le SIS ne vérifie pas juridiquement cette déclaration :
aucune intégration fournisseur, récupération d'URL externe, gestion de sièges
de licence ou DRM n'est ajoutée. Les champs historiques `url_externe` et
`base_donnees` du supérieur restent des métadonnées, pas un service de consultation
externe sous licence.

Une révocation bloque les requêtes suivantes ; elle n'efface pas un fichier déjà
téléchargé et ne reprend pas les octets déjà envoyés. Les contrôles de format
ne constituent ni un antivirus ni une validation exhaustive du contenu PDF.

## Habilitations et établissement

Les requêtes utilisent l'établissement et le schéma PostgreSQL réellement
courants. Un compte d'un autre établissement ne peut pas lire ou modifier les
objets locaux, même si leurs identifiants numériques coïncident.

| Usage | Droit et conditions |
|---|---|
| Consulter le fichier | `bibliotheque.consulter_ressource_numerique`, compte actif, fichier présent dans la référence, licence active et non expirée. |
| Gérer le titre, son fichier et sa licence | `bibliotheque.change_livre` explicite ; également requis pour créer ou supprimer un titre par l'API. |
| Emprunter pour soi | `bibliotheque.add_emprunt` explicite, exemplaire accessible et contrôle du demandeur. |
| Retourner ou renouveler son prêt | `bibliotheque.change_emprunt` explicite, propriété du prêt et transition autorisée. |

**Ni un rôle, ni `is_staff` ne donnent accès au fichier numérique ou à la
modification de sa licence.** Un apprenant, parent ou enseignant peut recevoir
les droits explicites nécessaires sans devenir staff. La consultation ne donne
pas implicitement le droit d'emprunter, de retourner ou d'administrer.

Les contrôles numériques, les écritures `Livre` et les prêts personnels
acceptent les portées ABAC `etablissement_id` et `livre_id`. Une portée inconnue
ou non satisfaite refuse l'action. Une création de titre ne possède pas encore
de `livre_id` : un droit limité à des titres existants ne l'autorise pas.
Les permissions et attributs sont relus par requête pour la consultation,
y compris après retrait dans la même session.

Le catalogue de métadonnées reste lisible par les comptes authentifiés du tenant
selon son contrat antérieur. Limiter la permission numérique à un titre ne masque
pas à lui seul les métadonnées des autres titres.

La **circulation physique** conserve ses habilitations gestionnaires historiques,
avec leurs différences entre variantes, notamment le comportement `is_staff`
antérieur du supérieur. Elles ne constituent pas un droit numérique.
L'API de réservation propre reste accessible à un compte authentifié local ;
la lecture et l'annulation sont bornées au demandeur ou au gestionnaire.

L'interface affiche ses actions selon les capacités explicites : notamment
`add_reservation` pour réserver, `add_reservation` ou `change_reservation` pour
annuler, et `change_livre` pour la gestion/remise. Les droits `view_livre`,
`view_emprunt` et `view_reservation` peuvent donner accès aux vues correspondantes.
Ces choix d'affichage ne remplacent jamais les contrôles serveur.

## Parcours dans l'interface

Routes communes aux profils habilités :

- scolaire : `/secondaire/bibliotheque` ;
- supérieur : `/superieur/bibliotheque`.

Les onglets sont **Catalogue**, **Prêts** et **Réservations**, selon les droits.
L'écran permet de gérer le fichier et la licence de **titres déjà existants** ;
il ne propose pas de création de titre ou d'exemplaire. Leur préparation utilise
l'API du catalogue existant, avec les habilitations correspondantes.

1. Rechercher un titre puis ouvrir sa fiche.
2. Avec `change_livre`, choisir **Gérer le fichier et la licence**, sélectionner
   éventuellement un PDF, saisir la référence et activer la licence. Sans
   nouveau fichier sélectionné, le fichier courant est conservé.
3. Le lecteur habilité utilise **Télécharger le PDF autorisé**. Le téléchargement
   authentifié passe par l'API ; l'indication de disponibilité n'est pas une
   autorisation réutilisable sans contrôle.
4. Choisir **Emprunter un exemplaire** parmi les disponibilités retournées par
   le serveur, puis **Retourner** dans l'onglet Prêts.
5. Le **même lecteur**, sans prêt intermédiaire à un tiers, peut ensuite utiliser
   **Réserver ce titre pour moi**.
6. Dans Réservations, **Ouvrir le titre réservé** permet de revenir au catalogue
   et d'emprunter lorsque sa réservation est prioritaire. Le gestionnaire peut
   également utiliser **Remettre un exemplaire**.

Les durées personnelles sont fixées côté serveur : **14 jours au scolaire,
21 jours au supérieur**, à partir de la date locale du jour. Le formulaire de
prêt personnel ne choisit pas une échéance libre.

## Licence, expiration et téléversement

Les deux variantes exposent les mêmes champs :

| Champ | Contrat |
|---|---|
| `licence_active` | Booléen, faux par défaut. |
| `licence_reference` | Texte de 1 000 caractères maximum ; non blanc obligatoire pour activer la licence. |
| `licence_expire_le` | Date facultative ; `null` signifie aucune échéance enregistrée, pas une validation juridique illimitée. |
| `ressource_numerique` | Fichier privé nullable, téléversable en multipart ; en lecture, URL contrôlée ou `null`. |
| `peut_consulter_ressource` | Booléen calculé par le serveur dans la liste et le détail. |

L'échéance est comparée à la **date locale configurée du service** : la date du
jour est encore valable ; une date antérieure interdit la consultation. Une
licence active dont l'échéance est passée ne suffit donc pas. Désactiver
`licence_active` interdit les prochains téléchargements, sans supprimer le fichier.

Les nouveaux fichiers sont limités au **PDF, 25 Mio par défaut**
(26 214 400 octets). Le validateur partagé
`sis_common.exam_files.validate_exam_copy` contrôle l'extension `.pdf`, le
préfixe `%PDF-`, le type MIME admis et la taille. La limite serveur est
`EXAM_COPY_MAX_SIZE` ; ce paramètre est partagé avec d'autres documents, pas
spécifique à la bibliothèque. Aucune conversion automatique des anciens fichiers
n'est effectuée.

## Contrats API

Préfixe commun : `/api/v1/bibliotheque/`. Les identifiants sont ceux du catalogue
existant. Les commandes exigent l'authentification et le bon contexte tenant.

### Routes communes

| Méthode et suffixe | Usage |
|---|---|
| `GET livres/?search=...` | Catalogue paginé ; recherche notamment titre, auteurs et ISBN. |
| `GET livres/{id}/` | Métadonnées, licence déclarée et capacité de consultation calculée. |
| `GET livres/{id}/exemplaires/` | Exemplaires et disponibilité pour le demandeur. |
| `GET livres/{id}/numerique/` | Octets du fichier après vérification permission/licence. |
| `POST livres/` | Création API d'un titre, notamment `titre` et `auteurs` ; pas de formulaire de création UI ajouté. |
| `PUT/PATCH livres/{id}/` | Modification habilitée ; multipart pour joindre `ressource_numerique`. |
| `DELETE livres/{id}/` | Suppression habilitée, refusée en présence d'historique de prêts/réservations. |
| `GET exemplaires/` ou `GET exemplaires/{id}/` | Consultation des exemplaires ; gestion physique selon les droits historiques. |
| `GET emprunts/` ou `GET emprunts/{id}/` | Prêts propres, ou prêts locaux visibles au gestionnaire. |
| `POST emprunts/` | Prêt personnel minimal : `{"exemplaire": 123}`. |
| `POST emprunts/{id}/renouveler/` | Renouvellement autorisé, au plus deux fois, de 14 jours ; refus si réservation active. |
| `GET emprunts/en_retard/` | Prêts en retard dans le périmètre du demandeur. |

Pour un prêt personnel, `emprunteur` absent désigne le compte courant ; désigner
autrui avec le seul droit `add_emprunt` est interdit. Les dates éventuellement
fournies doivent correspondre à la durée personnelle imposée. Le gestionnaire
conserve le contrat avec `emprunteur`, `date_emprunt`, `date_retour_prevue` et
des dates cohérentes. `PUT/PATCH/DELETE` génériques sur un emprunt sont refusés :
utiliser les actions dédiées, sans injecter de statut ou résultat à la création.

### Retours et réservations : différences conservées

| Action | SIS scolaire | SIS supérieur |
|---|---|---|
| Retour, corps vide | `POST emprunts/{id}/retourner/` | `POST emprunts/{id}/rendre/` |
| Liste/détail réservations | `GET reservations/`, `GET reservations/{id}/` | `GET reservations-bibliotheque/`, `GET reservations-bibliotheque/{id}/` |
| Réserver pour soi, `{"livre": 123}` | `POST reservations/` | `POST reservations-bibliotheque/` |
| Autre action de réservation | — | `POST livres/{id}/reserver/`, corps vide |
| Annuler, corps vide | `POST reservations/{id}/cancel/` | `POST reservations-bibliotheque/{id}/annuler/` |
| Remise gestionnaire | `POST reservations/{id}/fulfil/` avec `exemplaire` et `date_retour_prevue` future | `POST reservations-bibliotheque/{id}/recuperer/` avec `exemplaire` |
| Titre avec copie libre | Réservation initialement `en_attente`, immédiatement honorable si prioritaire | Réservation `disponible` si capacité libre suffisante, sinon `en_attente` |
| Réservation honorée | `honoree`, avec lien vers l'emprunt | `recuperee` |

Une réservation porte sur le **titre**, pas une copie affectée dès sa création.
La priorité suit la date de réservation puis l'identifiant. Un statut
`disponible` ne permet pas de doubler une réservation antérieure.
`POST emprunts/` peut honorer la propre réservation active du demandeur prioritaire :
le prêt et la clôture de la réservation sont enregistrés atomiquement.

Un non-propriétaire ne prend pas la capacité réservée. Le supérieur conserve la
possibilité d'emprunter une capacité réellement excédentaire ; le scolaire
conserve la priorité stricte des réservations actives. Les disponibilités sont
contextualisées pour que le titulaire prioritaire puisse emprunter sa copie libre.
Le scolaire propose aussi `GET livres/disponibles/`.

Erreurs usuelles : 400 pour entrée/transition invalide, doublon ou priorité non
satisfaite ; 401/403 pour authentification/habilitation insuffisante ; 404 pour
objet hors périmètre, fichier autorisé absent ou chemin média invalide ; 405 pour
mutation générique interdite une fois les gardes d'accès passées.

## Concurrence et conservation des historiques

Les commandes HTTP de circulation utilisent des transactions et un verrou commun
sur `Livre`, puis les verrous nécessaires sur exemplaire/emprunt. Elles vérifient
l'occupation et la file avant d'écrire. Deux demandes ne peuvent ainsi créer deux
prêts concurrents sur la même copie par ces chemins ; un non-propriétaire
concurrent ne peut prendre la copie réservée au demandeur prioritaire.

Les états historiques occupant une copie, dont les prêts perdus et en retard
et les prêts renouvelés au supérieur, ne sont pas assimilés à une disponibilité.
Un retour rejoué est refusé. Un exemplaire avec historique de prêts ne peut être
supprimé ou changé de titre ; les prêts/réservations clos ne sont pas effacés par le cycle.

**Ce verrouillage n'est pas une contrainte SQL universelle sur les prêts actifs.**
Aucun index d'unicité nouveau ne normalise les éventuels doublons historiques.
Les écritures SQL/ORM directes et les outils externes ne bénéficient pas
automatiquement des contrôles des commandes HTTP.

## Stockage privé et reverse proxy

Les nouveaux fichiers utilisent `PrivateLibraryStorage`, qui réutilise
`PrivateExamStorage` et la racine **existante** `PRIVATE_EXAM_STORAGE_ROOT`.
Dans la distribution Docker :

- racine privée : `/data/private_exam_copies` ;
- nom nouveau : `bibliotheque/numerique/<schema_name>/<uuid>.pdf` ;
- anciens médias : `MEDIA_ROOT=/data/media`.

Les API et workers montent déjà le volume `/data` de leur variante. Aucun nouveau
volume ou secret bibliothèque n'est nécessaire. Hors de cette distribution,
configurer explicitement des racines persistantes ; ne pas compter sur la couche
éphémère de l'image ou un répertoire sous `/app`.

Au supérieur, le nom du `FileField` antérieur est conservé. Si le fichier n'est
pas trouvé dans la racine privée, le stockage peut lire localement l'ancien nom
relatif sûr sous `MEDIA_ROOT/bibliotheque/numerique/`. **La migration ne déplace,
ne renomme et ne supprime aucun octet.** Un remplacement explicite change la
référence courante, sans purge automatique des anciens octets.

Le champ fichier ne fournit plus d'URL publique. L'endpoint numérique et les
anciennes URLs `/media/bibliotheque/numerique/*` contrôlent tous deux le tenant,
la permission et la licence avant ouverture. Une ancienne URL sans référence
`Livre` courante est refusée ; si plusieurs titres partagent ce nom, leurs
déclarations doivent toutes autoriser cet accès.

Les chemins comportant une composante vide, `.` ou `..`, ou un antislash, sont
refusés avant tout fallback média, y compris après décodage de segments encodés.
Cela interdit notamment les alias `../media/bibliotheque/numerique/...` en
mode DEBUG. Les médias ordinaires canoniques gardent leur comportement antérieur.
Une réponse autorisée utilise `Cache-Control: private, no-store`,
`X-Content-Type-Options: nosniff` et un téléchargement en pièce jointe.

Le reverse proxy livré transmet les requêtes à Django, **sans alias ni serveur
statique exposant `MEDIA_ROOT` ou la racine privée**. Conserver cette propriété :
un montage public direct contournerait les contrôles applicatifs.

## Migration et reprise

- supérieur : `bibliotheque.0003_digital_library`, après `0002_initial` ;
- scolaire : `bibliotheque.0004_digital_library`, après `0003_reservation_hold`.

Les migrations ajoutent les trois champs licence, le fichier au scolaire et les
paramètres de stockage/validation du fichier supérieur. `Meta.permissions` et
`post_migrate` créent normalement la permission Django de consultation.
Aucun groupe, droit direct, rôle, indicateur staff ou licence n'est attribué
automatiquement.

Les comptes ordinaires n'acquièrent donc aucun droit. Le superutilisateur global
**déjà existant** conserve la sémantique Django : sa liste effective de toutes
les permissions inclut naturellement la nouvelle permission. Ne pas interpréter
cette différence attendue comme une nouvelle affectation à un groupe ou compte
ordinaire ; ne pas créer un superutilisateur pour ouvrir la bibliothèque.

Les anciens fichiers sans déclaration explicite deviennent volontairement
**non consultables jusqu'à configuration**. Avant migration, sauvegarder noms,
empreintes des fichiers, catalogue et historiques ; après migration, contrôler
leur conservation avant de déclarer les licences et d'accorder les droits.

Pour la sauvegarde/restauration, utiliser `scripts/sis_backup.py` et la procédure
[Exploitation et restauration](INSTALLATION_ETABLISSEMENT.md#exploitation-et-restauration),
complétée par [BACKUP_RESTORE.md](BACKUP_RESTORE.md). Conserver ensemble :

1. la base PostgreSQL entière de chaque variante, schéma `public` et tenants ;
2. le volume `/data`, incluant **à la fois** anciens médias et stockage privé ;
3. la configuration et la **clé `FIELD_ENCRYPTION_KEY` existante**, nécessaire
   notamment aux données chiffrées/MFA antérieures, sans rotation lors de la reprise ;
4. les secrets nécessaires au dépôt de sauvegarde chiffré, protégés séparément.

La bibliothèque n'ajoute pas de clé et ne chiffre pas automatiquement les PDF
dans leur stockage local. Les scripts historiques ne sauvegardant que la base
ou `MEDIA_ROOT` ne suffisent pas pour les nouveaux fichiers privés.
En installation personnalisée, inclure toutes les racines réellement configurées
dans la même fenêtre de sauvegarde cohérente.

Restaurer sur des bases et volumes indépendants et vides, jamais par-dessus
l'installation en service. Comparer les lignes, droits, MFA et octets **avant
les connexions de vérification**, qui modifient légitimement les sessions et logs.
Contrôler ensuite téléchargements autorisés/refusés, ancien média, révocations,
expiration, isolation des tenants et cycle de circulation. Une recréation de
service avec le même volume n'est pas une preuve de restauration indépendante.

## Point de qualification du lot37

Le 8 novembre 2026, le lot37 a été qualifié sur l'image
`sha256:c7815bb7f5f86f442c312c2521c031bb5c0add29ba35f0a9cea466ef593f8e2e` :
**22 tests backend scolaires et 23 supérieurs**, 41 tests frontend principaux
et 89 tests Workspace, sans recompter les huit cas Workspace ciblés antérieurs.
Les contrôles de style et le build passent ; les trois avertissements de taille
du bundle restent consignés. Il ne s'agit pas de suites intégrales du produit.

Dans chaque SIS, Chromium réel couvre le gestionnaire non staff et le lecteur :
fichier/licence, recherche, téléchargement exact, emprunt, retour et réservation
par le même lecteur. Le second établissement est exercé par HTTP natif,
avec identifiants collisionnants, refus inter-tenant et rejeux de cookies.
Les refus sans droit/licence, la révocation sans reconnexion, les mutations
génériques interdites et deux demandes de prêt concurrentes sont vérifiés.

Les migrations et recréations des sources préservent les anciennes données.
De vrais dumps et archives sont ensuite restaurés dans **deux nouvelles bases
et deux nouveaux volumes**, comparés avant toute connexion : 579/630 tables,
523/574 séquences, 71/70 comptes, droits, MFA/TOTP et 41/42 entrées de volume.
Chaque restauration est rouverte, puis ses API/proxy sont réellement recréés
et rouverts à nouveau. Toutes les données métier et colonnes des comptes restent
identiques, sauf `last_login` des sept acteurs reconnectés ; seuls leurs nouveaux
enregistrements de session et de connexion sont ajoutés. Les fichiers et les
préfixes physiques des journaux sont conservés.

Les essais refusés restent archivés : recherche témoin ambiguë du premier
scénario, puis restauration v2 interrompue par un autovacuum PostgreSQL.
Les succès utilisent de nouvelles cibles, sans transformer ces essais en succès.
La restauration qualifiée reste sur le même cluster privé : elle ne prouve
ni reprise hors site, ni RTO de production.

Ces preuves permettent de vérifier **10.3 dans son périmètre déclaré** dans la
[matrice de recette](functional-acceptance-matrix.json). Elles ne clôturent pas
les lots globaux IAM, campus, import/export ou le programme institutionnel.
