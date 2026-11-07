# Reste à faire et critères de validation — LMS/SIS

État relevé le 5 novembre 2026. Ce document réunit les 34 tâches initialement
ouvertes de la TODO, **cinq tâches ajoutées** après rapprochement du nouveau
cahier SIS/LMS/ERP, et les exigences du cahier complémentaire « identités,
autorisations, sécurité et import/export » (source fournie : SHA-256
`e5e3b1e3ccfee313370bfe53e322aff2a2fe18fde4498e80ed6772e78d49f868`).
La [matrice de recette](functional-acceptance-matrix.json) reste la référence
des 94 exigences initiales ; ce cahier complémentaire **ajoute** des critères,
sans transformer les preuves antérieures en validation globale.

**Dernier cutoff documentaire : 7 novembre 2026 à 06:53:19 UTC**, vagues
15/16/17/18 publiées et qualifiées dans les seuls périmètres décrits ci-dessous.
État officiel inchangé : **1 vérifiée, 71 partielles, 20 absentes et
2 non vérifiées sur 94**. Les deux anciens fichiers Studio examinés
séparément restent **non qualifiés et non publiés**, sans preuve revendiquée
ici. Les bilans datés antérieurs conservent leurs cutoffs et attentes historiques.

**État historique au 5 novembre :** 5 tâches en cours, 31 à démarrer, 3 bloquées ; 170 tâches
terminées dans la TODO, mais seulement **1 exigence vérifiée sur 94**
(70 partielles, 21 absentes, 2 non vérifiées). Le dernier essai à 500
connexions est rouge. Les cases ci-dessous désignent des **lots encore à
valider**, même si certains composants existent déjà.

**Qualification du lot de code du 5 novembre 2026 :** les suites backend
isolées passent (570 tests secondaire, 564 supérieur), ainsi que 316 tests
frontend sur 29 suites et le build de production. Les contrôles ciblés des
écrans IAM/portails passent, mais le lint global frontend échoue encore
(328 erreurs). Ces preuves portent sur le code et des services de test, pas
sur un déploiement institutionnel de ces commits. L'image SIS
`lms-sis:local-20261105-c98acea` se construit et passe `manage.py check` dans
les deux variantes, mais n'a pas remplacé les services partagés. Vérifier les
migrations sur une copie des données, notamment les doublons de références
carte avant la contrainte unique, et requalifier le vrai Stripe, Open edX et
les parcours navigateur. Aucune nouvelle campagne à 500 connexions n'a été validée ;
ne cocher aucune exigence supplémentaire sur la seule base de ce lot.

**Avancement du 6 novembre 2026 :** neuf correctifs bornés ont été testés,
committés et poussés : validation des imports Excel, séparation des acteurs
courrier, diagnostic des écritures incertaines à la charge, lint des utilitaires
frontend, refus du rejeu LMS après changement d'établissement, refus du
remboursement comptable d'une carte sans preuve Stripe, revalidation des
portails, précontrôle des références carte avant migration et périmètre des
anciens portails. Les suites ciblées passent dans les deux SIS, la nouvelle
construction frontend passe et les 31 tests hors ligne du banc de charge
passent. Le registre de session indique 179 tâches terminées, 8 en cours,
28 en attente et 3 bloquées ; **les 94 exigences gardent leurs statuts**.
Le patch Open edX de rejeu d'un cours attend encore des tests sur une base
LMS isolée. Aucun nouveau déploiement, pilote réel ni passage à 500 vert
n'a été démontré.

**Avancement suivant du 6 novembre 2026 :** onze correctifs supplémentaires
ont été testés, committés et poussés séparément : affectation en classe
secondaire conditionnée à l'inscription, retrait d'accès aux documents après
changement de rôle, réaffectation des réclamations seulement après recours,
dépendances effectives des modules, neutralisation des formules CSV/XLSX,
exclusion des sessions JWT expirées, gestion des sessions depuis le compte
local, actions IAM bornées par les scopes, accès aux portails selon le rôle,
lint de cinq pages universitaires et restriction du répertoire des étudiants
supérieurs. Les suites partagées ont passé **26 tests dans chaque SIS** sur
PostgreSQL isolé ; les cas d'inscription secondaire (4) et de répertoire
supérieur (5) passent également. Les contrôles frontend ciblés, le lint des
fichiers modifiés et le build de production passent. Le lint global compte
encore **87 erreurs** avant la tranche suivante. Le patch Open edX non testé,
la recette institutionnelle, les fournisseurs externes et la charge 500
restent ouverts : **1/94 exigences vérifiées**, sans nouvelle promotion.

**Tranche suivante :** le lint frontend global passe désormais sans erreur,
les **342 tests Jest sur 30 suites** et le build de production passent. Les suites
isolées admissions, cycle académique, emploi du temps et services passent
**36/36 dans chacun des deux SIS**. Deux précontrôles d'installation ont
été ajoutés : rejet des clés privées/incomplètes du JWKS et des URL LMS/Studio
invalides avant la saisie des secrets ; les 8 tests CLI passent. Une image
backend correspondant au code publié (`lms-sis:local-20261106-1e196e9`) a
été construite ; `manage.py check` passe pour les deux variantes. Avec les
sources des tests d'installation, des contrats frontend et de la fixture
transport corrigée montées en lecture seule sur l'image applicative précédente
(code backend identique), la régression complète passe aussi (**596 secondaire,
593 supérieur**) sur PostgreSQL/Redis jetables. Cette image
n'est **pas déployée** sur les services partagés. La recette intégrale, les
vrais parcours LMS/prestataires et la charge 500 restent à démontrer ; le
correctif Open edX demeure non publié faute d'essai CMS/MySQL isolé.

**Quatrième vague du 6 novembre 2026 :** dix correctifs distincts ont été
testés, committés et poussés : signatures indisponibles après désactivation
du titulaire, refus des redirections d'inscription LMS, récupération de compte
inactif, bilan ECTS lié à son inscription, création de cours dans les seuls
espaces SIS gérés, présence cantine conditionnée à l'inscription, protection
des dossiers d'infirmerie par appartenance au tenant, transitions des projets
de recherche, attribution des bourses sur demande acceptée et capacité des
chambres d'internat sur périodes chevauchantes. La revue a aussi vérifié
qu'une occupation entièrement terminée n'empêche pas de diminuer la capacité.
L'image `lms-sis:local-20261106-f9f9018` a été reconstruite depuis ces
commits ; `manage.py check` passe pour les deux variantes. Sur PostgreSQL et
Redis jetables, les suites complètes de cette image passent (**609 tests
secondaire, 606 supérieur**), avec les scripts d'installation et contrats
frontend nécessaires à la collecte montés en lecture seule. La suite
frontend et son build n'ont pas été relancés : aucun fichier frontend n'a
changé depuis leurs derniers résultats verts. Cette image n'a remplacé aucun
service partagé ; le correctif Open edX antérieur reste non qualifié et non
publié. **La matrice demeure à 1/94 vérifiée** : ni parcours réels
institutionnels, ni fournisseurs externes, ni campagne à 500 connexions
verte ne sont démontrés par ces tests.

**Cinquième vague du 6 novembre 2026 :** dix autres incréments testés puis
poussés séparément protègent la validation d'un paiement sur facture annulée,
les champs de signature des diplômes, la disponibilité des exemplaires de
bibliothèque scolaire, les incidents déjà sanctionnés ou classés, la
publication des résultats validés après la fenêtre de saisie dans les deux
SIS, les prêts universitaires renouvelés, le statut comptable des factures
universitaires, la capacité des clubs et les transitions des mémoires. Pour
les examens, la clôture des périodes reste opposable ; la soutenance d'un
mémoire ne peut pas être déclarée par simple modification de son statut,
mais le circuit de jury réel reste à construire et à prouver. L'image
`lms-sis:local-20261106-491f7ae` passe `manage.py check` dans les deux
variantes et les régressions complètes sur PostgreSQL/Redis jetables
(**617 tests secondaire et 617 supérieur**). Le lint des fichiers Python
modifiés passe avec la règle du Makefile. Les scripts et contrats frontend
nécessaires à la collecte ont été montés en lecture seule ; le frontend
inchangé n'a pas été retesté. Aucun service partagé n'a été remplacé,
le correctif Open edX reste non publié, les prestataires et le pilote réel
ne sont pas qualifiés et le dernier essai à 500 reste rouge. **Matrice :
1/94 vérifiée**, sans promotion sur la seule foi de ces suites.

**Sixième vague du 6 novembre 2026 :** huit correctifs testés et poussés
séparément encadrent les décisions sur les justificatifs d'absence, l'accès
aux appréciations de bulletin, la capacité des salles, les conventions de
stage initialement non signées, les affectations enseignantes dans les deux
SIS, la signature des relevés universitaires et les candidatures de stage
supérieur. Les deux autres examens de cette vague n'ont produit aucune
modification qualifiée. L'image publiée
`lms-sis:local-20261106-c10a736` passe `manage.py check` dans chaque
variante et les suites backend complètes sur PostgreSQL/Redis jetables :
**625 tests secondaire, 626 supérieur**. Les scripts et contrats frontend
nécessaires à la collecte ont été montés en lecture seule. Aucun service
partagé n'a été remplacé, le frontend inchangé n'a pas été retesté,
le correctif Open edX demeure non qualifié, et les fournisseurs, parcours
institutionnels et 500 connexions restent à valider. **Matrice : 1/94
vérifiée**, sans promotion supplémentaire.

**Septième vague du 6 novembre 2026 :** huit incréments testés, lintés et
poussés séparément protègent les bulletins publiés et les dates
d'évaluation sur les deux routes secondaires, imposent les actions de
tenue et validation des conseils de classe, maintiennent les maquettes
universitaires dans leur établissement et hors des années closes,
interdisent les prérequis UE réflexifs, réservent les inscriptions au
rattrapage aux sessions correspondantes et conservent l'entreprise des
contacts de convention. L'examen du portail enseignant n'a identifié
aucune correction sûre dans son périmètre ; l'examen du jury a été refusé
avant toute intervention et reste non qualifié. L'image publiée
`lms-sis:local-20261106-46b1fb8` passe `manage.py check` dans les deux SIS
et leurs suites complètes sur PostgreSQL/Redis jetables (**632 tests
secondaire, 635 supérieur**). Le frontend inchangé n'a pas été retesté ;
aucun service partagé n'a été remplacé. Open edX, les prestataires réels,
la restauration et la campagne à 500 restent ouverts. **Matrice : 1/94
vérifiée.**

**Huitième vague du 6 novembre 2026 :** neuf correctifs ciblés ont été
testés, lintés, committés et poussés séparément : année cohérente des
groupes et des matières individuelles, conservation des périodes closes
lors de la suppression d'une année, appréciations immuables après
publication du bulletin, crédits ECTS validés bornés aux crédits inscrits,
notes universitaires dans leur barème, enseignants non dupliqués par
département, profil étudiant synchronisé avec l'inscription validée et
montant de facture universitaire inchangé après paiement. Une régression
initiale des matières individuelles a été corrigée : l'année est
obligatoire dans la requête ; quatre anciens tests d'inscription
universitaire utilisant une année fictive ont également été réalignés
avant publication. Le dixième examen, portant sur les inscriptions
universitaires, a été refusé avant toute modification et reste ouvert.
L'image `lms-sis:local-20261106-3d6e387` passe `manage.py check` dans
chaque variante et les suites backend complètes sur PostgreSQL/Redis
jetables (**638 tests secondaire, 642 supérieur**). Aucune migration,
aucun frontend ni service partagé n'ont été modifiés ; cette preuve
technique ne valide ni les parcours réels, ni la charge à 500, ni les
fournisseurs. **Matrice : 1/94 vérifiée.**

**Essai de démarrage isolé de l'image de huitième vague :** les migrations
du schéma public et d'un tenant synthétique ont réussi dans chaque SIS sur
deux bases PostgreSQL jetables distinctes. Les deux serveurs Gunicorn ont
répondu en HTTP à `/health/` et `/ready/` ; la disponibilité de PostgreSQL
et Redis y était vraie. Les serveurs et bases de cet essai ont ensuite été
arrêtés et supprimés sans modifier les services partagés. Cet essai avec
identifiants synthétiques ne constitue pas un déploiement institutionnel
persistent ni une preuve des parcours complets, du vrai LMS, des paiements
externes, d'une restauration ou de la charge à 500 ; la matrice reste à
**1/94 vérifiée**.

