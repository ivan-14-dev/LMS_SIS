# Recherche universitaire

Ce module est réservé au SIS supérieur. Il relie laboratoires, projets, équipes,
encadrements, publications, jalons, livrables et suivi financier. Ce guide décrit
le fonctionnement du produit ; il ne constitue pas une attestation de recette
institutionnelle ou de mise en production.

## Activation et droits

Le module `sis.research` est **désactivé par défaut**. L'administrateur active le
module dans la configuration de l'établissement, puis attribue les permissions
aux comptes ou aux groupes administrables. L'activation seule ne donne aucun droit.
Ouvrir ensuite **Recherche**, `/superieur/recherche`.

| Permission | Usage |
| --- | --- |
| `recherche.gerer_recherche` | Administrer les objets et leurs transitions dans le périmètre attribué. |
| `recherche.consulter_recherche` | Consulter les projets auxquels le compte est actuellement rattaché et leurs publications publiées. |
| `recherche.contribuer_recherche` | Contribuer aux projets auxquels le compte est actuellement rattaché. |
| `recherche.comptabiliser_recherche` | Enregistrer les opérations financières, consulter leur journal et leurs justificatifs. |

Attribuer consultation et contribution ensemble à un contributeur qui doit lire
et déposer des livrables. Un doctorant doit également être lié à une thèse active
du projet ; il ne consulte pas les thèses des autres doctorants. Un financier
sans droit académique ne reçoit que les métadonnées indispensables du projet :
ni description scientifique, ni équipe, ni pièces académiques.

Le portail Staff ou Étudiant, le rôle et `is_staff` n'accordent aucun accès implicite.
Les comptes et établissements doivent être actifs et appartenir au tenant courant,
y compris pour un super-utilisateur. Les permissions, affiliations et paramètres
du module sont relus à chaque requête.

Les permissions acceptent les portées `etablissement_id`, `laboratoire_id` et
`projet_id`, avec des identifiants entiers strictement positifs. Une portée
inconnue, mal typée ou vide refuse l'accès. Les sélecteurs sont paginés et limités
au tenant et aux droits effectifs. Un gestionnaire limité à un projet ne peut
pas sélectionner un doctorant encore sans rattachement autorisé : un gestionnaire
habilité à l'échelle de l'établissement doit établir le premier lien.

## Parcours académique

1. Créer un laboratoire, puis un projet avec son responsable, son équipe,
   ses dates, son budget et ses informations de financement.
2. Accepter le projet proposé, puis le démarrer. Définir les jalons et leurs
   échéances ; les contributeurs habilités déposent les livrables PDF privés.
3. Créer les encadrements et les publications liés au projet. Les auteurs et
   encadrants doivent être des personnes autorisées dans ce périmètre.
4. Valider chaque jalon après examen des livrables. Terminer le projet lorsque
   tous les jalons sont acceptés et qu'aucun engagement financier ne reste ouvert.
5. Archiver les objets clos pour conserver leur historique sans permettre
   de nouvelles modifications.

Un projet peut être suspendu, puis repris. Une publication suit le parcours
**brouillon → validée → publiée**, puis peut être archivée. Une pièce jointe est
facultative ; tout fichier joint doit être un PDF valide. Les participants ne
voient pas les brouillons, les publications simplement validées ou archivées.

Une thèse peut être soutenue avec sa date de soutenance, suspendue, reprise ou
abandonnée, selon son état. Les dates, encadrants et appartenances sont contrôlés
par le serveur. Il n'existe pas de suppression définitive dans cette interface.

Les commandes portent une version. En cas de conflit, relire la version actuelle,
comparer les données et confirmer explicitement avant un nouvel envoi. Une
modification d'un enfant incrémente aussi la version du projet : deux opérations
sur le même projet ne peuvent pas écraser silencieusement leur état respectif.

## Suivi financier

Il s'agit d'un **sous-grand-livre interne de recherche en EUR**, et non d'un
logiciel de comptabilité générale, d'une connexion bancaire ou d'une attestation
de paiement externe. Les justificatifs et le contrôle humain restent nécessaires.

Chaque opération nécessite une référence, une date, un montant exact et un
justificatif PDF, PNG ou JPEG. Le montant conserve ses décimales sans conversion
en nombre flottant.