**Neuvième vague du 6 novembre 2026 :** huit fonctionnalités bornées ont
été testées et poussées : dépôt initial d'admission par un apprenant déjà
authentifié (pas de candidature anonyme), modèle et aperçu CSV/XLSX versionnés
pour l'import Students, prévisions budgétaires secondaires (pas de livre de
dépenses), registre d'équipements scolaires, consentement alumni privé lié à
un diplôme signé et non révoqué, recherche universitaire limitée par
établissement et permissions, vérification publique d'un PDF signé sur
présentation du fichier (seul un booléen est retourné), et avis hors connexion
désactivé par défaut sans cache d'API ni données personnelles. Le dépôt des
notes LMS en brouillon demeure bloqué : les deux récepteurs publient des
notes directement et un état de validation humaine manque. La création
élémentaire de groupes universitaires était déjà montée ; l'exigence IAM
institutionnelle complète reste ouverte. Le correctif Open edX présent
localement demeure **non testé et non publié**.

Les incréments ont fait l'objet de tests ciblés et de contrôles lint ; les
migrations sont cohérentes (`makemigrations --check --dry-run`) et l'image
`lms-sis:local-20261106-d1ec6bf` passe les suites backend complètes sur
PostgreSQL/Redis isolés (**652 secondaire et 663 supérieur**). La régression
frontend passe (**349 tests, 32 suites**) avec un délai Jest de 20 secondes
pour le banc partagé ; le cas LMS lent dispose désormais de ce délai dans
son fichier de test et repasse sans option supplémentaire. Le lint frontend
termine avec 0 erreur et 8 avertissements antérieurs ; le build de production
passe. Sur cette image, la migration des schémas publics et d'un tenant
synthétique par variante a réussi sur deux bases jetables, puis les serveurs
ont répondu 200 à `/health/` et `/ready/`, avec PostgreSQL et Redis prêts.
Ce n'est pas un remplacement des services partagés ni un parcours complet.
Les fournisseurs externes, la recette navigateur de tous les champs et
boutons, la restauration, les brouillons LMS et une campagne **500
connexions verte** restent à démontrer. Le dernier essai à 500 avait
500 timeouts et 262 écritures indéterminées : **1/94 exigence vérifiée**,
sans promotion.

**Dixième vague du 6 novembre 2026 :** dix incréments bornés ont été testés,
committés et poussés séparément : les événements LMS ne remplacent plus une
note corrigée par le personnel ou une période close, sans pour autant créer
le brouillon officiel attendu ; réservations et remise de livres dans les
deux SIS, pointages cantine liés à l'élève du tenant, séjours d'internat
sans chevauchement pour un élève, solde de facture scolaire calculé sur les
seuls paiements confirmés, diplôme universitaire conditionné à l'inscription
validée et à une admission par jury final clôturé, candidatures/programmes/
accords de mobilité bornés à l'université, attributions de bourses vérifiées
et autorisées par les permissions, et conflits d'emploi du temps d'un groupe
refusés. Le transport n'a **pas** été modifié : ni trajet daté ni affectation
horaire véhicule/conducteur n'existent pour prouver un conflit. Les chambres
et bâtiments d'internat n'ont toujours pas de propriétaire tenant ; les
menus cantine s'appuient sur le schéma tenant. Les réservations universitaires
n'envoient pas de notification et n'ont pas de politique d'expiration.

Après vérification des routes, refus, rejouements et relations étrangères
concernés, l'image `lms-sis:local-20261106-e5a8be9` a été construite
à partir du code publié.
Les suites **correctement limitées à chaque variante** passent sur
PostgreSQL/Redis jetables (**669 tests secondaire, 691 supérieur**),
`manage.py check` et `makemigrations --check --dry-run` passent dans
les deux variantes. Sur deux bases indépendantes, les migrations du schéma
public et d'un tenant synthétique passent ; chaque serveur répond 200 à
`/health/` et `/ready/`, avec PostgreSQL et Redis prêts, puis les ressources
de cet essai sont arrêtées. Le frontend inchangé conserve ses dernières
preuves (349 tests, lint et build verts) ; aucune recette navigateur ni
restauration de cette image n'a été exécutée. Le patch Open edX local reste
non testé et non publié. Aucun service partagé n'a été remplacé, les
fournisseurs réels, la validation humaine des notes et la campagne à 500
connexions restent ouverts : **1/94 exigence vérifiée**, sans promotion.

**Onzième vague du 6 novembre 2026 :** neuf incréments ont été testés,
committés et poussés séparément : relevés universitaires signés non
modifiables ; sanctions scolaires refusées après résolution de l'incident ;
factures scolaires non annulables après paiement confirmé ; stages scolaires
lisibles uniquement par l'élève ou son superviseur affecté ; comptes étrangers
refusés sur les routes entreprises universitaires ; solde universitaire
calculé sur les paiements validés et visible par l'étudiant propriétaire ou
la finance locale ; revalidation des créneaux universitaires concurrents sous
verrous de formation, salle et enseignant ; justificatifs d'absence acceptés
seulement pour un cours et une inscription historique validée du tenant ;
rattrapages conditionnés à une inscription administrative et pédagogique
validées, ou à une affectation individuelle, dans la formation, le semestre
et l'université de la session. Les salles n'ont **pas** été modifiées :
aucun état daté de maintenance ou d'indisponibilité ne permet de refuser
une réservation sans inventer une règle. Le statut historique d'une
inscription scolaire n'est pas conservé : une annulation ultérieure peut
empêcher la validation d'une absence autrefois admissible. Les entreprises
universitaires sans propriétaire tenant obligatoire restent non isolées
au niveau des enregistrements.

L'image `lms-sis:local-20261106-8ecda9d` passe les suites complètes sur
PostgreSQL/Redis jetables (**680 tests secondaire et 705 supérieur**),
`manage.py check` et `makemigrations --check --dry-run` dans les deux
variantes. Les migrations des schémas publics et de deux tenants synthétiques
ont réussi sur deux bases isolées ; chaque serveur répond 200 à `/health/`
et `/ready/` avec base et cache prêts. Une première exécution secondaire
échouait sur deux sous-processus WSGI/ASGI privés des identifiants Open edX
synthétiques ; sa relance configurée a passé. Une première exécution
universitaire a signalé 22 erreurs de clé Fernet non reproduites par les
tests ciblés et une relance complète verte : la cause de cette variabilité
n'est pas établie, et **100 % de fiabilité n'est pas démontrée**. Le frontend
inchangé conserve ses dernières preuves (349 tests, lint et build verts).
Ni ces contrôles ni les démarrages jetables ne prouvent une restauration,
les parcours complets navigateur/Open edX/prestataires, une recette
institutionnelle ou la tenue à 500 connexions ; le dernier essai autorisé
à 500 demeure rouge. **Matrice : 1/94 exigence vérifiée**, sans promotion.

**Contrôle ciblé du 6 novembre 2026 après la onzième vague :** la recherche
universitaire de formations/parcours permettait à un étudiant de retrouver
une formation liée à une inscription administrative provisoire. Le test HTTP
reproduit ce défaut sur l'image précédente ; le correctif `a2e7f8e` n'accepte
plus que les inscriptions validées, y compris après refus ou annulation
(11 tests core verts sur l'image reconstruite sans montage source, lint ciblé
vert). Ce moteur ne couvre aucun des cinq types d'objets de la recherche
globale demandée en **10.7** ; à ce stade, cette exigence restait *absente*
dans la matrice. La preuve a été rattachée à 10.7 sans changer les statuts.
Cette image n'a pas remplacé le déploiement partagé ni passé une nouvelle
restauration ou charge à 500 : **1/94 exigence vérifiée** reste le compteur
de recette documentée, pas le pourcentage d'implémentation.

**Extension de la recherche le même jour :** `00f1755` ajoute la recherche
d'apprenants universitaires par matricule et nom sur la route académique
existante, avec réponse minimale, droits de lecture, périmètre d'établissement,
scopes et restriction de l'étudiant à sa seule fiche. Les tests vérifient
aussi le retrait de permission et les identités étrangères (**13/13 tests
core verts sur l'image jetable `lms-sis:local-20261106-00f1755` sans montage
source**, lint ciblé vert). C'est désormais **un des cinq types** attendus
par 10.7 : son statut passe d'*absent* à *partiel* (71 partielles,
20 absentes, 2 non vérifiées et **1 vérifiée** sur 94). Les cours LMS,
documents, factures et activités, la variante secondaire et le parcours
navigateur restent ouverts. Aucune nouvelle charge à 500 ni restauration
de cette image n'a été exécutée.

**Treizième vague du 6 novembre 2026 :** les incréments ont été vérifiés,
committés et poussés séparément : refus des comptes d'un autre établissement
sur les routes élèves scolaires (`d03385c`) ; refus d'une restauration vers
un volume non vide, y compris un répertoire vide ou un lien (`d5cb33e`) ;
garde de permission sur la route frontend discipline (`88e1299`) ; agent
d'archivage du courrier distinct du créateur et de l'approbateur (`b72afde`) ;
rattrapage après clôture réservé à une épreuve de session de rattrapage
(`68a3af3`) ; conservation des décisions définitives de mémoire (`456041f`) ;
bornage des dossiers et visites d'infirmerie aux élèves locaux (`b390b41`) ;
publication des bulletins uniquement par l'action prévue, sur les deux
routes API (`23405ca`) ; tests de lecture et d'écriture des entreprises sur
deux schémas distincts (`b1ce5b1`) ; indisponibilités de salles par journées
entières, contrôlées dans les deux sens avec les créneaux actifs (`1e97222`) ;
trajets datés avec interdiction PostgreSQL de chevauchement d'un même véhicule
(`60e8312`). Le contrat d'import tient compte du refus 403 des comptes
étrangers (`1e69013`). La revue supplémentaire a borné les métadonnées des
calendriers par classe et enseignant (`2556f6a`) et les routes de transport
aux comptes du tenant (`9814f3a`). Les tests ciblés couvrent les nouvelles
routes, les refus et les cas autorisés sur PostgreSQL jetable ; les
migrations des salles et des trajets sont cohérentes avec les modèles
(`makemigrations --check --dry-run`).

La production frontend se construit, son lint ne relève aucune erreur et
les 15 tests ciblés de route/permissions passent. La suite intégrée
universitaire passe **716 tests** sur l'image `1e69013` ; les deux derniers
commits ne modifient que le secondaire. L'image finale
`lms-sis:local-20261106-9814f3a` passe `manage.py check` et le contrôle
des migrations dans les deux variantes ; la suite secondaire finale passe
**693 tests**. Ces suites ont été exécutées en série sur PostgreSQL et
Redis jetables, sans installer l'image sur les services partagés.
Sur deux bases et deux tenants synthétiques neufs, les migrations publiques
et tenant ont réussi avec un propriétaire PostgreSQL non superutilisateur
(`salles.0003` et `transport.0002` comprises) ; `/health/` et `/ready/`
répondent 200 avec base et cache prêts dans les deux variantes via le
client Django. Ce contrôle n'est pas un déploiement institutionnel.

Restent notamment à valider avant clôture : installer et migrer les deux
tenants sur une copie de données réelles, vérifier sur deux hôtes que ni
les métadonnées ni les écritures scolaires ne franchissent le tenant, puis
restaurer une sauvegarde institutionnelle dans des volumes vierges et
comparer comptes, inscriptions, rôles, pièces et journaux avant/après.
Pour le transport, créer un conducteur à identité pérenne et vérifier le
refus des affectations concurrentes d'un même conducteur ainsi que la
compatibilité des anciennes lignes non datées ; le modèle actuel ne
garantit que la non-superposition des **véhicules datés**. Pour les
entreprises, établir une propriété tenant explicite des lignes historiques
et tester leur migration sans perte ; la preuve actuelle est une isolation
de schéma. Les réservations de salle ne décrivent que des journées entières,
pas une maintenance horaire ni les exceptions calendaires hebdomadaires.
Les fournisseurs réels, la recette navigateur et Open edX, les parcours
institutionnels exhaustifs et une campagne à 500 autorisée et verte
restent nécessaires. **La matrice demeure à 1/94 exigence vérifiée**
(71 partielles, 20 absentes, 2 non vérifiées) : ces tests de code ne sont
pas une réception de bout en bout.

**Quatorzième vague du 6 novembre 2026 :** vingt incréments bornés ont été
revus, testés, committés et poussés séparément. Le précontrôle d'installation
refuse désormais un manifeste JSON mal formé avant les effets de bord. Dans
le secondaire, les corrections concernent la confidentialité des emprunts,
les accès cantine par établissement, la capacité des clubs, les décisions
validées du conseil de classe, les deux routes d'évaluations, les réservations
d'internat futures, les transactions de paiement liées à l'établissement,
les justificatifs de présence et la signature de conventions annulées.
Dans le supérieur, elles concernent les candidatures à une offre de stage
fermée, les emprunts d'autres titulaires, les actions sur bourses, les
diplômes signés, les crédits ECTS négatifs, les affectations enseignantes,
les maquettes d'un autre établissement, les accords de mobilité, les
rattrapages et les projets de recherche. L'examen disciplinaire secondaire
a été refusé avant toute intervention : aucun correctif de ce module
n'est déclaré qualifié. Les deux fichiers Open edX modifiés localement
restent non testés et non publiés.

Les suites API groupées passent sur PostgreSQL/Redis jetables (**89 tests
secondaire, 66 supérieur**), le lint des fichiers Python modifiés et le
contrôle des espaces passent. L'image du code publié
`lms-sis:local-20261106-d79a735` passe `manage.py check` et
`makemigrations --check --dry-run` dans les deux variantes, puis les suites
complètes en série (**708 secondaire, 730 supérieur**), sans monter de
code applicatif local. Le premier lancement groupé secondaire redirigeait
les requêtes HTTP vers HTTPS faute de configuration de test ; la relance
configurée a passé. Les scripts et contrats frontend utilisés par les tests
ont été montés en lecture seule ; le frontend inchangé n'a pas été retesté.
Aucun service partagé n'a été remplacé. Pour clôturer les exigences
institutionnelles, restent nécessaires les migrations et la restauration
sur copies de données réelles, les parcours navigateur et LMS/prestataires
autorisés, les contrôles de rôles sur deux établissements et une nouvelle
campagne à 500 précontrôlée, autorisée et verte. La dernière campagne à
500 demeure rouge : **1/94 exigence vérifiée** (71 partielles, 20 absentes,
2 non vérifiées), sans promotion sur les seuls tests de code.

**Cutoff historique des deux bilans suivants : 7 novembre 2026 à 06:37:14 UTC.**

**Quinzième vague, publiée et qualifiée au cutoff du 7 novembre 2026 :**
les commits présents dans `origin/main` ajoutent les chauffeurs à identité
pérenne et coordonnées protégées, avec refus des affectations chevauchantes
(`35ef40c`), la recherche universitaire de documents selon leurs sources
autorisées et de vrais cours (`d9ca357`), la recherche scolaire d'élèves et
de factures selon les politiques de visibilité communes (`c1eac39`), puis
les propositions de notes LMS soumises à approbation ou rejet nominatif
audité avant toute note officielle (`06b55e8`). Le conflit PostgreSQL
`DISTINCT`/`FOR UPDATE` des factures scolaires est corrigé par un queryset
verrouillable. Le rafraîchissement en boucle des permissions dans
`EvaluationsManager` est corrigé avec `refetchOnMount: false` ; sa
régression ciblée passe 14 tests.

L'image backend `lms-sis:local-20261107-06b55e8`, digest
`sha256:956bf0382d5b42b527080d27c937ca6b5622dfda4c22881a87aa99b5cae7f917`,
a été testée sans montage de code applicatif backend, sur PostgreSQL/Redis
jetables : **762 tests et 305 sous-tests secondaire**, **781 tests et
300 sous-tests supérieur**, tous verts. `manage.py check` et
`makemigrations --check --dry-run` passent dans chaque variante. Les
migrations transport/chauffeurs ont été validées avec un propriétaire de
base non superutilisateur selon le parent ; le journal de préparation
secondaire conserve l'application de `transport.0002` et `transport.0003`.
Les anciennes données ne sont pas automatiquement rapprochées : seuls les
trajets datés portant une référence chauffeur bénéficient de sa contrainte.

Les protections des notes comprennent **11 tests par variante**, inclus
dans les suites complètes, avec concurrence PostgreSQL réelle : deux
décisions obtiennent **200/409**, une seule note et un seul audit de décision
sont créés. Le snapshot académique période/année est recontrôlé et un
événement plus récent retenu bloque l'approbation d'une ancienne proposition.
Les parcours navigateur réussis `wave15-browser-secondaire-r3` et
`wave15-browser-superieur` utilisent des fixtures jetables sur loopback :
webhook signé **synthétique**, tâche réellement exécutée en **Celery eager**,
absence de note officielle avant approbation, rejet motivé, second onglet
obsolète refusé en 409, rejeu et non-écrasement de la note officielle.
Ce n'est **pas un échange avec un vrai LMS natif Open edX**, ni une recette
institutionnelle humaine ; **F09 reste partiel**.

**Seizième vague, publiée et qualifiée au même cutoff :** `ae86edd`, présent
dans `origin/main`, raccorde la recherche métier à la palette existante et
ouvre les fiches autorisées sans cache partagé. La première suite frontend
n'est **pas entièrement verte** : **400 tests passés et 2 timeouts sur
402 tests, 34 suites passées et 2 échouées sur 36**. Seuls les deux cas
en timeout ont été relancés avec une limite de 20 secondes : **2 passés,
78 ignorés** dans les deux fichiers sélectionnés. Cette relance ciblée ne
remplace pas une nouvelle suite complète verte. Le lint final compte
**0 erreur et 8 avertissements** ; le build de production passe avec
**3 avertissements de taille/performance**.

Les parcours navigateur `wave16-browser-search-secondaire` et
`wave16-browser-search-superieur-r2` passent sur fixtures jetables loopback :
recherche et ouverture d'élève/étudiant et de facture, pagination de
**25 factures en 20 + 5**, puis ouverture d'une attestation universitaire.
Ils ne prouvent ni la recherche des activités, ni les cinq familles dans les
deux SIS, ni tous les rôles/révocations ; **10.7 reste partielle**.
Les reçus `.last-run.json` attestent le succès des derniers passages cités ;
leur périmètre est rapproché des scénarios publiés et des résultats du parent,
pas d'une trace exhaustive.

Les preuves conservées dans le dossier `files` de la session
`d0c25c75-b0da-489a-9501-d00e100d5269` sont notamment
`wave15-school-published-full.log`, `wave15-university-published-full.log`,
`wave15-image-build.log`, `wave15-capability-regression.log`,
`wave16-frontend-full.log`, `wave16-frontend-timeout-recheck.log`,
`wave16-frontend-lint-final.log`, `wave16-frontend-build-r2.log` et les quatre
reçus navigateur ci-dessus ; leurs empreintes sont rattachées aux nouveaux
cutoffs dans la matrice. Aucun test ni service n'est relancé pour cet import
documentaire. Aucun déploiement partagé de ces vagues, pilote ou réception
humaine n'est démontré. Les rapports rouges historiques restent intacts,
dont le dernier essai à **500 : 500 timeouts et 262 écritures indéterminées**.
**Aucune des 94 exigences n'est promue. La vague 17 en cours, non publiée,
est exclue de ces preuves** et sera traitée séparément après vérification.

**Dix-septième vague, publiée et qualifiée au cutoff du 7 novembre 2026
à 06:43:28 UTC :** trois commits sont désormais présents dans `origin/main`.
`1be9eaa` ajoute les vrais cours LMS et les bulletins scolaires recherchables
par référence PDF `BUL-<id>`, avec une politique partagée entre liste, détail,
PDF et recherche : familles soumises à la publication, établissement et
scopes respectés, référence du professeur principal corrigée vers `User`.
`bae0bd4` ajoute la recherche d'évaluations SIS universitaires reliées à des
sous-sections LMS actives, avec scopes et détail de cours autorisé.
`f24fd4f` raccorde les fiches de cours dans les deux SIS, le bulletin scolaire
et l'évaluation reliée au LMS universitaire ; le retrait d'`is_staff` enlève
l'accès administratif LMS même si une permission générique `*` subsiste.
Les cours recherchés sont des mappings réels, pas des formations présentées
comme des cours ; les évaluations restent des objets SIS reliés au LMS.

La qualification backend est **ciblée**, avec le code de vague 17 monté en
**lecture seule sur l'image `lms-sis:local-20261107-06b55e8`** :
aucune image de vague 17 reconstruite ni suite backend complète de vague 17
n'est revendiquée. Le premier passage secondaire
`wave17-school-search.log` conserve **85 tests et 73 sous-tests passés,
1 échec HTTP 429** : le parcours de fixture dépassait le quota. Après
isolation/vidage du cache **uniquement dans les tests**, sans relâcher le
quota applicatif, `wave17-school-bulletins-recheck.log` passe **10 tests et
19 sous-tests**. Cette relance ciblée **ne rend pas le premier passage
intégralement vert**. Le supérieur passe **70 tests et 25 sous-tests**
dans `wave17-university-search.log`.

`wave17-workspace-complete.log` passe les **75 tests du seul fichier
Workspace**, avec délai de 20 secondes ; ce n'est pas toute la suite
frontend. `wave17-frontend-lint.log` donne **0 erreur et 8 avertissements** ;
`wave17-frontend-build.log` compile avec **3 avertissements de taille/performance**.
Les deux parcours navigateur réels, un par variante, passent sur la même
infrastructure de fixtures jetables loopback :
`wave17-browser-search-secondaire` ouvre élève, factures (25, pagination
20 + 5), cours et bulletin ; `wave17-browser-search-superieur` ouvre étudiant,
factures, cours, évaluation mappée et attestation. **Aucune réponse réseau
n'est simulée** : l'interception ne fait qu'espacer les requêtes avant
`route.continue()`. Les reçus `.last-run.json` attestent le succès, leur
périmètre étant rapproché des scénarios publiés et des résultats du parent.
Le parent confirme l'arrêt des API et passerelles de ces fixtures après
les parcours ; aucun service n'est démarré ou sondé pour cet import.

Les huit artefacts cités sont hachés dans la matrice. **10.7 et F09 restent
partiels**, sans promotion d'exigence : activités secondaires en cours de
vague 18 non qualifiée, pas de catalogue LMS natif exhaustif ni de recette
navigateur exhaustive multi-rôles/révocations. Aucun déploiement partagé,
pilote ou réception humaine ; les suites complètes de vague 15 ne se
transfèrent pas au code monté de vague 17. Les premiers rouges frontend
de vague 16 et secondaire de vague 17 restent conservés ; le dernier
essai à 500 reste rouge avec **500 timeouts et 262 écritures indéterminées**.

**Dix-huitième vague, publiée et qualifiée au cutoff du 7 novembre 2026
à 06:53:19 UTC :** `9ff9752`, présent dans `origin/main`, ajoute le type
`evaluations_lms` au secondaire et de vrais parcours apprenants dans les
deux SIS. Les évaluations recherchées sont des objets SIS reliés au LMS :
permission de lecture et queryset natif des évaluations, attribution
enseignante via `Personnel`, cohérence matière/classe/période/année,
tenant actif, scopes et mappings actifs sont contrôlés. Il ne s'agit pas
d'un catalogue natif exhaustif des activités Open edX.

`wave18-school-activity-search.log` passe **69 tests et 87 sous-tests**
(core complet, API d'intégration et protections des notes LMS dans la
sélection secondaire), pas toute la suite backend. `wave18-search-ui.log`
passe **37 tests ciblés**, avec **42 non sélectionnés sur 79**, dans
Workspace et avec délai de 20 secondes ; ni les 79 tests ni toute la suite
frontend ne sont déclarés exécutés. `wave18-frontend-build.log` compile avec
**3 avertissements de taille/performance**. Le parent atteste un lint
frontend **ciblé à 0 erreur et 0 avertissement**, ainsi que Black, isort et
flake8 verts sur l'API et les tests secondaires concernés ; aucun journal
dédié de ces contrôles n'a été fourni, et ce n'est pas une nouvelle preuve
de lint global sans avertissement.

`wave18-browser-search-secondaire` et `wave18-browser-search-superieur`
passent chacun **deux parcours réels : staff et apprenant**, avec la
configuration `testMatch: academic-search.e2e.js`. Le staff ouvre cours,
évaluation reliée au LMS, bulletin scolaire ou attestation universitaire,
et les factures paginées (25 en 20 + 5). L'apprenant se connecte sur la vraie
base de fixture et ouvre sa facture ; les types administratifs Cours LMS
et Évaluations reliées au LMS sont absents de sa palette. La recherche de
la facture d'un autre apprenant est vide, son détail API répond **404 sans
divulguer le numéro**, et l'URL directe d'évaluation est refusée sans
aucun champ de détail (`dd`). Cela ne qualifie pas tout l'accès pédagogique
de l'apprenant dans le LMS natif.

Les comptes et factures sont synthétiques, sur la seule infrastructure
jetable loopback ; **aucune réponse réseau simulée**, seulement le pacing
avant transmission réelle. Les reçus `.last-run.json` sont verts ; nombre
et contenu des parcours sont rapprochés des scénarios publiés et des
résultats du parent. Celui-ci confirme l'arrêt des API/passerelles après
les parcours. Les cinq artefacts cités sont hachés dans la matrice.
**Aucune image 18 reconstruite ni suite complète 18 n'est revendiquée**,
aucun déploiement partagé, pilote ou réception humaine. **10.7 reste
partielle** : catalogue LMS natif exhaustif et parcours navigateur
parents/enseignants/multi-tenant non exhaustifs ; **F09 reste partiel**.
Les deux anciens fichiers Studio examinés par un agent distinct sont
**non qualifiés et non publiés** au cutoff. Les précédents cutoffs, leurs
rapports rouges et le dernier essai à 500 (**500 timeouts,
262 écritures indéterminées**) restent intacts ; aucun statut n'est promu.