| Opération | Effet |
| --- | --- |
| Financement | Enregistrer un encaissement : débit banque, crédit financement. |
| Engagement | Réserver une partie du budget disponible, sans mouvement de trésorerie. |
| Dépense | Consommer un engagement et de la trésorerie : débit charge, crédit banque. |
| Annulation d'engagement | Libérer la réservation restante, sans mouvement de trésorerie. |
| Contrepassation | Annuler exactement une opération admissible, une seule fois, avec les écritures inverses. |

Les dépenses ne peuvent dépasser ni le reliquat de l'engagement ni la trésorerie.
Les engagements ne peuvent dépasser le budget disponible. Les encaissements nets
ne peuvent dépasser le budget du projet ; une réduction du budget ne peut
invalider les encaissements, dépenses ou réservations déjà enregistrés.
Une opération liée ne peut précéder l'opération d'origine.

Le journal est immuable et ordonné par une séquence propre au projet, pas par
l'horloge du serveur. Les corrections s'ajoutent à l'historique ; aucune opération
ni écriture existante n'est modifiée ou supprimée. Le rapprochement contrôle
les écritures réellement persistées, les montants, les relations et la continuité
de la séquence. Une incohérence bloque le rapport au lieu de produire un bilan
apparemment valide.

Le rapport JSON et son export CSV présentent budget, encaissements, dépenses,
engagements ouverts, disponible budgétaire, trésorerie, totaux débit/crédit et
résultat du rapprochement. L'export est limité au projet et aux droits du compte.

### Envoi incertain et reprise

L'interface conserve la clé d'idempotence, les champs et le fichier de la tentative.
Si le résultat d'un envoi est incertain, **ne pas recréer une opération équivalente
avec une nouvelle clé**. Relire le journal ou rejouer exactement la tentative
conservée. Un rejeu identique retrouve l'opération sans créer de nouvelle écriture,
pièce ou version ; un contenu différent sous la même clé est refusé.

Un ancien bilan n'est plus présenté comme actuel après un résultat incertain.
La navigation est bloquée pendant cette résolution et une relecture est requise.
Les droits sont revérifiés même lors d'un rejeu ; un projet archivé refuse
les opérations et leurs rejeux.

## Pièces, confidentialité et données existantes

Les livrables et publications utilisent un stockage privé académique ; les
justificatifs utilisent le stockage privé financier. Les téléchargements passent
par des endpoints autorisés, avec `Cache-Control: private, no-store`.
Les justificatifs financiers sont aussi contrôlés par leur taille et leur SHA-256.
Aucune URL publique de stockage n'est publiée dans les réponses.

Les anciens fichiers `publications/` restent à leur emplacement et ne sont ni
déplacés ni effacés. Leur lecture passe désormais par le contrôle privé ; l'accès
direct `/media/publications/...` est refusé, y compris en mode DEBUG.
Les chemins ambigus, traversées et liens hors racine sont refusés.

La migration ajoute les nouveaux champs et conserve les identifiants et relations
historiques. Les anciennes publications deviennent des brouillons, jamais des
publications validées automatiquement. Les anciennes thèses sans projet restent
conservées ; les nouvelles créations exigent un projet.

Les événements de recherche sont exclus des listes, acteurs, bilans et exports
génériques de workflow afin de ne pas divulguer les données privées. Ce module
n'envoie pas de nouvelles notifications, de courriels ou de SMS.

## Repères API

La base est `/api/v1/recherche/` :

| Ressource | Parcours |
| --- | --- |
| `laboratoires/` | Création, modification versionnée, archivage et sélecteurs. |
| `projets-recherche/` | Projet, équipe, capacités, transitions et collections liées. |
| `productions-scientifiques/` | Publication, validation, publication effective, archivage et fichier privé. |
| `theses/` | Encadrement, soutenance, suspension, reprise, abandon et archivage. |

Sous `projets-recherche/{id}/` : `jalons/`, `livrables/`, `valider-jalon/`,
`operations-financieres/`, `rapport-financier/`,
`exporter-rapport-financier/` et `justificatifs/{operation_id}/`.
Les téléchargements de livrables utilisent `livrables/{livrable_id}/fichier/`.
Les commandes de transition sont distinctes des modifications de métadonnées ;
les écritures directes des états et les méthodes PUT/DELETE sont refusées.