## Règle de clôture commune

Pour cocher un point : conserver le scénario de départ et les preuves de
résultat (tests automatisés, réponse API, parcours navigateur et état
persisté). Exécuter succès, refus, erreur amont, rejeu, révocation et
concurrence lorsque pertinents, dans **les deux variantes SIS**, avec deux
établissements et au moins deux rôles distincts. Vérifier côté serveur les
permissions tenant/objet et les écritures, pas seulement la présence d'un
bouton. Une opération non applicable à un pack doit être explicitement
désactivée et documentée, pas déclarée réussie. Comparer les comptes,
MFA, droits et données protégées avant/après migration, redémarrage et
restauration isolée. Associer à chaque case les tests, journaux non sensibles,
version d'image et preuve de déploiement dans la matrice. Une API HTTP 200,
un test simulé ou une interface seule ne prouvent pas le parcours réel.
Toutes les lignes des tableaux ci-dessous restent ouvertes tant que leurs
conditions propres n'ont pas une preuve de recette.

Les services externes (paiement, SMTP, annuaire, IA, établissement pilote)
nécessitent des accès autorisés ; inscrire **bloqué** et le contrat non
qualifié tant qu'ils manquent. Ne modifier ni le design ERP figé, ni les
budgets ou seuils de la campagne de charge pour obtenir artificiellement
un résultat vert.

## A. Tâches déjà ouvertes (34)

### En cours (5)

- [ ] **F02 — Identités et habilitations** (`ft-identity`). Terminer les
  affiliations simultanées, campus, profils, multi-rôles et
  délégations temporaires. **Valider :** un même compte change de tenant
  et de rôle sans fusionner les données ; retrait/expiration coupe API,
  fichiers et LMS immédiatement ; droits directs et hérités restent bornés ;
  comptes, MFA et historique survivent à la migration et au redémarrage.
- [ ] **F03 — Contrats des modules** (`ft-contracts`). Registre, versions,
  dépendances, permissions, migrations, contrats API/événements et extensions
  tierces isolées. **Valider :** installation, mise à niveau, désactivation,
  réactivation et rejeu d'un module dans deux tenants produisent chacun
  exactement les données attendues, sans perte, doublon ni droit implicite.
- [ ] **F06 — LMS exploitable** (`ft-lms-deployment`). Terminer la qualification
  institutionnelle d'Open edX/Studio, TLS/domaines, stockage et exploitation.
  **Valider :** créer/publier/suivre un cours réel sur image empaquetée,
  redémarrer puis restaurer dans un projet distinct ; contenu, inscription,
  résultats, comptes et secrets restent cohérents ; documenter les limites
  de la version et les ressources nécessaires.
- [ ] **F07 — SIS ↔ LMS** (`ft-lms-sync`). Raccorder utilisateurs, enseignants,
  cours, inscriptions, suspensions, départs et SSO pour tous les profils.
  **Valider :** octroi et retrait observés dans le vrai LMS avec seul cours
  autorisé, coupure/réponse perdue puis rejeu sans doublon, révocation après
  changement d'affectation, parcours navigateur et diagnostics des deux SIS.
- [ ] **Capacité 500** (`universal-load-500`). Préparer un nouveau précontrôle
  distinct sur **l'image à qualifier**, puis la campagne protégée.
  **Valider :** 500 sessions réellement authentifiées et activités métier
  simultanées pendant le plateau de 120 s, p95 ≤ 2 s, zéro timeout, échec,
  écriture non confirmée ou donnée étrangère, 500 déconnexions et zéro
  session/tâche résiduelle ; conserver budgets, rampe, cohorte et preuves.
  Le succès précédent à 100 ne valide pas 500 ni une nouvelle image.

### À démarrer (26)

- [ ] **F04 — Configuration et circuits** (`ft-configuration`). Formulaires
  typés, transitions, acteurs, délais, simulations et versions. **Valider :**
  une règle changée ne réécrit pas les dossiers passés ; entrée invalide,
  étape sautée, retard et refus de rôle sont testés en admission et soutenance.
- [ ] **F05 — Gouvernance des données** (`ft-data-governance`). Audit,
  fichiers privés, antivirus/quarantaine, quotas, consentements et rétention.
  **Valider :** accès, export, purge et téléchargement selon tenant/objet ;
  fichier dangereux bloqué ; piste d'audit complète et données restaurables.
- [ ] **F11 — Candidatures** (`ft-admissions`). Campagnes, formulaires, pièces,
  compléments, concours/entretiens, décisions et conversion. **Valider :**
  un candidat neuf devient un unique dossier/inscription, sans ressaisie,
  même en rejeu ou concurrence ; calendrier, capacité et refus appliqués.
- [ ] **F12 — Cycle académique** (`ft-academic-lifecycle`). Programmes,
  équivalences, suspensions, abandons, réorientations et réinscriptions.
  **Valider :** transferts et statuts historisés, résultats clos intacts,
  aucun ajout hors période, y compris après reprise.
- [ ] **F08 — Cours et activités** (`ft-learning-activities`). Sections,
  ressources, quiz, vidéos, devoirs, discussions et groupes liés à Studio.
  **Valider :** enseignant publie, apprenant accède/remet, correcteur répond ;
  aucun contrôle factice, fichiers et permissions vérifiés dans LMS et SIS.
- [ ] **F09 — Correction** (`ft-grading`). Relier copie, rubrique, feedback
  et nouvelles remises aux évaluations SIS. **Valider :** réponse LMS en
  retard ou répétée n'écrase jamais un résultat clos ; publication seulement
  après validation humaine nominative et vérification des conflits.
  **Preuve bornée au cutoff vagues 15/16 :** proposition LMS obligatoire,
  approbation/rejet audité, rejeu et concurrence qualifiés sur fixtures dans
  les deux SIS ; pas d'échange natif Open edX ni de réception humaine réelle.
  **F09 reste partiel**, copies/rubriques/remises et circuit complet à valider.
- [ ] **F10 — Espaces pédagogiques** (`ft-learning-workspaces`). Cours,
  reprises, travaux à rendre/corriger, progression et agenda par rôle.
  **Valider :** valeurs et actions réelles, refus et états vide/erreur sur
  ordinateur et mobile ; mêmes droits côté API et interface.
- [ ] **F13 — Résultats officiels** (`ft-official-results`). Coefficients,
  arrondis, absences, rattrapages, compensations, crédits, jurys et PV.
  **Valider :** calcul reproductible sur cas limites, brouillon privé,
  publication validée et rectification traçable sans réécriture silencieuse.
- [ ] **F14 — Emploi du temps** (`ft-timetable`). Salles, enseignants,
  groupes, vacances, remplacements, présences et justificatifs.
  **Valider :** chevauchement refusé ou arbitré explicitement, changement
  notifié aux destinataires corrects dans les deux SIS, historique conservé.
- [ ] **F15 — Finance** (`ft-finance`). Tarifs, aides, factures, échéances,
  paiements partiels, reçus, impayés et remboursements. **Valider :**
  inscription → facture → encaissement → solde arithmétiquement réconciliés ;
  références uniques, double validation et refus des paiements fictifs.
- [ ] **F16 — Paiement/ERP** (`ft-payment-erp`). Prestataires du pays pilote,
  callbacks signés, devises, comptabilité et paie. **Valider :** paiement,
  attente, échec, doublon et remboursement rapprochés avec source externe ;
  le retour navigateur seul ne confirme jamais un encaissement.
- [ ] **F17 — Communications** (`ft-communications`). Annonces,
  conversations, calendriers, fournisseurs réels et consentements.
  **Valider :** parent multi-enfants et personnel ne voient que leurs
  destinataires ; panne, reprise, refus et révocation sont observables.
- [ ] **F18 — Stages/recherche** (`ft-internships-research`). Offres,
  conventions, tuteurs, missions, livrables, évaluations et jurys.
  **Valider :** dossier complet signé/archivé ; partenaire cantonné à sa
  mission et à ses dates, retrait d'accès effectif à expiration.
- [ ] **F19 — RH/gouvernance** (`ft-hr-governance`). Recrutement, contrats,
  affectations, congés, remplacements, formation et paie.
  **Valider :** approbations par personnes distinctes, confidentialité des
  documents RH et rapprochement des écritures avec l'ERP.
- [ ] **F20 — Services du campus** (`ft-campus-services`). Bibliothèque,
  cantine, transport, internat, équipements, achats et maintenance.
  **Valider :** demande → capacité/stock → validation → service/frais,
  avec conflit, annulation et refus contrôlés sur chaque service activé.
- [ ] **F21 — Réclamations** (`ft-complaints`). Services responsables,
  délais, relances, recours, délégation parentale et conservation.
  **Valider :** dossier privé, résolution notifiée, recours traçable et
  rectification uniquement par action autorisée, sans altération automatique.
- [ ] **F22 — Titres et documents** (`ft-credentials`). Gabarits,
  génération, signatures, diplômes, badges, archives et alumni.
  **Valider :** acquis requis et signataires vérifiés avant émission ; URL
  publique limitée de vérification, révocation vérifiable et aucune fuite
  des dossiers sous-jacents.
- [ ] **F23 — Recherche/rapports** (`ft-reporting`). Filtres enregistrés,
  exports volumineux et provenance des indicateurs. **Valider :** résultats
  paginés complets, calculs/périodes/fraîcheur explicites, aucun champ ou
  établissement hors droit et aucun tronquage silencieux.
- [ ] **F24 — Interopérabilité** (`ft-interop`). LTI 1.3, calendriers et
  standards sélectionnés selon le pack. **Valider :** échanges réels avec
  partenaire autorisé, version/identité/certificats contrôlés, refus et
  rejeux traçables ; ne pas promettre un standard non testé.
- [ ] **F25 — Recommandations** (`ft-recommendations`). Objectifs,
  prérequis, compétences et acquis validés. **Valider :** chaque suggestion
  cite ses données et sa règle, mise à jour après changement d'acquis,
  sans sanction ni classement opaque automatique.
- [ ] **F26 — IA/OCR** (`ft-ai`). Recherche sourcée et permissionnée,
  préremplissage OCR et brouillons pédagogiques supervisés.
  **Valider :** contrôle humain avant écriture/publication, citations
  consultables, refus tenant/secret, coût plafonné, désactivation et
  comportement explicite sans fournisseur autorisé.
- [ ] **F27 — Mobile et packs** (`ft-mobile-profiles`). Accessibilité,
  langues, fuseaux, formats, PWA et éventuel hors ligne.
  **Valider :** tâches par profil aux tailles prévues, clavier/lecteur
  d'écran, conflit de synchronisation visible et cache sensible révoqué
  après logout ou retrait d'accès.
- [ ] **F28 — Réseau d'établissements** (`ft-network`). Console plateforme
  séparée, packs/licences, affiliations et suspensions.
  **Valider :** création, mise à jour, suspension et reprise de deux
  établissements sans effacer les dossiers, fuite inter-tenant ni droit
  métier global implicite.
- [ ] **F29 — Exploitation** (`ft-operations`). Installation LMS/SIS,
  secrets/TLS, mises à jour, files, alertes et sauvegardes hors instance.
  **Valider :** installation neuve puis mise à jour, panne simulée et
  restauration SIS+LMS+fichiers dans un environnement distinct, avec
  RPO/RTO mesurés et comptes/MFA/données identiques.
- [ ] **F30 — Recette complète** (`ft-acceptance`). Tous les parcours,
  rôles, profils, offres, formulaires, boutons et erreurs sur les deux SIS.
  **Valider :** matrice des 94 exigences et du présent ajout, tests
  automatisés + navigateur + concurrence + coupures, preuves par cas,
  zéro anomalie critique ouverte ; résultats négatifs conservés.
- [ ] **F31 — Livraison institutionnelle** (`ft-release`). Guides par
  rôle, support, artefacts versionnés, reprise et retour arrière.
  **Valider :** une installation neuve et une mise à jour faites depuis la
  documentation, tâches réalisables sans console développeur, retour
  arrière testé et limites/identités/fichiers inchangés.

### Bloquées (3)

- [ ] **Précontrôle de charge admission** (`admission-live-preflight`).
  **Débloquer/valider :** budgets CPU/swap effectifs conformes dans les
  cgroups du générateur, PostgreSQL et Redis, observer borné, cohortes
  protégées, sauvegarde et autorisation d'une campagne distincte.
- [ ] **Charge admission 100** (`admission-one-run`). **Débloquer/valider :**
  après le précontrôle, une seule campagne bornée avec seuils et cohorte
  scellés ; verdict sur toutes les réponses/écritures et déconnexions,
  sans transformer un échec en réussite.
- [ ] **F32 — Pilote externe** (`external-pilot`). **Débloquer/valider :**
  serveur/domaines, services LMS/SMTP/prestataires et référents habilités
  fournis ; homologation par établissement après restauration indépendante,
  alertes, sécurité et parcours réels. Aucun pilote public sans ces accès.

### Travaux nouveaux non isolés dans les 34 tâches précédentes (5)

Les autres exigences du cahier SIS/LMS/ERP restent rattachées aux lots F
ci-dessus ; ces cinq tâches sont suivies séparément pour éviter que leur
absence soit masquée par un lot plus large. Elles conditionnent F30.

- [ ] **Admin : créer et attribuer des rôles et permissions**
  (`iam-role-authoring`, F02/F03/F05). L'API possède déjà des groupes Django
  et un catalogue de permissions en lecture, mais le formulaire utilisateurs
  présente des rôles fixes et aucune console d'édition des rôles n'est
  proposée. **Reste :** permettre à l'admin *habilité* d'un établissement
  de créer, cloner, modifier, désactiver et attribuer un rôle à plusieurs
  utilisateurs, de choisir ses permissions par action/ressource dans le
  registre et de publier une permission métier nouvelle seulement après
  contrôle du module/propriétaire et de l'approbation requise. Versionner
  rôles, politiques et groupe ; isoler leur stockage et leur lecture par
  tenant **et** variante SIS, sans modifier les droits d'un autre tenant.
  **Valider :** créer un rôle « tuteur », lui ajouter uniquement lecture de
  ses étudiants, l'attribuer à un staff puis lui retirer ce droit : API,
  menus, fichiers et LMS accordent/refusent immédiatement selon le cas.
  Refuser doublon, clé inconnue, tenant étranger, rôle privilégié ou
  auto-attribution non approuvés ; vérifier MFA/SoD pour l'escalade,
  audit auteur/avant/après, conservation après redémarrage, révocation
  des sessions/caches et reprise sans perte des groupes existants.
- [ ] **Deux portails authentifiés : Staff et Étudiant/Élève**
  (`staff-student-portals`, F02/F07/F10/F30). Des écrans staff et
  apprenant existent, mais le choix des espaces et plusieurs liens restent
  basés sur des noms de rôles fixes ; ceci ne démontre pas « chaque
  utilisateur ne fait que ce qu'il peut ». **Reste :** une entrée Staff
  (direction, enseignant, scolarité, RH, comptable, etc. selon droits
  effectifs) et une entrée Étudiant/Élève (dossier, cours, activités,
  résultats et paiements personnels autorisés), sur secondaire et
  supérieur. Le même design ERP figé est conservé ; tableaux, boutons,
  actions, recherche, export et états vide/erreur dépendent des capacités
  réelles du tenant, de l'affiliation et de l'objet. **Valider :** chacun
  des deux comptes n'obtient que son menu et ses propres données ; URL
  directe, appel API, fichier, export, LMS et job hors droit sont refusés
  côté serveur ; un staff cumule deux rôles sans privilège indu, puis
  retrait/expiration change menu et réponse immédiatement (y compris
  session déjà ouverte). Tester l'entrée après SSO, changement de tenant,
  rechargement, mobile et redémarrage. Conserver les espaces parent,
  candidat public et compte personnel existants, sans les confondre avec
  une entrée Staff ou donner aux parents accès aux autres enfants.
- [ ] **Gamification pédagogique optionnelle** (`lms-gamification`,
  F08/F22/F25). Points, niveaux, défis, objectifs, séries, récompenses,
  classements facultatifs et certificat de progression ne sont pas
  couverts par la seule tâche « badges ». **Valider :** un événement de
  cours réel attribue la récompense une seule fois après rejeu ; dates,
  retrait de résultat et fraude changent l'état conformément à une règle
  versionnée. Paramétrage par établissement, désactivation sans perte de
  progression, classements privés/consentis et aucun score hors tenant.
- [ ] **Courriers et circuits documentaires ERP** (`erp-document-circuits`,
  F05/F22). Compléter les documents/signatures existants par courrier
  entrant/sortant, classement, affectation, approbation, versions,
  recherche et archivage/destruction selon la conservation.
  **Valider :** courrier reçu → service habilité → validation distincte →
  envoi/archivage ; document altéré, destinataire étranger et étape sautée
  refusés ; historique, confidentialité et restauration vérifiés.
- [ ] **Immobilisations et amortissements ERP** (`erp-fixed-assets`,
  F15/F20). Relier achats, inventaire et maintenance aux fiches d'actif
  (numéro unique, propriétaire, lieu, affectations, état, sortie/réforme)
  et aux règles comptables d'amortissement configurées.
  **Valider :** achat → activation → transfert → entretien → réforme,
  stock/actif/journal réconciliés ; dotation correcte sur cas limites,
  double immobilisation et écriture sur période close refusées.

### Exigences initiales encore absentes ou non vérifiées (23 sur 94)

Le reste des 94 exigences est **partiel**, sauf 1.2 déjà vérifiée. Leurs
conditions propres (deux ou trois contrôles par exigence) sont conservées dans
`requirements[].acceptance_checks` de la
[matrice](functional-acceptance-matrix.json) ; le lot F correspondant
ci-dessus ne remplace jamais leur validation individuelle. Les lacunes les
plus nettes sont détaillées ici, avec les identifiants **du cahier initial**
(indépendants des sections 1–10 du cahier complémentaire ci-dessous).

| Exigence initiale / statut | Condition de validation propre |
|---|---|
| 4.4 Comptabilité/budgets — absente | Écriture recettes/dépenses équilibrée par journal/centre de coûts, banque/créances/dettes/budget rapprochés ; période close ou rejeu ERP ne génèrent pas d'écriture. |
| 4.8 Stocks/équipements — absente | Réception et sortie des sept familles, stock initial + mouvements = stock final, seuil d'alerte ; sortie au-delà du disponible et double réception refusées, auteur conservé. |
| 4.9 Achats/fournisseurs — absente | Huit étapes d'un achat jusqu'au paiement, réception partielle, facture rapprochée au budget/stock ; auto-approbation et double réception/facture refusées. |
| 5.1 Assistant IA — absent | Questions réelles de cinq profils, contexte/réponse limités au rôle/tenant ; données interdites, source absente, indisponibilité et révocation testées, zéro décision officielle automatique. |
| 5.2 Tuteur IA — absent | Cours réel : explication adaptée, exercice, indice et révision sourcés ; contexte interdit et panne refusés sans dégrader le parcours humain. |
| 5.3 Génération IA — absente | Générer/éditer/valider chaque type de ressource ; brouillon jamais publié sans accord humain, retrait d'accès effectif. |
| 5.4 Correction IA — absente | Proposition sur copie modifiable/refusable par correcteur ; note officielle seulement après validation humaine, jamais sur source interdite. |
| 5.5 Décrochage — absent | Indicateurs connus, alerte explicable seulement au conseiller habilité ; aucune sanction/exclusion automatique ni donnée inventée. |
| 5.6 Conseiller IA — absent | Plusieurs parcours compatibles avec acquis/prérequis, alternatives expliquées ; aucune inscription/réorientation sans décision humaine. |
| 5.7 OCR — absent | Chaque catégorie de document extraite puis corrigée/approuvée ; aucune donnée officielle écrasée avant approbation. |
| 5.8 Analytics IA — absents | Analyses rapprochées des données réelles filtrées par date/périmètre ; formule, fraîcheur et sources vérifiées, aucune valeur inventée. |
| 6.3 Badges — absents | Condition réellement acquise, badge unique avec métadonnées/preuve ; conditions absentes, doublon et divulgation refusés ; révocation visible. |
| 6.6 Alumni — absent | Diplôme puis portefeuille conservé, inscription volontaire, mentorat/événement/enquête ; refus de diffusion non consentie et d'accès à l'ancien dossier privé. |
| 8.6 Licences — absentes | Essai, abonnement, modules/quotas, facture, renouvellement ; quota atteint puis suspension/réactivation sans perte ni fuite inter-tenant. |
| 9.1 Super Admin — absent | Console plateforme gère deux établissements et abonnements sans accorder d'accès métier aux dossiers des tenants. |
| 10.1 Mobile — absent | Installation Android **et** iOS, tâches apprenant/enseignant/parent réelles ; session/appareil révoqué ne révèle plus les données privées. |
| 10.2 Hors ligne — absent | Cours téléchargé sous droit, travail préparé hors réseau puis synchronisé une fois ; conflit et accès révoqué/expiré bloquent les données privées. |
| 10.5 Projets — absents | Équipe, jalons, livrables et évaluations individuelles/collectives ; autre équipe interdite en lecture et écriture. |
| 10.7 Recherche globale — partielle | Au cutoff vague 18 : apprenants, factures, vrais cours et évaluations SIS reliées au LMS dans les deux SIS, documents sources universitaires et bulletins scolaires `BUL-<id>` ; palette/fiches sans cache partagé, parcours staff et apprenant qualifiés sur fixtures, facture d'autrui absente de la recherche et détail 404 sans numéro. Restent catalogue LMS natif exhaustif et parcours parents/enseignants/multi-tenant/révocations exhaustifs ; aucun statut promu, aucun acquis déduit du chantier Studio non qualifié/non publié. |
| 10.9 Portail public — absent | Formations publiées, actualités et procédure consultables sans connexion ; candidature démarrée, brouillons et dossiers privés inaccessibles. |
| 10.10 Signature — non vérifiée | Habilitation approuvée par tiers, signature, archive et notification ; auto-approbation, mandat révoqué et document altéré refusés. |
| 11 Cycle candidat → alumni — non vérifié | Neuf étapes 11.1–11.9 sur un identifiant continu ; refus/doublons/clôtures/coupures et restauration isolée contrôlés, versions et preuves navigateur/API/BD conservées. |
| 11.9 Après formation — absent | Portefeuille conservé et adhésion alumni volontaire ; refus hors tenant, historique/rejeu contrôlés avant clôture du cycle. |

## B. Cahier complémentaire : contrôle des accès

Chaque modèle ci-dessous est une **capacité à implémenter ou à prouver**,
pas un module réputé existant. Une décision doit être prise avant l'action
sur API, vues, fichiers, tâches et intégrations ; `DENY` par défaut si tenant,
attribut, relation ou politique requis est manquant. Évaluer les conflits
entre modèles selon une règle documentée ; une interdiction explicite et
une classification obligatoire ne sont jamais annulées par un rôle permissif.

| Point du cahier | Livrable et condition exacte de validation |
|---|---|
| 1.1 RBAC | Créer/dupliquer/désactiver rôles personnalisés, multiples, temporaires, propres au tenant, avec héritage explicite et permissions par module. Tester attribution, retrait, expiration et refus de `student.read/create/update/delete/export/import` hors rôle ; aucun `admin.all` implicite. |
| 1.2 ABAC | Décider sur attributs utilisateur, ressource, action et contexte (classe, département, campus, statut, sensibilité). Deux enseignants de même rôle : celui affecté lit son dossier, l'autre reçoit 403 ; changement d'affectation révoque lecture et export. |
| 1.3 PBAC | Politiques centralisées, versionnées et isolées par tenant/module. Tester note clôturée, facture comptabilisée, dossier médical et inscription conditionnelle : refus ou validation supplémentaire conformément à la politique ; modification n'altère pas les décisions historiques. |
| 1.4 ReBAC | Relations vérifiées parent/enfant, enseignant/classe, direction/département, tuteur/apprenant et encadrant/travail. Ajouter et retirer la relation ; accès au seul objet lié, refus de l'objet voisin, de l'autre enfant et de l'autre tenant. |
| 1.5 TBAC | Dates, horaires, jours, fuseau, durée et retrait automatique. Tester avant/pendant/après fenêtre de note ou examen, passage à minuit et changement de fuseau ; accès expiré refusé même avec jeton encore valide. |
| 1.6 GBAC | Groupes manuels, dynamiques, imbriqués et temporaires. Tester adhésion/retrait, absence de boucle d'héritage, recalcul après changement de classe et absence de privilège hors groupe/tenant. |
| 1.7 MBAC | Activation du module séparée de la permission de chaque action ; SIS/LMS/finance/RH/bibliothèque/IA/titres. Tester module coupé, activé sans permission, permission révoquée et réactivation sans fuite de données. |
| 1.8 MAC | Niveaux public/interne/confidentiel/restreint/très restreint et habilitations. Un rôle autorisé sans habilitation suffisante reçoit 403 sur dossier sensible, fichier, export et copie ; reclassification est historisée. |
| 1.9 DAC | Propriétaire partage lecture/commentaire/modification puis retire l'accès ; partage au-delà de son propre périmètre interdit, retrait effectif aussi sur lien de téléchargement existant. |
| 1.10 ACL | Accès directs par utilisateur/groupe sur document, cours et ressource. Tester ajout/retrait, héritage, collision avec interdiction et absence de droit sur un objet adjacent. |
| 1.11 CBAC | Appareil/IP/réseau/heure et session évalués selon politique tenant. Contexte reconnu autorise ; contexte interdit refuse ou demande un second facteur vérifié ; échec du signal ne contourne pas la règle. |
| 1.12 Risque | Opération de masse ou appareil inhabituel déclenche blocage, MFA renforcée ou approbation. Tester seuil configuré, identité de l'approbateur et impossibilité de rejouer une décision expirée ; pas de décision opaque sans trace. |
| 1.13 Capabilities | Jeton signé/opaque imprévisible, limité ressource/action/tenant/durée, révocable et éventuellement à usage unique ; refus après expiration, réutilisation, partage hors périmètre ou modification du jeton. |
| 1.14 SoD | Incompatibilités de rôles et d'acteurs imposées à l'attribution **et** à l'action : dépense, note, export, privilège. Le créateur ne peut approuver lui-même ; journal conserve deux identités distinctes. |
| 1.15 Break-Glass | Motif, MFA renforcée, portée minimale, durée, notification et révision indépendante a posteriori obligatoires. Tester expiration/révocation, refus sans motif/MFA et journal de chaque accès ; jamais de super-admin permanent. |
| 1.16 Multi-tenant | Affiliation et rôle distincts par établissement. Appel avec host, schéma, JWT, objet ou fichier d'un autre tenant refuse avant lecture/mutation ; contrôle identique pour jobs, exports, LMS et liens signés. |
| 1.17 Hiérarchie | Campus → faculté → département : délégation et héritage explicites, limitées et révocables. Tester filiale autorisée, campus voisin refusé et interdiction explicite prioritaire. |
| 1.18 Synthèse | Vérifier les dix-sept mécanismes précédents selon leur pertinence par pack, avec justification documentée pour ceux désactivés ; RBAC+ABAC+PBAC+ReBAC, SoD, Break-Glass et isolation sont essentiels ; TBAC, GBAC, MBAC, MAC, ACL, contexte et risque sont de priorité élevée, DAC et capacités de priorité moyenne. Aucun menu masqué ne remplace un contrôle serveur. |

### 2. Moteur central et administration

Un **point de décision (PDP)** renvoie `ALLOW`, `DENY`, `STEP_UP` ou
`APPROVAL`, motif et version de politique ; un **point d'application (PEP)**
contrôle toute opération métier avant accès. Chaque décision expose
tenant, acteur, ressource et action dans une trace non sensible ; mêmes
attributs donnent la même décision en SIS, LMS et tâches asynchrones.
Une panne du moteur ne produit jamais une autorisation par défaut.

| 2.1 Composant | Condition de validation |
|---|---|
| IAM | Identité stable, statut et affiliations réconciliés ; suspension et suppression de session empêchent immédiatement API/SIS/LMS. |
| Role Manager | Création/attribution/retrait/version d'un rôle en un tenant n'altèrent ni autre tenant ni droits historiques. |
| Permission Registry | Catalogue stable `{module}.{resource}.{action}` avec propriétaire, version et défaut refusé ; doublon ou permission inconnue rejeté. |
| Policy Engine | Version/motif/test de simulation conservés ; règle de refus prioritaire et replay d'une décision à sa version d'origine. |
| Relationship Engine | Relations datées et vérifiées côté serveur ; suppression révoque tous les accès dépendants. |
| Tenant Resolver | Host, schéma, identité et objet concordent ; incohérence refuse avant requête de données. |
| Context Engine | Horloge/fuseau, IP et appareil utilisés seulement selon politique explicite ; valeurs absentes suivent le refus prévu. |
| Risk Engine | Niveau de risque explicable et seuil tenant testé pour accès normal, step-up et blocage. |
| SoD Engine | Conflits vérifiés à l'attribution et lors de l'approbation ; auteur et approbateur distincts. |
| Audit Engine | Autorisation, refus, modification de politique et export traçables sans secret, sans édition via API. |
| Session Manager | Liste et révocation individuelle/globale ; session révoquée inutilisable sur toutes les routes concernées. |

- [ ] **2.2 Identifiants de permission.** Publier et tester
  `sis.student.{read,create,update,delete,export,import}`,
  `lms.course.{create,publish}`, `lms.assignment.grade`,
  `lms.exam.manage`, `finance.invoice.{read,create}`,
  `finance.payment.{record,refund}`, `finance.report.export`,
  `iam.user.create`,
  `iam.role.assign`, `iam.permission.manage`, `iam.policy.update` et
  `credentials.diploma.{issue,revoke,verify}` avec variantes
  `read.{own,assigned,department,tenant}` et `export.restricted`.
  **Valider :** refus des clés inconnues, permission fine par action/objet
  et absence de conversion automatique d'un rôle SIS en privilège LMS.
- [ ] **2.3 Console de sécurité.** Rôles, groupes, politiques, relations,
  habilitations, classification, fenêtres, campus, MFA, approbations,
  accès temporaires, SoD, sessions, appareils, décisions et historique
  disposent d'écrans et API autorisés. **Valider pour chacun :** créer,
  consulter, modifier/révoquer si applicable, simuler un accès
  utilisateur/ressource/action avec explication et version de règle ;
  utilisateur non autorisé refusé, changement audité et visible après
  redémarrage.

## C. Cahier complémentaire : sécurité

- [ ] **3.1 Authentification/identité.** Qualifier MFA/TOTP, passkeys
  WebAuthn, SSO, OAuth/OIDC, annuaires LDAP/AD et SCIM selon les packs
  annoncés. **Valider séparément :** connexion, échec, récupération,
  provisionnement/suspension, sessions/appareils reconnus puis révoqués,
  politique de mot de passe/renouvellement et verrouillage temporaire
  contre essais suspects ; Argon2id si retenu avec paramètres documentés.
  Un connecteur sans fournisseur réel reste « non qualifié ».
- [ ] **3.2 Protection des données.** TLS, chiffrement au repos,
  gestion/rotation de clés et secrets, masquage, pseudonymisation,
  anonymisation, rétention/purge, sauvegardes chiffrées et téléchargements
  contrôlés. **Valider pour chaque type de donnée sensible :** accès
  autorisé/refusé, chiffrement effectif, rotation/restauration sans perte,
  secrets absents du code/logs/exports, fuite détectée/bloquée selon
  politique et purge vérifiée.
- [ ] **3.3 Opérations sensibles.** Note officielle, facture/remboursement,
  export personnel, suppression de dossier, rôle/admin, diplôme, politique
  et dossier confidentiel :
  permissions spécifiques, justification, MFA ou approbation indépendante
  selon règle. **Valider :** autorisation à deux acteurs, refus de
  l'auto-approbation, audit nominatif et rollback sans publication fictive.
- [ ] **3.4 API.** Jetons OAuth/OIDC courts et validés, rotation/révocation
  refresh, gateway/rate limiting, entrées strictes, CORS, webhooks signés,
  mTLS si requis, clés API révocables et journal sans secrets. **Valider :**
  révocation d'une intégration puis refus immédiat, tests d'expiration,
  audience, émetteur, signature, injection, débit, tenant/objet sur chaque
  endpoint ; masquer un bouton ne compte pas comme un refus serveur.
- [ ] **3.5 Fichiers.** Taille/type réel, antivirus/quarantaine, rejet
  d'exécutables et chemins dangereux, stockage privé, version/empreinte
  et URL de téléchargement courte/révocable. **Valider :** fichiers
  valides, malformés et dangereux, traversal, autre tenant, expiration
  et téléchargement audité.
- [ ] **3.6 Journal/surveillance.** Connexion, mot de passe, rôles, refus,
  consultation sensible, import/export, document, module et urgence.
  **Valider :** acteur/tenant/action/horodatage/résultat corrélables,
  consultation permissionnée, intégrité/rétention, alertes vérifiées et
  absence de mots de passe, tokens ou données médicales dans les traces.
- [ ] **3.7 Infrastructure.** Séparer environnements, analyser
  dépendances/images, contrôler pare-feu, secrets et vulnérabilités,
  détecter les intrusions, superviser et tester régulièrement réponse à
  incident/continuité et pénétration autorisée. **Valider :**
  preuves d'alertes, restauration isolée chiffrée, sauvegarde hors hôte,
  rotation de secret et exercice de sécurité autorisé avec corrections
  critiques closes avant production.

## D. Cahier complémentaire : import/export universel

Le **Data Transfer Center** doit couvrir les entités métier permises :
étudiants, enseignants, parents, classes/groupes, cours, inscriptions,
notes, présences, factures/paiements, personnel, formations, diplômes,
compétences, utilisateurs, salles, équipements, fournisseurs et
bibliothèque. Exclure par défaut secrets, sessions, journaux de sécurité
bruts et tables techniques. Chaque entité déclare explicitement
`import`, `export` ou « non applicable » motivé. Les écritures passent
par le service métier propriétaire, jamais par un accès SQL générique.

- [ ] **4.1 Formats.** CSV, XLSX, JSON et XML import/export ; XLS
  seulement si besoin institutionnel confirmé ; PDF export uniquement
  (sauf extraction OCR spécialisée) ; ZIP et ZIP+JSON pour paquets.
  **Valider chaque format annoncé :** aller-retour sur accents, dates,
  nombres, encodages, feuilles et relations ; fichier corrompu ou trop
  volumineux rejeté sans écriture ; format non annoncé explicitement refusé.
- [ ] **4.2.1 Sélection.** Module, entité, fichier, feuille, encodage,
  séparateur, langue et date visibles. **Valider :** mauvais type,
  taille, feuille et encodage rejetés avant staging, aucune écriture.
- [ ] **4.2.2 Mapping.** Colonnes détectées puis mappées manuellement
  (`Nom`→`last_name`, `Matricule`→`student_number`, etc.), profil réutilisable
  versionné. **Valider :** champs manquants/ambigus signalés, réemploi
  sur fichier compatible et refus d'un champ non autorisé.
- [ ] **4.2.3 Validation.** Champs requis, e-mail, téléphone, dates,
  identifiants, valeurs, références et permissions. **Valider :**
  référence de classe hors tenant, note hors barème, date invalide et
  doublon déclarés avec numéro de ligne, sans mutation du dossier.
- [ ] **4.2.4 Doublons.** Ignorer, mettre à jour, créer uniquement,
  signaler, remplacer certains champs avec droit renforcé ; clé stable,
  jamais prénom+nom. **Valider :** import répété sous la même clé
  d'idempotence crée zéro doublon ; conflit retourne un état vérifiable.
- [ ] **4.2.5 Aperçu.** Totaux valides/invalides/doublons/créations/
  mises à jour et champs modifiés, rapport téléchargeable.
  **Valider :** nombres égaux au staging, droits et données source
  inchangés avant confirmation ; nouvelle validation si source ou règle
  a changé.
- [ ] **4.2.6 Exécution.** Recontrôler tenant, rôle et contexte au
  lancement **et à chaque lot** ; progression et rapports, erreurs sans
  état partiel incohérent, reprise idempotente et annulation/retour arrière
  uniquement si sûr. **Valider :** gros fichier interrompu puis relancé :
  résultat exactement une fois, relations valides, rejets traçables.
- [ ] **4.3 Export.** Colonnes, lignes, filtres, période, campus,
  classe, département, ordre, nom de fichier et format choisis ; droits
  séparés `sis.student.export.personal_data`,
  `sis.student.export.academic_data`, `sis.student.export.financial_data`,
  `sis.student.export.all_fields` en plus de `sis.student.export`.
  **Valider :** aucun
  champ/ligne hors périmètre, volume borné ou approbation supplémentaire,
  génération complète sans troncature, lien expirable/révocable et audit.
- [ ] **4.4 Relations/migration.** Ordre classes → étudiants → cours →
  inscriptions → factures, références stables, manifeste ZIP JSON.
  **Valider :** dépendance absente/étrangère refusée, migration isolée
  dans une base vide puis rejeu sans doublon et rapprochement des comptes.
- [ ] **4.5 Historique.** Auteur, tenant, module, entité, fichier,
  date, volume, statut, créations/mises à jour/rejets et rapport.
  **Valider :** attente → cours → réussi/partiel/échec visibles, rapport
  permissionné, révocation du téléchargement et compensation seulement
  pour opérations réversibles.

### 5. Modèles officiels

Pour chaque type de donnée applicable : télécharger CSV/XLSX depuis la
table concernée, versionner manifeste/champs/types/requis, fournir un
exemple **synthétique**, tester round-trip et refuser le modèle obsolète
ou d'un autre établissement sans migration explicite.

| Modèle | Champs contractuels et validation spécifique |
|---|---|
| 5.1 Students | `student_number,last_name,first_name,email,phone,birth_date,class_code` : matricule unique par périmètre, classe du tenant et dates valides ; rejet de classe étrangère. |
| 5.2 Teachers | `teacher_number,last_name,first_name,email,department_code,status` : identifiant stable, département existant et statut reconnu ; pas de promotion LMS automatique. |
| 5.3 Courses | `course_code,course_name,department_code,level,credits,teacher_number` : enseignant affectable, crédits valides et cours créé par le contrat LMS propriétaire. |
| 5.4 Grades | `student_number,course_code,assessment_code,score,max_score,academic_period` : barème et période valides, import en **brouillon** puis validation officielle par autre acteur. |
| 5.5 Payments | `student_number,invoice_reference,payment_reference,amount,currency,payment_date,payment_method` : référence unique, montant réconcilié ; aucune confirmation créée sans source fiable ou validation autorisée. |
| 5.6 Catalogue | SIS : Students, Parents, Guardians, Admissions, Enrollments, Classes, Groups, Academic Records ; LMS : Courses, Subjects, Lessons, Assignments, Questions, Grades, Competencies ; RH : Employees, Teachers, Contracts, Departments, Leave Requests ; Finance : Invoices, Payments, Expenses, Scholarships, Budgets ; infrastructure : Buildings, Rooms, Equipment, Inventory ; bibliothèque : Books, Authors, Categories, Loans ; Credentials : Diplomas, Certificates, Badges ; organisation : Campuses, Faculties, Departments, Programs ; utilisateurs : Users, Groups, Role Assignments, External Identities. **Valider chaque modèle activé :** contrat, round-trip, droits, tenant et références ; rôles/politiques nécessitent une approbation distincte. |

### 6 à 10. Architecture, options et configuration du transfert

Les dix services du cahier sont des **responsabilités logiques** : réutiliser
les composants Django/Celery existants lorsque cela satisfait le contrat,
plutôt que créer dix microservices sans nécessité.

| Point 6 | Condition de validation |
|---|---|
| import-service | Réception authentifiée, type/taille et stockage temporaire contrôlés ; aucun enregistrement métier avant validation. |
| export-service | Filtres tenant/objet/colonne appliqués au calcul et au téléchargement ; fichier complet et révocable. |
| schema-registry | Manifeste de chaque entité/version publié ; champ inconnu ou version non supportée refusé. |
| template-service | Modèles générés depuis le schéma versionné ; exemple synthétique et test round-trip. |
| mapping-service | Correspondances enregistrées par tenant/version ; erreur sur colonne ambiguë ou champ interdit. |
| validation-service | Rapport par ligne et référence, même règle avant aperçu et avant écriture. |
| deduplication-service | Identifiant stable et stratégie explicite ; rejeu à clé identique sans nouvelle création. |
| transfer-job-service | Lots bornés, progression, panne puis reprise, état final sans succès fictif. |
| audit-service | Auteur/tenant/version/résultat consultables selon droit ; aucune donnée brute sensible dans les logs. |
| storage-service | Quarantaine, chiffrement, expiration et nettoyage testés ; aucun accès direct par URL devinée. |

- [ ] **7. Manifeste JSON.** Déclarer `template.name`, `template.version`,
  `template.module`, `template.entity`, `template.format`,
  `options.tenant_required`, `options.duplicate_strategy`,
  `options.allow_updates`, `options.validate_relations` et, pour chaque
  champ, `name/type/required/unique`
  ou `format`/`entity` si nécessaire. **Valider :** le modèle Students
  génère formulaire, validation et aperçu identiques ; version inconnue,
  type invalide et référence hors tenant sont rejetés avant exécution.
**8. Options avancées.** Pour chacune, tester aussi un accès refusé dans un
autre tenant et un échec métier explicite ; ne proposer l'option que si le
parcours complet est livré.

| Option (point 8) | Condition spécifique de validation |
|---|---|
| Template Builder | Un administrateur publie un modèle personnalisé validé par le schéma ; champ interdit refusé. |
| Template Versioning | Ancien modèle reste lisible ; nouvelle version et migration explicite sans réinterprétation silencieuse. |
| Auto Field Mapping | Deux colonnes connues reconnues, une ambiguïté signalée avant écriture. |
| Custom Mapping | Profil enregistré par tenant, réutilisé puis révoqué ; champ hors droit rejeté. |
| Data Transformation | Date, devise et valeur converties selon règle affichée ; entrée non convertible rejetée par ligne. |
| Validation Rules | Règle métier versionnée, testée avant staging et après édition ; violation refuse le lot concerné. |
| Duplicate Detection | Même identifiant stable identifié dans fichier et base ; stratégie explicite avant exécution. |
| Import Preview | Totaux et changements prévus égaux au rapport de staging, aucune écriture avant confirmation. |
| Batch Processing | Gros fichier réparti en lots bornés, reprise sans doublon et erreur isolée sans corruption. |
| Background Jobs | État/progression récupérables après redémarrage, terminal succès/partiel/échec exact. |
| Import Rollback | Créations/modifications réellement réversibles compensées ; opération irréversible refuse l'annulation. |
| Export Profiles | Profil de colonnes/filtres sauvegardé puis réévalué aux droits actuels de l'utilisateur. |
| Scheduled Export | Planification autorisée puis révoquée ; tâche refuse si rôle/tenant a changé à l'exécution. |
| API Import/Export | Authentification/signature, schéma, quota et idempotence testés ; API respecte les mêmes droits que l'UI. |
| Migration Wizard | Paquet ZIP/manifest vérifiés en base isolée ; dépendances et comptages réconciliés. |
| Transfer Audit | Toutes les transitions et téléchargements ont auteur/tenant/résultat ; aucun secret journalisé. |
| Error Reports | Fichier rejeté donne lignes, champs, motifs, totaux ; rapport hors tenant refusé. |
| Data Reconciliation | Nombres, identifiants stables, relations et montants comparés avant/après ; écart non nul bloque la clôture. |
- [ ] **9. Registre des permissions.** Déclarer
  `data.import.{create,preview,validate,execute,cancel,rollback}`,
  `data.export.{create,preview,execute,download,schedule,revoke}`,
  `data.template.{read,create,update,delete,publish}`,
  `data.mapping.{create,update,delete}`, `data.audit.read`,
  `data.report.download`, `data.migration.execute`, ainsi que les
  permissions métier `sis.student`, `lms.course`, `finance.invoice`,
  `hr.employee` et `credentials.diploma` en import/export.
  **Valider chaque clé :** accès accordé au seul acteur/objet/tenant
  autorisé, refus pour autre rôle/tenant ou permission absente ; avoir
  `sis.student.export` ne donne pas les colonnes sensibles ni tous les
  étudiants.

| Point 10 — espace de configuration | Validation attendue |
|---|---|
| Identity Management | Comptes, SSO et MFA configurés par tenant ; suspension propagée. |
| Access Management | RBAC/ABAC/ReBAC/GBAC/MBAC/ACL simulés, appliqués et révocables. |
| Policy Management | Règles et exceptions versionnées ; refus par défaut et historique contrôlés. |
| Organization Security | Campus et tenants séparés dans API, fichiers, LMS et tâches. |
| Data Classification | Habilitation requise pour chaque classe de données sensible. |
| Session & Device Security | Sessions/appareils listables et révocables sans fuite de métadonnées. |
| Risk & Threat Management | Seuil de risque testé pour autorisation, step-up et blocage. |
| Approval Management | SoD et urgence avec deux identités, durée et audit. |
| Audit & Compliance | Journaux intègres, filtrés et conservés selon règle prouvée. |
| Data Transfer Center | Import/export, staging, jobs, rapports et révocation de liens testés. |
| Template Management | CSV/XLSX/JSON et versions cohérents avec le registre. |
| Data Governance | Rétention, anonymisation et purge validées sans supprimer les sauvegardes dues. |
| Infrastructure Security | Secrets, clés, restauration et alertes vérifiés dans l'installation cible. |

## E. Nouveau cahier SIS/LMS/ERP : écarts à clôturer

Source additionnelle : SHA-256
`126b2e3165c641abd6aa743bfbbab6926ee6484171ce4599f329b432e8811f4d`
(1 044 lignes). Les identifiants de cette section sont préfixés **N** pour
éviter de les confondre avec ceux de la matrice des 94 exigences et du
cahier IAM ci-dessus. Chaque ligne décrit ce qui **reste à prouver ou à
terminer**, pas ce qui est livré. La matrice initiale recouvre une grande
partie de ces sujets : les lots indiqués réutilisent les tâches ouvertes
plutôt que recréer un second projet parallèle. Les capacités optionnelles
(RFID, visio, classements, etc.) doivent être activées et vérifiées si
annoncées ; sinon leur exclusion par pack doit être explicite.

### N1 — SIS : vie administrative et académique

| Point / tâches ouvertes | Condition de validation restante |
|---|---|
| N1.1 Admissions (F11, F04, F17) | Candidat crée son compte sur portail public, remplit formulaire configuré, choisit formation et soumet pièces/frais dans les dates ; évaluateur distinct vérifie, convoque si besoin, met en attente/demande complément/accepte/refuse ; notifications et conversion en **un** dossier observables, refus hors délai/capacité. |
| N1.2 Dossier individuel (F05, F12, F22) | Matricule unique, identité, contacts/tuteurs/urgence, photo, documents et historiques académiques/disciplinaires/financiers présents selon droit ; fusion contrôlée et transfert entre établissements conservent références et audit sans fuite. |
| N1.3 Inscriptions (F11, F12, F15) | Inscription initiale, annuelle et par période/UE/option affecte classe/groupe uniquement avec pièces, prérequis, place et validations administrative/financière ; suspension, abandon, reprise et tentative de doublon appliquent les états exacts. |
| N1.4 Programmes (F04, F12) | Faculté/école/département/filière/niveau/classe/groupe, matières/UE/crédits/coefficients/prérequis et équivalences reliés ; ajout invalide ou transfert entre tenants refusé, parcours restant recalculé sans changer l'historique clos. |
| N1.5 Emplois du temps (F14, F17) | Disponibilité salle/enseignant/classe, remplacement et export PDF/XLSX/calendrier personnel sur données réelles ; conflit refusé, modification notifiée au bon groupe, aucune double réservation. |
| N1.6 Présences (F14, F17, F20) | Appel manuel, QR/badge RFID/mobile **si activés**, retard, justification, sortie et taux par classe/période rattachés à une vraie séance ; preuve anti-usurpation, correction auditée, alertes aux seuls parents liés et aucun pointage sur séance close. |
| N1.7 Examens officiels (F09, F13, F14) | Session/surveillants/salles/candidats et copies reliés ; barèmes, rattrapage, délibération, classement, PV et recours calculés puis validés par autorité ; note importée reste brouillon, résultat clos non modifiable sans rectification traçable. |
| N1.8 Progression (F12, F13, F25) | Passage/redoublement/rattrapage/réorientation/crédits restant calculés sur résultats officiels et règles versionnées ; seule autorité compétente tranche, suspension et transfert ne réécrivent pas les acquis. |
| N1.9 Parents (F02, F10, F17) | Parent lié voit notes, absences, devoirs, planning, factures/paiements, messages, rendez-vous et bulletin **de ses seuls enfants** ; liaison retirée coupe API, fichier et portail, même après rechargement. |
| N1.10 Stages/projets (F18, F25) | Offre → affectation → convention → tuteur → rapport/mémoire → évaluation/soutenance/archivage ; partenaire limité à sa mission et à ses dates ; projet de fin d'études relié à son cursus. |
| N1.11 Diplômes (F22, F13) | Conditions remplies → titre/attestation/certificat unique, signature autorisée, QR minimal, archive/portefeuille ; réédition et révocation auditées, titre falsifié ou incomplet refusé, alumni sans diffusion automatique. |
| N1.12 Dashboard SIS (F23, F30) | Effectifs, admissions, inscriptions, classes/filières, réussite/échec/absentéisme, difficulté, irrégularités, diplômes et tendances rapprochés aux données persistées/périodes ; filtrage par rôle/tenant, états vides et sources vérifiés. |

### N2 — LMS : apprentissages (Open edX réutilisé si possible)

| Point / tâches ouvertes | Condition de validation restante |
|---|---|
| N2.1 Cours (F06–F08) | Enseignant habilité crée/duplique/édite/publie/dépublie cours lié à formation/classe/groupe, objectifs/prérequis/dates ; seuls inscrits pendant la fenêtre lisent le cours ; suppression contrôlée préserve remises et historique. |
| N2.2 Éditeur de contenus (F08) | Texte, image, vidéo, PDF, présentation, audio, lien, interaction, code et formules combinés dans le vrai Studio ; aperçu, version antérieure et publication programmée vérifiés ; contenu non publié invisible à l'étudiant. |
| N2.3 Bibliothèque de ressources (F05, F08) | Déposer/classer/rechercher/partager/réutiliser/versionner un même document dans deux cours sans doublon de téléversement ; accès, téléchargement, import/export et ancienne version respectent l'auteur/tenant. |
| N2.4 Parcours (F08, F25) | Parcours obligatoire/optionnel avec prérequis, ordre et déblocage après leçon/évaluation réellement validée ; échec ou retrait bloque la suite, progression et compétences cohérentes. |
| N2.5 Visio (F08, F14, F17) | Professeur planifie, invite et tient une séance réelle avec participants, partage/chat/tableau/enregistrement **selon fournisseur activé** ; présence reliée au cours, accès et rétention des enregistrements refusés hors périmètre. |
| N2.6 Devoirs/TP (F08, F09) | Consigne/fichier/date → remise texte/fichier, individuelle ou groupe → retard, commentaire, barème, correction et nouvelle version ; seules remises autorisées sont visibles, l'historique n'est pas écrasé. |
| N2.7 Quiz/examens (F08, F09) | Banque et types QCM/ouvert/numérique/association/classement, durée, tirage et tentatives vérifiés sur le vrai LMS ; auto-correction limitée aux réponses compatibles, validation humaine pour le reste, publication différée. |
| N2.8 Notes pédagogiques (F09, F13) | Carnet avec pondérations/rubriques/commentaires, export borné ; échange vers SIS idempotent, notes brouillon jusqu'à validation officielle, résultat clos jamais écrasé. |
| N2.9 Progression LMS (F10, F23, F25) | Événements réels de leçon, cours, devoir, quiz, temps et compétence alimentent tableaux de bord staff/apprenant ; rejeu ne double pas compteurs, périmètres et fraîcheur affichés. |
| N2.10 Collaboration (F08, F17) | Forum, annonce, message, groupe, commentaire et document d'un cours réel accessibles seulement aux inscrits/enseignants autorisés ; exclusion/révocation coupe lecture et notification. |
| N2.11 Gamification (`lms-gamification`) | Points/niveaux/badges/défis/séries et classement **opt-in** dérivés d'activités validées ; événement rejoué ne crée pas de récompense supplémentaire ; désactivation et retrait de droit protégeant les données personnelles. |
| N2.12 IA pédagogique (F26) | Tuteur, brouillons cours/quiz/exercices, résumé, traduction, révision/correction et détection de difficultés seulement sur contenus autorisés ; coûts/sources connus, enseignants valident avant publication et IA ne publie pas de note officielle. |
| N2.13 Standards (F24) | Pour chaque SCORM/xAPI/LTI 1.3/QTI/OneRoster/Open Badges/Caliper **annoncé** : échange avec outil réel, authentification/version/références, rejet/rejeu et révocation ; standard non qualifié affiché comme non disponible. |
| N2.14 Dashboards LMS (F10, F23) | Étudiant voit ses cours/devoirs/examens/planning/progression/résultats/ressources ; enseignant ses classes/corrections ; direction seulement agrégats autorisés, chacun avec données réelles et refus des URL/API hors droit. |

### N3 — ERP : ressources et opérations (charte graphique inchangée)

| Point / tâches ouvertes | Condition de validation restante |
|---|---|
| N3.1 Finance (F15, F16) | Comptes/journaux/centres de coûts, créances/dettes, budgets/prévisions, banque et clôture rapprochés ; écriture déséquilibrée, dépassement non approuvé et mutation de période close refusés. |
| N3.2 Facturation (F15) | Tarifs par frais, facture individuelle/collective/récurrente, bourse/remise/exonération/avoir/échéance/reçu/relance calculés sur inscription réelle ; solde, aide et impayé cohérents après annulation. |
| N3.3 Paiements (F16) | Espèces, banque, mobile money, carte, tiers, tranches et remboursement selon prestataire/pack autorisé ; confirmation serveur rapprochée à facture et référence unique, callback rejoué ou retour navigateur seul ne paye rien. |
| N3.4 RH (F19) | Employé/enseignant possède contrat, poste, affectations, absences/congés, formation, évaluation, documents et départ historisés ; droits RH bornés, accès enseignant/LMS retiré au départ. |
| N3.5 Paie (F16, F19) | Base, primes, heures, retenues, avances et cotisations du pays pilote configurées ; bulletin calculé, contrôlé par autre acteur et rapproché comptablement, période close et auto-validation refusées ; règles nationales non qualifiées restent bloquées. |
| N3.6 Achats (F15, F20) | Demande → appel d'offres/devis → deux approbations si requis → commande → réception partielle/contrôle → facture fournisseur → paiement ; quantités/budget/stock réconciliés, doublon refusé. |
| N3.7 Fournisseurs (F20) | Fiche avec contrat/documents/contacts, commandes, paiements et litiges ; fournisseur étranger/archivé inutilisable, historique d'évaluation conservé. |
| N3.8 Stocks (F20) | Article/entrepôt/lot/série et mouvements entrée/sortie/transfert/inventaire ; stock initial + mouvements = final, valorisation correcte, seuil bas notifié, sortie excessive interdite. |
| N3.9 Immobilisations (`erp-fixed-assets`) | Numéro d'actif, propriétaire, lieu/état, affectations/maintenance, amortissement et réforme reliés au stock/achat/journal ; double immobilisation et dotation de période close refusées. |
| N3.10 Maintenance (F20) | Panne → ticket → technicien/planification → pièces/coût → intervention et clôture avec historique ; matériel indisponible non réservable, pièces consommées une seule fois. |
| N3.11 Bâtiments/salles (F14, F20) | Bâtiment/étage/salle/labo/amphi, capacité et équipement avec réservation synchronisée à l'emploi du temps ; chevauchement ou dépassement de capacité refusé. |
| N3.12 Transport (F15, F20) | Véhicule/chauffeur/ligne/arrêts/abonnement/horaire, carburant/incidents/entretien et frais liés à l'élève autorisé ; capacité et double affectation contrôlées. |
| N3.13 Hébergement/restauration (F15, F20) | Chambre/lit, réservation/affectation, tarif/facture et menus/repas/abonnements/consommation rapprochés ; lit occupé deux fois ou service non payé selon règle refusé. |
| N3.14 Bibliothèque (F20) | Catalogue/auteurs/éditeurs/exemplaires, prêt/retour/réservation, retard/pénalité, recherche et numérique ; exemplaire déjà emprunté non prêté, ressource sous licence privée inaccessible. |
| N3.15 Documents/courriers (`erp-document-circuits`) | Courrier reçu → classement → approbation/signature → sortie/archivage ; versions, conservation et destruction autorisée contrôlées, recherche et téléchargement sans fuite. |
| N3.16 Événements/réunions (F14, F17, F20) | Réunion/conférence/cérémonie réservée sans conflit salle, invitations et réponses aux seuls participants, budget/compte rendu conservés avec approbation ; annulation notifiée. |
| N3.17 Dashboard ERP (F23) | Trésorerie, dépenses, factures/recouvrement, paie, budgets, achats, stocks, équipements/maintenance, occupation et fournisseurs rapprochés par période/centre/tenant, sans afficher détails sensibles au mauvais rôle. |

### N4 — Circuits intégrés, services et paramètres

Propriétaires des données : **SIS** pour identités académiques/inscriptions
et résultats officiels ; **LMS** pour cours/activités et notes provisoires ;
**ERP** pour factures, encaissements, RH et ressources. Contrats versionnés,
événements avec identifiants stables, outbox/rejeu idempotent, audit et
contrôle de tenant à chaque frontière ; jamais d'écriture directe dans
les tables d'un autre domaine.

- [ ] **N4.1 Admission → paiement → cours** (F07, F11, F15, F16, F17).
  **Valider les neuf étapes du cahier :** candidature acceptée → dossier
  unique SIS → facture ERP → paiement effectué → confirmation ERP par
  source fiable → inscription validée → affectation aux seuls cours LMS →
  espace apprenant actif → notification au bon compte. Simuler panne et double événement
  à chaque frontière ; aucun cours avant condition, aucune facture payée
  fictivement, réconciliation des trois systèmes après reprise.
- [ ] **N4.2 Examen → résultat officiel** (F08, F09, F13, F16).
  **Valider les sept étapes :** candidats SIS → examen LMS → correction
  enseignant → transfert des propositions → validation SIS → progression
  mise à jour → facture de rattrapage *si* règle active ; rejets sur
  non-inscrit, note en double et résultat clos.
- [ ] **N4.3 Recrutement → accès enseignant** (F02, F07, F14, F19).
  **Valider les sept étapes :** dossier de recrutement ERP → contrat
  approuvé par RH → identité existante réutilisée ou créée → affectation
  SIS au département → cours LMS autorisés → planning → accès remis ;
  contrat rejeté ou terminé
  retire immédiatement cours et portail, sans révoquer un autre mandat
  actif du même utilisateur.

| N5 — responsabilité partagée | Condition de validation restante |
|---|---|
| IAM | Identité, rôles, permissions, SSO et MFA uniques ; changement/révocation observés sur SIS, LMS et ERP. |
| Notifications | E-mail/SMS/push/interne par consentement et tenant ; panne/rejeu sans doublon ni mauvais destinataire. |
| Workflow | Étape/acteur/délai et double approbation versionnés ; étape sautée ou auto-validation refusée. |
| Documents | Version, partage, signature, archive et rétention identiques dans les trois domaines ; fichier hors droit refusé. |
| Search | Index de ressources autorisées et filtres ; révocation retire même titre/extrait, pas seulement la fiche. |
| Import/Export | CSV/XLSX/JSON, modèles, staging, jobs et migrations appliquent les règles de la section D et les domaines propriétaires. |
| Audit | Même identifiant de corrélation pour action/événement/rejeu et résultat, avec tenant et sans secret. |
| Analytics | Indicateurs réconciliés aux écritures métier, date/fraîcheur et périmètre affichés. |
| AI | Sources/tenant vérifiés, désactivation sans fournisseur et aucune écriture officielle sans humain. |
| Integration | API/webhook/connecteur versionné, signature et idempotence ; erreur amont visible et reprise testée. |
| Calendar | Disponibilités et événements liés au même planning ; conflit inter-domaines refusé. |
| File Management | Import/téléchargement privés, type/antivirus/quotas et révocation de liens testés dans les trois systèmes. |

- [ ] **N6 Configuration SIS** (F04, F12, F13, F14). Règles d'admission,
  inscription, notation, progression, calendrier, classes, diplôme,
  présence, pièces et bulletins configurables et versionnées.
  **Valider :** changer chaque règle dans un campus seulement ; nouveau
  dossier l'applique, ancien dossier clos conserve sa version et autre
  établissement ne change pas.
- [ ] **N6 Configuration LMS** (F04, F08, F09). Paramètres cours,
  activités, barèmes, publication, examens, groupes, suivi, IA, formats
  et notifications configurables. **Valider :** échec de prérequis et
  changement de publication modifient seulement cours/dates visés ;
  activité terminée conserve ses règles et ses résultats.
- [ ] **N6 Configuration ERP** (F04, F15, F16, F19, F20). Comptabilité,
  taxes/devises, moyens de paiement, facturation, exercice, stocks, RH,
  approbations, fournisseurs et modèles de facture configurables.
  **Valider :** calculs distincts pour deux exercices/tenants, facture
  historique inchangée et paramètre absent bloquant la transaction plutôt
  que valeur financière inventée.
- [ ] **N6 Héritage** (F02, F04). Paramètre global → établissement →
  campus, avec override explicite et droits d'édition séparés.
  **Valider :** deux campus héritent de la version globale, un override
  ne touche pas son voisin ; retrait d'override rétablit l'héritage sans
  réécrire les décisions passées.

**N7 Ordre de réalisation :** reprendre les dépendances des tâches SQL
existantes ; identités/tenants et deux portails permissionnés avant
ouverture du pilote, parcours SIS réels avant leur facturation/inscription
LMS, puis autres domaines et fonctions facultatives. La liste des neuf
phases du cahier est une priorité, pas une preuve de livraison.

## Condition d'arrêt globale

Ne déclarer « 100 % » qu'après validation **individuelle** des 94 exigences,
des 39 tâches ouvertes (dont cinq nouvelles) et de tous les points
supplémentaires applicables ci-dessus : parcours des deux SIS, du vrai LMS
et de l'ERP, rôles/tenants, formulaires,
boutons, import/export, refus et sécurité, 500 connexions concurrentes selon
le protocole scellé, installation et restauration locales persistantes,
puis pilote externe autorisé. Toute case sans preuve reste ouverte ;
les prérequis institutionnels manquants restent explicitement bloqués.
