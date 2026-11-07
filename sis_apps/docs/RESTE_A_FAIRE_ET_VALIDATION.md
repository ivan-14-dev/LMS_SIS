# Reste à faire et critères de validation — LMS/SIS

État relevé le 5 novembre 2026. Ce document réunit les 34 tâches initialement
ouvertes de la TODO, **cinq tâches ajoutées** après rapprochement du nouveau
cahier SIS/LMS/ERP, et les exigences du cahier complémentaire « identités,
autorisations, sécurité et import/export » (source fournie : SHA-256
`e5e3b1e3ccfee313370bfe53e322aff2a2fe18fde4498e80ed6772e78d49f868`).
La [matrice de recette](functional-acceptance-matrix.json) reste la référence
des 94 exigences initiales ; ce cahier complémentaire **ajoute** des critères,
sans transformer les preuves antérieures en validation globale.

**Dernier cutoff documentaire : 7 novembre 2026 à 20:05:28 UTC** :
vagues 15 à 29 publiées et qualifiées dans leurs périmètres bornés ;
**vague29 publiée en `0bb4766`, vérifié égal à `HEAD` et `origin/main` sur main**.
Le passage autorisé de **10.5 d'absente à partielle** appartient à la
vague25. **Aucun statut promu en vague29** :
**1 vérifiée, 72 partielles, 19 absentes et 2 non vérifiées sur 94**.
Les 93 autres statuts et les chiffres historiques restent inchangés.
Le blocage de qualification Studio a été levé
vers 07:30 UTC : le correctif est publié, avec une preuve ciblée limitée
décrite en vague 19, **sans clôture de F07**. Après les lots et parcours
groupes 20/21, les vagues 22/23 ajoutent l'audit du cycle de vie **via API**
et son lecteur d'historique. La vague 24 ajoute la désactivation réversible
des groupes sans retirer membres ou permissions, avec suites backend
intégrales sur l'image reconstruite du commit publié, 31 tests UI et deux parcours
navigateur par SIS, dont révocation/rétablissement dans une même session.
IAM reste en cours, sans recette exhaustive multi-tenant, tous menus/rôles,
MFA/SoD ou versionnement. Les acquis projets25/cours26/enseignants non staff27
sont conservés. La vague28 ajoute des **objectifs compétences facultatifs** issus
exclusivement des offres déjà rattachées à la classe ou à la formation,
avec instantanés privés et accès acteur/responsable opposables.
**Objectifs sélectionnés ≠ acquisition**, sans notes officielles ou LMS distant induits.
La vague29 ne change que **tests/harness**, pas produit, migrations ou UI produit :
image **`ee2a9bc…`**,17 tests projets par SIS, cycle navigateur **individuel complet**
désormais qualifié avec gestionnaire et évaluateur non staff distincts,
deux révisions PDF privées et publication humaine. Cours26/collectif25 réellement
rejoués29 : **trois cas par SIS**, six reçus HTTP après recréation.
Les premiers rouges backend, fixture, navigateur et Jest sont conservés.
Jest34/34 au timeout30 s après14 timeouts à5 s ; bundle28 inchangé réutilisé,
**aucun nouveau build frontend ni intégrale29**.
**10.5 reste partielle**, mais le parcours individuel n'est **plus manquant**.
Les preuves fonctionnelles individuelles/collectives et les refus interéquipes
en lecture **et** écriture sont désormais disponibles. Restent les conditions
de la **règle commune préexistante**, pas de nouveaux critères métier :
deux établissements réellement peuplés, restauration isolée et comparaison
comptes/MFA/droits/données protégées. Un objet établissement sans création de
schéma et un tenant navigateur par SIS ne prouvent pas deux établissements ;
une recréation avec volume conservé ne prouve pas une restauration de sauvegarde.
La source918 n'exige ni acquisition, ni notes officielles, ni provisioning LMS :
ces travaux ouverts du programme ne deviennent **pas de nouvelles obligations
de10.5**. Objectifs ≠ acquis reste une limite de portée du produit.
La relecture29 de la règle commune précise son application à10.5 sans modifier
les bilans27/28 : aucune réception prestataire/production n'est ajoutée à ses critères.
Les concurrences exactes offre/sélection et affectation/rattachement ne sont
pas qualifiées ; pas de jeton client de révision d'offre.
**Le 100 % n'est pas atteint.**
Les bilans datés antérieurs conservent leurs cutoffs, blocages et rouges.

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

**Complément Studio du 7 novembre 2026 à 07:00:50 UTC : qualification
bloquée, pas de livraison.** Deux approches sur un réseau interne et une
base MySQL jetables ont échoué avant l'exécution des tests : les migrations
CMS complètes exigent MongoDB, absent de cette fixture ; la synchronisation
des modèles sans migrations dépasse la limite MySQL de longueur d'index
pour `oel_tagging_tag.lineage`. **12 tests détectés, aucun exécuté** :
ni le refus de reprise après révocation des droits Studio, ni les verrous
consultatifs ne sont qualifiés. Les deux fichiers existants restent
inchangés et non publiés. Conteneurs, volume, réseau et dossier temporaires
ont été supprimés ; aucun service partagé n'a été modifié.
Le rapport de session `wave18-cms-qualification-d0c25c75/report.json`
(SHA-256 `2a0171010d4725fdb52a983de1edd9ea7b8fce039c016be0103350945c19b752`)
conserve commandes, erreurs et limites. F07 n'est pas clôturé.

**Dix-neuvième vague, qualification débloquée vers 07:30 UTC et consignée
au cutoff du 7 novembre 2026 à 08:12:15 UTC :** les commits `56c3b33`
(garde de reprise Studio) et `63949d1` (copie de groupe) sont publiés dans
`origin/main`. Le blocage daté de 07:00:50 ci-dessus reste historique,
pas l'état courant des deux fichiers Studio.

La qualification CMS utilise l'image native de base
`lms-sis-openedx:local-20261105-access-ownership2`, **MySQL 8.4.11 et
MongoDB 7.0.39 jetables**, sur réseau interne sans ports publiés ni services
partagés selon le parent. L'ajout d'un vrai MongoDB permet les migrations
CMS complètes : **1 188 migrations appliquées**. Le premier passage exécute
12 tests avec **2 erreurs de fixture d'assets** ; le second conserve
**2 erreurs d'URL MFE**. Les fixtures sont corrigées vers les vrais assets
de l'image (`/openedx/staticfiles/studio/webpack-stats.json`) et une
`COURSE_AUTHORING_MICROFRONTEND_URL` localhost, sans changer le produit
pour contourner ces erreurs ni simuler une réponse 500.
`wave19-courses-recheck2.log` passe ensuite **12/12**.

Sur les mêmes services, le code publié avant la garde échoue exactement
sur **`200 != 403`** dans `wave19-courses-baseline.log` ; le cas candidat
seul repasse dans `wave19-courses-regression-final.log`. `56c3b33` publie
deux lignes de garde, 17 lignes de test et la documentation opérateur
`DEPLOIEMENT_INTEGRATIONS.md` ; flake8, isort et Black ciblés sont verts
selon le parent. `wave19-sql-state.log` conserve les comptes **1 188
migrations, 0 binding et 0 utilisateur de service de test retenus**.
`wave19-course-lock-statements.log` contient **51 `GET_LOCK` et 51
`RELEASE_LOCK` de cours effectivement appelés en SQL** : cumul de plusieurs
passages, **pas preuve de concurrence**, ni 51 cours ou scénarios uniques.

Ces tests CMS utilisent `force_authenticate` et simulent le modulestore,
`create_new_course`, `resume_initialization` et les droits d'auteur Studio.
MongoDB est réel pour la fixture/migration, **mais aucune création réelle
de cours MongoDB ni révocation Studio native de bout en bout n'est prouvée**.
Il n'y a **ni nouvelle image LMS ni déploiement**. Les deux conteneurs
natifs ont été arrêtés par le parent ; vérification du réseau vide et
nettoyage restent en suivi, sans affirmer leur achèvement. Les journaux
et le rapport initial sont conservés dans
`files/wave18-cms-qualification-d0c25c75`. **F07 reste ouvert**.

`63949d1` ajoute à la console existante une copie des permissions d'un
groupe lisible en **brouillon éditable**, enregistrée via le POST existant,
sans copier les membres ni modifier la source. L'habilitation
`auth.add_group` non scopée est requise ; une liste de permissions absente
du serveur interdit la copie. `wave19-group-duplication.log` passe
**16 tests InstitutionalGroupsEditor, dont 4 nouveaux** ; il s'agit de
tests UI avec services simulés, pas d'un parcours navigateur de clonage.
ESLint ne relève aucun diagnostic sur les deux fichiers selon le parent.
`wave19-frontend-build.log` compile avec **3 avertissements de taille/performance**.
Aucune nouvelle capacité backend ni cycle de rôle métier n'est déduit.

Les dix artefacts référencés, dont le rapport historique, sont hachés dans
la matrice ; les contrôles qualité sans journal dédié restent attribués
au parent. Aucun test ou service n'est relancé pour cet import. Aucun
déploiement partagé, pilote ou réception externe/humaine ; les **94 statuts
restent inchangés**, F09 et 10.7 partiels. Le dernier essai à 500 reste
rouge (**500 timeouts, 262 écritures indéterminées**). **Vague 20 groupes
en cours, non qualifiée : aucune preuve importée ici.**

**Vingtième vague, publiée et qualifiée au cutoff du 7 novembre 2026
à 08:52:32 UTC :** `2ade295`, présent dans `origin/main`, ajoute dans
les deux SIS les POST `utilisateurs/groupes/{id}/assign_many/` et
`unassign_many/`. `user_ids` accepte **1 à 100 entiers strictement positifs,
uniques**, sans coercition des types ; la réponse trie les identifiants.
La transaction verrouille le groupe et les comptes dans l'ordre des clés,
prévalide **toutes les cibles avant la mutation M2M**, puis conserve un
`WorkflowEvent` nominatif avec acteur, tenant, `group_id`, `user_ids` et
différentiel des membres réellement ajoutés ou retirés. Une cible refusée
ou un échec d'audit annule toute l'opération. Le rejeu ne duplique pas les
membres, **mais crée un nouvel événement d'audit au différentiel vide** ;
les autres groupes restent intacts.

Les permissions `auth.change_group`, `utilisateurs.change_utilisateur` et
`utilisateurs.view_utilisateur` doivent être non scopées : **la présence
d'une clé de scope, même `{}`, est refusée**, hors exception superutilisateur
préexistante. Tenant actif, groupe du bon périmètre et droits non délégables
restent protégés. Le helper commun `sis_common/group_assignment.py`
mutualise transaction, différentiel et audit ; la publication comprend sept
fichiers backend, deux fichiers frontend et le README frontend.

L'interface conserve l'affectation individuelle et ajoute une sélection
multiple Autocomplete avec contrat 1–100 visible. Un refus est affiché et
conserve la sélection ; succès ou changement de groupe la réinitialisent.
Les commandes de navigation/changement de groupe sont bloquées pendant
la mutation ; la garde UI est alignée sur le refus d'une clé de scope vide.
`wave20-school-group-api.log` passe **62 tests et 108 sous-tests**,
`wave20-university-group-api.log` **63 tests et 108 sous-tests** :
sélections utilisateurs, autorisations et séparation des rôles métier,
exécutées en série sur PostgreSQL selon le parent, **pas les suites backend
complètes**. `wave20-group-batch-ui-final2.log` passe les **21 tests du seul
composant InstitutionalGroupsEditor**. `wave20-frontend-build-final2.log`
compile avec **3 avertissements de taille/performance**. Le parent atteste
ESLint ciblé sans erreur, flake8/isort verts sur les sept fichiers backend
et Black vert sur le helper commun ; aucun journal dédié n'a été fourni
pour ces contrôles, ni nombre d'avertissements ESLint.

Les quatre journaux sont hachés dans la matrice. **Pas encore de parcours
navigateur batch, d'image backend reconstruite ni de suite backend complète**
pour ce lot. Les conteneurs PostgreSQL/Redis de vague 20 sont isolés sur
réseau interne sans ports publiés et **conservés pour le parent**, en vue du
raccordement navigateur 21 ; aucun arrêt, nettoyage ou sondage n'est effectué
par cet import documentaire. Aucune preuve de vague 21 n'est revendiquée.
Pas de déploiement partagé, pilote ou réception humaine ; **IAM reste en
cours**, désactivation/versionnement des groupes et MFA/SoD ouverts.
Les **94 statuts restent inchangés**, F07 ouvert, F09/10.7 partiels.
Les cutoffs et rapports rouges antérieurs restent intacts ; dernier essai
à 500 toujours rouge (**500 timeouts, 262 écritures indéterminées**).

**Vingt et unième vague, publiée et qualifiée au cutoff du 7 novembre 2026
à 09:03:09 UTC :** `c8e2348`, présent dans `origin/main`, ajoute seulement
`group-membership.e2e.js` et `group-membership.config.js` (**121 lignes
ajoutées : 111 de scénario et 10 de configuration**). Aucun code produit
n'a changé depuis la vague 20, aucune image backend n'a été reconstruite.
Le parent atteste ESLint e2e sans diagnostic, sans journal dédié fourni.

Les reçus `wave21-browser-groups-secondaire/.last-run.json` et
`wave21-browser-groups-superieur/.last-run.json` sont verts : **un parcours
réel par variante**, chacun comprenant un staff et un apprenant, et non
deux parcours distincts par rôle. Le staff se connecte dans l'UI réelle,
crée un groupe à partir de `view_utilisateur` dans le catalogue et affecte
les deux comptes synthétiques **4 et 5**. Les relectures API confirment les
membres et préservent leur groupe préexistant **1**. La duplication conserve
les permissions, sans copier les membres ni modifier la source. Un lot
mixte contenant une cible valide et l'identifiant inexistant **2147483647**
reçoit **404 sans écriture partielle**. Le retrait du lot entier restitue
les groupes initiaux sans toucher aux autres groupes. Enfin, dans un nouveau
contexte navigateur, l'apprenant s'authentifie réellement et son POST
`assign_many` est **refusé en 403 sans modification**.

**Aucune réponse réseau n'est simulée**, seulement le pacing avant
transmission réelle. Les reçus attestent `passed` ; le périmètre et le
nombre de parcours sont rapprochés du scénario publié et des résultats
du parent. Les bases neuves `sis_wave21_browser_*` utilisent PostgreSQL/Redis
privés de vague 20. Une première passerelle entièrement interne n'exposait
pas de port ; le raccordement final ajoute un réseau edge **à la seule
passerelle**, exposée sur **`127.0.0.1:32490`**. API et bases restent internes :
ne pas décrire cette configuration finale comme totalement sans port publié.
Les API et passerelles ont été arrêtées après les deux cas selon le parent ;
aucun arrêt de PostgreSQL/Redis n'est déduit et aucun service n'est sondé ici.

Les deux reçus sont hachés dans la matrice. Ces parcours lèvent l'attente
navigateur batch/duplication de vague 20 dans **ce seul périmètre** ; ils
ne qualifient pas plusieurs tenants, les parents/enseignants, MFA/SoD,
versionnement ou désactivation des groupes. **IAM reste en cours** :
aucun rôle métier universel, déploiement partagé, pilote ou réception
humaine n'est déduit. **94 statuts inchangés**, F07 ouvert, F09/10.7
partiels ; tous cutoffs et rouges antérieurs conservés, dernier essai
à 500 rouge (**500 timeouts, 262 écritures indéterminées**).

**Vagues 22 et 23, publiées et qualifiées au cutoff du 7 novembre 2026
à 14:40:10 UTC :** `5a90d45` publie l'audit du cycle de vie des groupes et
`e495418` son lecteur d'historique ; les deux commits sont dans `origin/main`.
`GroupAuditMixin` et le helper d'affectation individuelle assurent transaction
et événement nominatif pour création, modification, suppression, affectation
et retrait **par les API groupes des deux SIS**, pas pour les opérations
Django admin hors API. L'identité du groupe est conservée après suppression ;
les snapshots avant/après contiennent `name` et les permissions `{id, code}`
triées par identifiant. Une affectation sans changement ne remute pas les
membres mais crée un nouvel audit au différentiel vide. Les refus ne créent
pas d'événement ; six sous-opérations avec panne injectée après écriture
d'audit vérifient le rollback du groupe, des relations M2M et de l'événement.

Le journal global accepte `object_id` jusqu'à **64 caractères**, combiné
aux filtres acteur/date dans liste, exports et summary ; ses filtres d'objet
et de tenant restent opposables. `actor_nom` retombe sur le username si le
nom complet est vide. Le lecteur UI exige `auth.view_group` et
`core.view_workflowevent` non restreints ; il expose pagination, avant/après
et différentiels d'identifiants. Le cache React Query utilise `gcTime: 0` ;
révocation des capacités : démontage/purge, réponse 403 : données masquées
avant réessai, mutation réussie : rafraîchissement. Le filtre reste celui
du **journal global**, pas une nouvelle politique universelle IAM.
L'historique d'un groupe supprimé persiste côté API ; **la console ne propose
ni suppression ni désactivation**.

L'image reconstruite **`lms-sis:local-20261107-e495418`**, initialement
qualifiée sous `qualification-wave22-d0c25c75`, a le digest
`sha256:9b9d8311fd7341c50bd066414809f4ec354d55932eb8c4b237ed714ef856efb5`.
Elle comprend la vague 22 **et le backend de vague 23**, sans overlay de
code backend pendant les tests selon le parent. `wave22-backend-build.log`
en conserve le digest ; les deux journaux `wave22-*-check.log` sont verts.
`wave22-secondaire-iam.log` passe **65 tests et 132 sous-tests**,
`wave22-superieur-iam.log` **66 tests et 132 sous-tests** : utilisateurs,
autorisations, séparation des rôles et deux tests de filtres workflow,
**pas les suites backend complètes**. Black/isort/flake8 ciblés sont verts
selon le parent, après passage Black sur trois fichiers de tests.

`wave23-group-history-ui.log` passe **26 tests du composant**. Le parent
rapporte 14 erreurs ESLint initiales de formatage, corrigées par autofix des
tests seulement, puis **0 erreur et 0 avertissement ciblés** ; aucun journal
dédié de lint n'est fourni. `wave23-frontend-build.log` compile avec
**3 avertissements de taille/performance** ; sa durée Webpack anormale,
affectée par l'horloge, n'est pas interprétée. Le build séparé
`wave23-frontend-browser-build.log` utilise explicitement les URL de fixture
et l'authentification locale, sans mocks, et passe avec 3 avertissements.

`wave23-browser-groups-secondaire` et `wave23-browser-groups-superieur`
passent chacun **un parcours réel staff + apprenant**. Ils reprennent la
vague 21 puis vérifient dans l'UI l'historique du groupe source : exactement
**3 événements** (`group_created`, `assign_many`, `unassign_many`), avant
absent/après permission réelle ; relecture API du count, des identifiants,
noms d'acteurs et différentiels, puis refus **403** de l'historique pour
l'apprenant. Les reçus `.last-run.json` sont verts ; durées de 42,9 s et
44,1 s rapportées par le parent, pas un benchmark. Les bases synthétiques
**`sis_wave21_browser_*` sont réutilisées**, pas recréées pour 23 ; chaque
test crée de nouveaux groupes. Les serveurs utilisent l'image `9b9d…`
sans overlay applicatif, avec seuls settings de test wave15 montés selon
le parent. PostgreSQL/Redis20 restent internes et privés, la passerelle
edge est exposée sur `127.0.0.1:32490` ; API/passerelles arrêtées après les
deux cas, PostgreSQL/Redis conservés pour le parent et le lot 24.

Les dix artefacts sont hachés dans la matrice, répartis en **deux campagnes
documentaires : backend commun 22/23, puis UI/builds/navigateurs 23**.
Aucune exécution applicative pour cet import, aucun déploiement partagé,
nouveau 500, pilote ou réception institutionnelle. **94 statuts inchangés**,
IAM en cours, F07 ouvert, F09/10.7 partiels. Pas de preuve de vague 24 ;
cutoffs et rouges antérieurs intacts, dont le dernier 500 (**500 timeouts,
262 écritures indéterminées**).

**Vague 24, publiée et qualifiée au cutoff du 7 novembre 2026
à 15:48:28 UTC :** `9f432e3` (« Support reversible permission-group
deactivation without removing memberships »), **21 fichiers, 1110 ajouts
et 37 suppressions**, est vérifié égal à `HEAD` et `origin/main` sur `main`.
`GroupLifecycle` relie en OneToOne l'état d'un groupe dans son tenant ;
les migrations `0006_group_lifecycle` des deux SIS préservent les anciens
groupes sans état comme **actifs**. L'API expose le booléen `actif` à la
création et en PATCH/PUT ; son omission conserve l'état. Les backends
ModelBackend/Guardian dérivés filtrent les groupes désactivés, avec couverture
sync/async, `with_perm` et préchargement Guardian. Droits directs, autres
groupes actifs, rôle et `is_staff` restent inchangés. Les gardes de
délégabilité, scopes, tenant et propre groupe sont conservées ; les
permissions objet sont contrôlées à la bascule et l'échec d'audit annule
l'opération. Le snapshot de capacités exclut aussi les **noms** des groupes
Django désactivés, tandis que les listes d'appartenance conservent leurs
identifiants. Les groupes de configuration académique restent indépendants,
calculés selon leurs propres conditions.

La console ajoute la case **« Groupe actif »**, le suffixe inactif, la
copie conservant l'état et l'état avant/après dans l'audit. Sans `actif`
dans l'ancienne API, pas de bascule ; une réponse ne confirmant pas l'état
est une erreur. Le PATCH contient uniquement les champs modifiés depuis
le snapshot initial figé : une bascule seule envoie **`{"actif": false}`**,
sans écraser un nom ou des permissions modifiés entre-temps. Ce mécanisme
**n'est pas un versionnement optimiste complet**.

L'image locale **`lms-sis:local-20261107-9f432e3`**, qualifiée sous
`lms-sis:qualification-wave24-release-d0c25c75`, porte le digest
`sha256:12bd66a6402e7a3987b866ac04c6a9a3a25958f066ac96b4b2d7e0f8ed8dec6f`.
`wave24-backend-build-release.log` conserve ce digest ; les empreintes des
**15 fichiers Python** de `wave24-image-source-comparison.json` correspondent
au snapshot publié `9f432e3`. Pas d'overlay backend pendant suites ou
navigateurs selon le parent : `wave24-container.sh` ne monte que les scripts
et `frontend-app-sis/src/services/api.js` pour la collecte ; les serveurs
navigateur ne montent que des settings synthétiques.

Les suites intégrales **release**, sélection
`python -m pytest --confcutdir=.. -p no:cacheprovider -o addopts= --tb=short -q apps ../sis_common/tests`,
passent : `wave24-secondaire-full-release.log` **814 tests et 496 sous-tests,
574,20 s** ; `wave24-superieur-full-release.log` **818 tests et 430 sous-tests,
707,37 s**. Ne sommer ni variantes ni campagnes en tests uniques.
Les deux `wave24-*-checks-release.log` attestent les checks sans erreur et
les migrations sans dérive, **avec l'avertissement connu `guardian.W001`**.
Guardian reconnaît le chemin exact du backend standard, pas son dérivé ;
**ne pas ajouter le backend standard**, qui réaccorderait les droits filtrés.

Le premier `wave24-secondaire-full-final.log`, sur l'image intermédiaire
`91652…` selon le parent, reste **rouge : 1 échec, 813 tests et 496 sous-tests
passés**, `FakeGroups` n'ayant pas de méthode `filter`. La correction concerne
le **double de test**, pas un fallback en production ;
`wave24-authorization-double.log` passe ensuite **15 tests**. L'adaptation et
le formatage finaux du double sont inclus dans le commit et les nouvelles
intégrales release vertes. Les anciens ciblages 76/135 et 77/135 sur `1b9…`,
ainsi que les navigateurs antérieurs au filtrage des noms, restent
intermédiaires selon le parent : ils ne sont pas les résultats finaux
importés et leurs journaux ne sont pas réécrits.

`wave24-group-lifecycle-ui-final.log` passe **31 tests du composant** ;
`wave24-frontend-browser-build-final.log` compile avec **3 avertissements
habituels de taille/performance**. ESLint, Black, isort et flake8 ciblés sont
verts selon le parent, sans inventer de journal dédié ni de suite frontend
intégrale. Les journaux `wave24-browser-groups-{secondaire,superieur}-release.log`
et reçus des dossiers homonymes passent **deux cas par variante** sur
l'image finale `12bd…`. Le premier reprend audit, copie, lots atomiques et
refus apprenant. Le second connecte l'apprenant **avant** affectation :
accès au compte voisin **200**, désactivation UI puis **404** avec permission
et nom du groupe absents des capacités, réactivation UI puis **200** et
permission/nom rétablis, dans la **même session**, sans retirer membres ni
permissions. Les actions API sont réelles, sans réponses simulées.

Les bases navigateur **synthétiques `sis_wave21_browser_*` sont réutilisées
et migrées en 0006**, pas créées pour 24. API/passerelle24 arrêtées après
qualification selon le parent ; PostgreSQL/Redis20 restent privés pour25.
Ces faits ne constituent pas un déploiement partagé. Quinze artefacts sont
hachés dans la matrice, en trois campagnes : backend release et historique
rouge, UI/build, puis navigateurs finaux.

**Limites conservées :** audit des API groupes seulement, pas audit universel
ORM/admin ; appels directs aux backends/raccourcis natifs Guardian hors de
ces contrôles non couverts. Les caches Django sont par instance : recharger
l'utilisateur dans un traitement long ; les anciennes sessions enregistrant
l'ancien backend nécessitent une reconnexion. Migrer **tous les schémas avant
trafic** : aucun déploiement partiellement migré qualifié ; revenir à l'ancien
code peut réaccorder les droits. Pas de nouvelle SSO/LMS réelle, qualification
de tous menus/rôles, MFA/SoD, versionnement complet, dates de délégation,
rôles métier, pilote, production ou réception institutionnelle. **94 statuts
inchangés**, IAM en cours, F07 ouvert, F09/10.7 partiels, **pas 100 %**.
Aucune qualification25 importée ; politiques, preuves22/23 et rouges
historiques intacts, dont le dernier500 (**500 timeouts, 262 écritures
indéterminées**). Aucun test ni service lancé pour cet import documentaire.

**Vague 25, preuve provisoire au cutoff du 7 novembre 2026 à
16:35:02 UTC — qualification en cours, non publiée :** préparation limitée
aux deux registres du worktree `LMS_SIS-wave25-projects`, base `a5e0797`.
Le code projets n'est pas committé ; ce SHA de base **n'est pas le SHA
du nouvel incrément**. Le parent autorise **10.5 : absente → partielle**,
pas vérifiée, après confrontation de son obligation et de ses deux critères.
L'ancienne évaluation de 10.5 est archivée dans l'update JSON ; les 94 IDs,
les 93 autres statuts, les politiques et tous anciens cutoffs sont conservés.

Le gestionnaire couvre les projets **individuels et collectifs**, équipes,
appartenances historisées, jalons/échéances/barèmes, livrables PDF privés
révisionnés, évaluations de groupe, contributions individuelles privées et
publication humaine. Le contrat est décrit dans `sis_apps/README.md:204` ;
API `/api/v1/core/projets/` dans les deux SIS, migrations
`0010_pedagogical_projects`, pages `/secondaire/projets` et `/superieur/projets`.
`sis.projects` est **désactivé par défaut** ; capacités serveur et refus par
défaut contrôlent routes, fichiers et UI. Un conflit **409** conserve les
saisies et impose rechargement puis nouvelle confirmation, sans rejeu
automatique. Stockage privé persistant, limite PDF **25 Mio** par défaut ;
extension/type MIME/signature PDF ne constituent **ni antivirus ni signature
électronique d'auteur**. Les évaluations ne sont pas des notes officielles.
**Restent non réalisés : liens cours/classes/ECUE/compétences, notes
officielles et synchronisation LMS.** Aucun de ces liens n'est inféré du
seul usage des mots « projet », « évaluation » ou « publication ».

**Confrontation des critères de 10.5 :** création collective, équipes,
jalons, dépôt et évaluations de groupe/contributions sont exercés par
API et navigateur ; le mode individuel est couvert par les tests API,
pas par un parcours navigateur individuel revendiqué. Deux équipes du
**même projet**, dont deux membres dans A, permettent de vérifier les
frontières : l'autre équipe reçoit 404 en lecture ; le test
`sis_common/tests/test_projects.py:355` couvre aussi le refus du POST privé
avant parsing. Brouillon invisible, publication humaine et seule contribution
personnelle visible sont testés. Ces acquis retirent la fonction principale
de la catégorie « absente », sans satisfaire toute l'exigence ni une recette
institutionnelle ; les limites et attentes empêchent « vérifiée ».

Le parent a repris la qualification avec le **Dockerfile standard inchangé**
et `wave25-standard-container.sh` **sans TMPDIR**. L'image de base
`lms-sis:qualification-wave25-release-d0c25c75` a le digest
`sha256:febf3c0fffb0a3ed540a0e84526807883a82eec05d9292820c3d2e0de46da391`.
Le rapport `wave25-image-source-comparison.json` atteste 12 fichiers Python
identiques à l'image à son cutoff. Depuis, le parent a ajouté seulement
`ui=("projets",)` à `module_registry.py` : relecture **11/12 identiques**,
le douzième retrouvant exactement l'empreinte du rapport en retirant
uniquement cette ligne, sans modifier le fichier. Le bundle frontend reste
inchangé selon le parent. **L'image febf3c0 n'est donc pas l'image finale.**
La nouvelle image standard `qualification-wave25-final-d0c25c75` est en
construction selon le parent ; aucun digest ni résultat final n'est importé.

`wave25-secondaire-standard.log` et `wave25-superieur-standard.log`
contiennent chacun **23 tests et 2 sous-tests verts**, checks sans erreur
et migrations sans dérive, **avec `guardian.W001` connu depuis24** :
ne pas ajouter les backends standards qui réaccorderaient les droits filtrés.
Black/isort/flake8 ciblés sont verts selon le parent, sans journal dédié
inventé. L'intégrale de base `wave25-secondaire-full-standard.log` passe
**830 tests et 496 sous-tests en 571,83 s** ; **l'intégrale supérieure reste
en cours au cutoff**, aucun résultat supposé. Les campagnes se chevauchent :
ne sommer ni variantes ni sélections en tests uniques.

Le premier `wave25-projects-ui-parent.log` reste **rouge : 117 passés,
1 échec sur 118, quatre suites vertes et une rouge sur cinq**. L'attente
`findByRole` de 1 s pour une recherche temporisée a été corrigée dans le
helper de test : champ actif puis option attendue jusqu'à 5 s.
`wave25-projects-ui-final.log` recontrôle seulement `ProjectsPage` et
`navigation.projects` : **24/24 verts sur deux suites**, pas une relance
verte des cinq suites. Le premier lint agent omettait JSX
(`fedx-scripts eslint src/projects` sans `--ext`) ; le parent atteste le
contrôle corrigé `--ext .js,.jsx` vert après formatage. Le build
`wave25-projects-frontend-build-final.log` passe avec **3 avertissements
Webpack habituels**, sans déduire une suite frontend complète.

Sur l'image **de base**, `wave25-browser-projects-secondaire-r7.log` et
`wave25-browser-projects-superieur.log` passent chacun **un parcours réel** :
collectif, deux équipes, jalon, PDF avec xref valide et SHA, remise tardive,
dépôt/téléchargement réels, brouillon invisible, publication humaine,
contribution privée, autre équipe404, retrait404 puis rétablissement,
désactivation du module403 puis réactivation200. Pas de réponse simulée.
Les six essais secondaires préliminaires restent rouges et hachés :
Escape fermant le dialogue, libellés MUI requis, mot de passe de fixture5,
lecture de réponse d'authentification après navigation, `data-testid` MUI
absent en production, rafraîchissement déjà fermé par révocation ;
causes de harness/fixture rapportées par le parent. Le supérieur passe au
premier essai. **Ces parcours ne qualifient pas la future image finale.**

Les bases sont des **clones synthétiques dédiés25 des bases21**, pas des
bases partagées. Les logs `wave25-{secondaire,superieur}-{before,after}-restart.log`
montrent des identifiants de conteneur différents, même image et mêmes
volumes privés. Le script `wave25-projects-after-restart.cjs` effectue de
vrais GET HTTP après recréation : projet, équipe, jalon, livrable/PDF au
**même SHA**, évaluation publiée et **seule contribution propre**.
Les deux `wave25-projects-*-persistence.json` concordent avec les reçus de
projet navigateur. Les helpers API/nginx sont arrêtés selon le parent.
Cette persistance bornée sur l'image de base **n'est pas une qualification
de redéploiement en production**, ni une nouvelle sauvegarde/restauration
institutionnelle.

`wave25-projects-sql-provenance.json` est conservé comme **intermédiaire** :
ancien Dockerfile dérivé et TMPDIR ajoutés sans essai ni échec standard
préalable. Ses résultats ne prouvent pas l'installation standard ; il garde
aussi son premier 22-passés/1-échec de double de réponse streaming. Les
preuves standard reprises par le parent sont distinctes et ne réécrivent
ni cet artefact, ni les rouges UI/navigateur.

**Attentes bloquant la conclusion de vague25 :** résultat intégral supérieur
sur la base, SHA final du code, digest/provenance de la nouvelle image
standard, recontrôles modules/registre/projets des deux SIS et nouveaux
parcours navigateur sur cette image après correction du manifeste. Pas de
publication/qualification finale déclarée avant transmission du parent.
**État courant : 1 vérifiée, 72 partielles, 19 absentes, 2 non vérifiées** ;
10.5 partielle seulement, F-lots non clos, F07 ouvert, F09/10.7 partiels,
IAM en cours, **100 % non atteint**. Aucun déploiement partagé, réception
d'établissement ou charge500 corrigée : dernier rouge **500 timeouts,
262 écritures indéterminées**. Aucun test/service/commit/push pour cet import.

**Vague 25, complément provisoire au cutoff du 7 novembre 2026 à
16:42:03 UTC :** les deux intégrales standard sont maintenant confirmées
sur l'image **de base `febf3c0…`** : secondaire **830 tests et 496 sous-tests,
571,83 s**, supérieur **834 tests et 430 sous-tests, 755,45 s**.
`wave25-superieur-full-standard.log` apporte le résultat auparavant attendu ;
le log secondaire et le cutoff provisoire précédent restent intacts.
**Ces intégrales n'ont pas été réexécutées sur la nouvelle image finale.**

L'image standard `lms-sis:qualification-wave25-final-d0c25c75` porte le digest
`sha256:488312ed06d9dba5b27d47fc8284786448cc2b06cdd92854f9e31c1f39421add`.
`wave25-image-source-comparison-final.json` et la relecture du worktree
confirment **12 fichiers Python identiques** ; seul `module_registry.py`
diffère de l'image des intégrales, avec `ui=("projets",)`. Ce contrôle lie
l'image aux fichiers de travail observés, **pas encore à un SHA code publié**.
Le bundle frontend est inchangé selon le parent.

`wave25-browser-projects-secondaire-final.log` et
`wave25-browser-projects-superieur-final.log` passent chacun **un parcours**
sur `488312…` selon le parent, avec reçus `.last-run.json` verts et nouveaux
reçus de projets dont les IDs diffèrent des parcours de base. Le scénario
reste collectif : dépôt/téléchargement PDF, brouillon/publication humaine,
contribution privée, autre équipe404, retrait/rétablissement et module403/200.
Le log secondaire a les mêmes octets que le précédent (mêmes libellés et
durées arrondies) : son hash seul ne distingue pas les exécutions. Les
reçus de projets sont distincts ; le rattachement au digest final est
attesté par le parent. Les anciens parcours restent des preuves de **base**.

**Toujours en cours au cutoff :** checks/migrations et sélection de
**26 tests** projets/modules/registre sur l'image finale dans les deux SIS,
**sans résultat importé**, contrôle complémentaire de persistance sur cette
image, puis SHA code. Les premières persistances réussies restent attachées
à `febf3c0…` ; ne pas les transférer à `488312…`. Deux campagnes documentaires
supplémentaires distinguent intégrales **BASE** et provenance/navigateurs
**FINALE**, sans addition en tests uniques ni conclusion anticipée.
Statuts **1/72/19/2** inchangés depuis la réévaluation autorisée de10.5 ;
liens académiques/notes officielles/LMS toujours absents, aucune publication,
réception d'établissement, livraison partagée ou réparation de charge500.

**Vague 25, qualification bornée achevée et publication confirmée au cutoff
du 7 novembre 2026 à 16:46:20 UTC :** le commit **`13e99f5`**
(« Add private pedagogical projects with teams, deliveries and human
assessment », 25 fichiers, 4423 ajouts/6 suppressions) est vérifié égal à
`HEAD`, `main` et `origin/main` ; fast-forward/push attestés par le parent.
Le tag local **`lms-sis:local-20261107-13e99f5`** désigne selon le parent
l'image standard finale `qualification-wave25-final-d0c25c75`, digest
`sha256:488312ed06d9dba5b27d47fc8284786448cc2b06cdd92854f9e31c1f39421add`.
Les **12 empreintes Python** du rapport final correspondent au commit
publié, et pas seulement aux fichiers de travail. L'unique différence
Python avec la base des intégrales demeure `module_registry.py`,
`ui=("projets",)` ; le bundle frontend reste inchangé.

**BASE et FINALE restent séparées :** les intégrales **830 tests/496
sous-tests secondaire, 571,83 s**, et **834/430 supérieur, 755,45 s** ont
été exécutées sur `febf3c0…`. Les recontrôles de l'image **FINALE `488312…`**
sont dans `wave25-secondaire-final.log` et `wave25-superieur-final.log` :
checks sans erreur, migrations sans dérive, **26 tests et 15 sous-tests
verts chacun**, respectivement **110,22 s et 150,52 s**, pour
projets/modules/module_registry. `guardian.W001` reste présent et documenté :
**ne pas ajouter les backends standards**. Ces sélections finales ne sont
pas des suites intégrales ; aucun cumul avec les campagnes de base en
tests uniques. Les deux parcours navigateur finaux déjà importés restent
rattachés à `488312…`, sans transformer les premiers parcours de base.

La persistance sur l'image **FINALE** est désormais rapprochée des
**nouveaux reçus de projets finaux**, pas des reçus de base :
`wave25-projects-secondaire-persistence-final.json` et
`wave25-projects-superieur-persistence-final.json` confirment par GET HTTP
après arrêt/recréation API le projet, l'équipe, le jalon, le PDF au même
SHA, l'évaluation publiée et **seule contribution propre**.
Pour le supérieur, `wave25-superieur-final-before-restart.log` et
`wave25-superieur-final-after-restart.log` montrent des IDs de conteneur
distincts, même digest final et même volume privé. Pour le secondaire,
**seul `wave25-secondaire-final-after-restart.log` est capturé** :
les commandes d'arrêt/recréation sont attestées par le parent, mais aucune
capture « before » finale n'est disponible ni inventée. L'ancienne paire
avant/après sur `febf3c0…` reste historique et **ne remplace pas** cette
capture manquante. Les GET et le reçu final prouvent la continuité bornée
des objets/fichier contrôlés, pas une restauration ou un redéploiement
institutionnel exhaustif.

Tous les helpers API/nginx sont arrêtés selon le parent ; PostgreSQL/Redis
privés restent pour la prochaine vague. Aucun sondage ou arrêt de service
effectué pour cet import. Onze artefacts sont référencés/hachés dans ce
dernier update, réparti en **deux campagnes : publication/recontrôles
ciblés FINALE, puis persistance FINALE avec sa limite de capture**.
Les cutoffs provisoires 16:35 et 16:42, leurs attentes alors ouvertes,
les premiers rouges et la provenance SQL dérivée sont conservés intacts.

**Conclusion bornée : 10.5 partielle**, pas vérifiée ; **1 vérifiée,
72 partielles, 19 absentes et 2 non vérifiées sur94**, les 93 autres
statuts inchangés. La fonction projets est livrée et qualifiée dans les
périmètres décrits ; les liens cours/classes/ECUE/compétences/notes officielles
et LMS restent non réalisés. PDF validé par format/signature, **pas antivirus**.
Pas de réception d'établissement, déploiement partagé, pilote/production
ou charge500 corrigée ; dernier rouge **500 timeouts, 262 écritures
indéterminées**. F07 ouvert, F09/10.7 partiels, IAM en cours, **pas100 %**.
Aucune qualification de la vague suivante importée ; aucun commit/push
effectué par cet import documentaire.

**Vague 26, publiée et qualifiée au cutoff du 7 novembre 2026 à
17:47:21 UTC :** `4f282a20bf474bcf37fbfab7cb2d99c44badd7b6`, vérifié
égal à `HEAD` et `origin/main` sur le principal propre avant cet import ;
comparaison `ls-remote` et publication attestées par le parent. Le lien
optionnel `cours` est une **FK PROTECT vers `EdxCourseMapping` local
préexistant**, via les migrations `0011_project_course` des deux SIS.
Il fournit le contexte classe/matière au secondaire, ECUE au supérieur,
**sans créer un cours LMS, inscrire un apprenant ou écrire une note officielle**.

La recherche paginée ne propose que l'intersection des cours actifs
accessibles au gestionnaire **et** au responsable. Elle réutilise sans les
modifier les helpers `apps.integration.api.visible_course_mappings` :
tenant, classe/niveau/année/matière au secondaire, années de semestre
**et** de maquette au supérieur, scopes reconnus et prérequis `is_staff`.
La permission explicite `integration.view_edxcoursemapping` est exigée
pour chacun des deux comptes ; staff ou rôle enseignant seul ne suffit pas.
**Aucun enseignant non staff n'est promu implicitement** ; les projets non
rattachés restent utilisables selon leurs permissions projets existantes.
Un lecteur sans droit voit `{disponible:false}`, sans ID, nom ni contexte.

Omettre `cours` conserve le lien, `null` le retire explicitement ;
réaffecter le responsable revalide le mapping conservé. Un mapping inconnu,
inactif, étranger ou hors périmètre produit un **400 générique** sans mutation
ni audit de succès ; une version obsolète produit **409**. L'UI conserve
les saisies, recharge la version sans rejouer la commande puis exige
une nouvelle confirmation humaine. Retirer le lien ne supprime pas l'équipe.

Le correctif final protège aussi l'historique après déplacement du contexte
académique **même si les IDs classe/ECUE restent identiques** : chaque
snapshot porte une empreinte interne versionnée des dimensions tenant et
académiques, comparée au contexte courant. Noms et codes descriptifs en
sont exclus : un simple renommage garde les libellés historiques lisibles.
Empreinte absente, inconnue ou malformée : contexte masqué, sans réécriture
des preuves persistées. Les champs internes ne sont jamais exposés, y
compris dans `metadata.avant.cours`. Les tests couvrent les changements
de niveau/année et UE/formation/années de maquette et semestre.

Image standard corrigée **`lms-sis:local-20261107-4f282a2`**, digest
`sha256:e89d28822086501f1442b973184e729e81f80bd10462d270920f47621c871ac7`.
Le rapport `wave26-image-source-comparison-final.json` conserve **7 fichiers
Python source/image identiques**, également rapprochés au commit publié.
Dockerfile standard, aucun overlay backend ni TMPDIR selon le parent ;
les captures navigateur ne montrent que volume privé et settings synthétiques.
`wave26-secondaire-final.log` passe **40 tests/17 sous-tests en127,31 s**,
`wave26-superieur-final.log` **40/20 en152,76 s**, avec checks sans erreur
et migrations sans dérive. **`guardian.W001` connu reste présent : ne pas
ajouter les backends standards**. L'ancienne image `47a…` et les anciens
37/15 sont antérieurs au correctif, pas des substituts à ces résultats.
**Aucune suite intégrale26** : les intégrales25 ne qualifient que25 BASE,
sans total de tests uniques additionnant variantes ou campagnes.

`wave26-projects-ui-parent.log` passe **32/32 sur deux suites**
(`ProjectsPage` et navigation), pas toute la suite frontend.
`wave26-frontend-browser-build.log` compile avec **3 avertissements
habituels de taille/performance** ; UI inchangée depuis selon le parent.
Black/isort/flake8 des sept Python, ESLint `src/projects --ext .js,.jsx`
et quatre fichiers E2E, ainsi que diff-check : verts attestés dans le
terminal parent `wave26-final-quality`, **sans journal local inventé**.
`project-helpers.js` et `project-courses.e2e.js` sont publiés ; le scénario
collectif25 reste exercé, sans réponse réseau simulée.

Le premier `wave26-browser-projects-secondaire.log` reste **rouge :
1 passé/1 échec sur2**, assertion de visibilité à5 s alors que le chargement
n'était pas achevé. Sa trace, lue sans extraction, contient des GET projet
HTTP200 ; elle ne constitue pas un parcours réussi. Correction du **harness
seulement** : attendre explicitement le heading jusqu'à20 s.
`wave26-browser-projects-secondaire-recheck.log` et
`wave26-browser-projects-superieur.log` passent ensuite **2/2 chacun**.
Chaque variante vérifie création avecA, contexte apprenant masqué, omission
conservant le cours, choixB avec409/saisies conservées/sans rejeu/confirmation,
ID inconnu400 sans mutation, retrait explicite conservant l'équipe puis
rattachementA. Le second scénario conserve le collectif PDF/SHA, contributions,
publication, retrait d'accès et désactivation/réactivation du module.

Les quatre captures `wave26-{secondaire,superieur}-{before,after}-restart.json`
sont présentes : IDs de conteneur différents, mêmes images et volumes privés.
Les quatre reçus `wave26-course-*-persistence.json` et
`wave26-projects-*-persistence.json` sont rapprochés aux nouveaux reçus
navigateur : vrais GET HTTP authentifiés après recréation vérifient
cours/version, masquage apprenant, équipe conservée, PDF au même SHA,
évaluation publiée et seule contribution propre. Le script cours26 est
lu ; `wave25-projects-after-restart.cjs` est réutilisé **sans modification**,
empreinte25 identique. Ce ne sont ni une restauration exhaustive ni une
qualification de déploiement institutionnel.

Les fixtures `wave26-browser-fixture-{secondaire,superieur}.log/.json`
attestent les mappings locaux **2 et3**, anciens mappings/outbox/accès
inchangés, **aucun provisioning** ; bases `sis_wave26_browser_*` isolées.
Helpers API/nginx26 explicitement arrêtés selon le parent ; codes137 observés
après ces arrêts Docker, **sans diagnostic OOM supplémentaire**. PostgreSQL/Redis
historiques privés restent disponibles, aucun service partagé touché.
Les **29 artefacts lus puis hachés** sont répartis en quatre campagnes :
backend corrigé, UI/build, navigateurs avec rouge préservé, fixtures/persistance.

**10.5 reste partielle**, avec interdiction conservée de **lecture ET écriture
des livrables d'une autre équipe**. Restent compétences, notes officielles,
provisioning/inscriptions/synchronisation LMS, parcours enseignants non staff
et réception complète. **1 vérifiée,72 partielles,19 absentes,2 non vérifiées
sur94**, aucun statut/F-lot promu, aucun lot27 qualifié. Pas de déploiement
institutionnel, nouvelle charge500 ou100 % : dernier rouge **500 timeouts,
262 écritures indéterminées**. Politiques, cutoffs et preuves historiques
intacts ; aucun test/service/commit/push pour cet import documentaire.

**Vague 27, publiée et qualifiée au cutoff du 7 novembre 2026 à
18:25:28 UTC :** `a0ddbaa4421fdb696099b8cd804eafbbae61fb27`, vérifié égal
à `HEAD` et `origin/main` sur le principal propre avant import ; comparaison
distante et publication attestées par le parent. Le commit modifie cinq fichiers :
helper cours, tests associés, README et scénario/config navigateur enseignants.
**Aucun statut promu : 1 vérifiée,72 partielles,19 absentes,2 non vérifiées sur94**.
Seule la portée courante de10.5 est actualisée, sans modifier ses critères.

Le parcours **non staff** exige `integration.view_edxcoursemapping`,
les permissions/scopes projets, un profil réel et le rôle `enseignant`
(également `chercheur` au supérieur). Il réutilise le queryset local
`apps.portail.api._TenantTeacherPortal._affectations_queryset`, **sans modifier
les portails ni appeler leurs actions HTTP**. Au secondaire, une même affectation
doit relier profil/classe/matière/année, avec tous les parents locaux.
Au supérieur, une affectation ECUE ne couvre pas ses frères ; une affectation
UE sans ECUE couvre ses ECUE, mais une UE explicite contradictoire est refusée.
L'année d'affectation doit égaler celles de maquette **et** de semestre ;
formation/département/faculté doivent être locaux. **Formation sans département
non éligible au non-staff** ; aucune condition temporelle `en_cours` inventée.

La branche staff conserve la frontière administrative26 ; chaque acteur et
responsable reste contrôlé, y compris les couples staff/non-staff.
Aucun staff automatique, accès administrateur LMS, provisioning, inscription
ou droit aux notes n'est accordé. Le retrait d'affectation masque le contexte
du détail et de l'historique **sans réécrire les preuves persistées** ; une
configuration conservant le lien devient400 sans mutation. Le retrait explicite,
les projets non rattachés et les activités autonomes du projet restent possibles
selon leurs droits propres. Verrous projet/mapping et revalidation sont conservés ;
**la concurrence exacte édition d'affectation contre rattachement n'est pas qualifiée**.

Image standard **`lms-sis:local-20261107-a0ddbaa`**, digest
`sha256:cefe061a07c134d2a428f82a5849fb9e2edc8e99fe9f4b0e0e077cf0cc3e7aae`.
Le build et `wave27-image-source-comparison.json` sont lus : **deux Python
identiques source/image/commit publié**, frontend `src` et manifests inchangés
depuis `4f282a2`, portails inchangés également. Aucun overlay applicatif backend
pour la qualification finale ; runner standard limité aux scripts/collecte frontend,
navigateurs limités aux settings synthétiques et au volume privé.

`wave27-secondaire-standard.log` : **48 tests passés,1 ignoré,26 sous-tests,
128,59 s** ; le skip concerne uniquement le contrat UE/ECUE du supérieur.
`wave27-superieur-standard.log` : **49 tests/29 sous-tests,145,35 s**.
Checks sans erreur et migrations sans dérive, avec **`guardian.W001` connu**
(ne pas ajouter les backends standards pour le faire disparaître).
Campagne séparée `wave27-*-portals-integration.log` : secondaire
**28 tests/8 sous-tests,93,87 s**, supérieur **27/8,112,68 s**.
Ne pas sommer variantes/campagnes comme tests uniques ; **aucune intégrale27**.

Les deux `wave27-*-baseline-reproduction.log` restent **rouges attendus** :
le nouveau positif non-staff échoue sur l'ancien backend26 `e89d…`, liste vide
au lieu du cours attendu, **1 échec en90,32 s /107,83 s**. Selon le parent,
seul le nouveau fichier de tests est monté en lecture seule pour cette
reproduction, pas le code applicatif. Ces rouges ne qualifient pas l'image27
et ne remplacent pas ses campagnes finales vertes.

Qualité Python attestée par le parent (Black/isort/flake8) :
`wave27-python-quality.log` conserve le résultat Black «2 fichiers inchangés» ;
les outils silencieux ne reçoivent pas de sortie inventée. ESLint des deux
nouveaux E2E vert dans `wave27-e2e-quality.log`, diff-check vert attesté.
Les neuf erreurs de formatage initiales ont été corrigées par autofix selon
le parent, **avant tout lancement navigateur**. Aucun nouveau Jest ni build
frontend27 : le bundle26 est réutilisé, **ses32 tests ne deviennent pas des tests27**.

Le premier `wave27-browser-teachers-secondaire.log` reste **1 échec** :
`getByRole('option')` global comptait trois options au lieu d'une ; le contexte
d'erreur montre les deux choix «Contexte SIS» en plus du cours attendu.
Correction du **harness uniquement**, recherche d'options limitée au `listbox`.
`wave27-browser-teachers-secondaire-recheck.log` et
`wave27-browser-teachers-superieur.log` passent **1 cas chacun**, en54,1 s
et54,3 s pour les cas (durées totales des runs56,2 s et56,1 s).

Ces parcours réels utilisent deux enseignants A/B **non staff**, dont les scopes
autorisent les mappings2 et3 mais les affectations diffèrent : A ne choisit queA,
admin avec responsableA également, B seulementB. B reçoit404 sur GET/POST du
projetA ; l'endpoint administratif mappings reste403. Suppression d'affectation
par admin HTTP204, puis **même sessionA** rechargée : détail/historique masqués,
choix vides, conservation400 sans mutation. Retrait explicite par UI conservant
l'équipe ; restauration admin POST201 avec nouvel ID, puis même sessionA
choisissant de nouveauA par UI, sans accès administratif. **Aucune réponse réseau
simulée**. Les `wave27-browser-projects-{secondaire,superieur}.log` passent
séparément **2/2 chacun** : rattachement administratif26 et collectif privé25
(PDF/SHA, contributions, publication, retrait et module). Reçus et `.last-run.json`
finaux verts, premier reçu rouge conservé.

Quatre captures `wave27-{secondaire,superieur}-{before,after}-restart.json`
attestent IDs de conteneur différents, même image et mêmes volumes par variante.
**Six reçus HTTP authentifiés** `wave27-{teacher,course,projects}-*-persistence.json`
sont rapprochés aux reçus navigateur après arrêt/recréation : cours/version/équipe
enseignant et affectation restaurée persistants, autre enseignant404, mappings
admin403, contexte apprenant invisible ; cours administratif et PDF au même SHA,
évaluation publiée et contribution propre persistants.
Nouveau `wave27-teacher-after-restart.cjs` ; scripts26 cours et25 projets
réutilisés **sans modification**, empreintes précédentes confirmées.

Fixtures DB27 et volumes27 **clonés de26 au repos selon le parent**, pas services
partagés. Script et reçus `wave27-browser-fixture-*` gardés : comptes antérieurs,
mappings/outbox/intent/enrollment/notes/évaluations/projets/audit inchangés.
**Exception synthétique explicite au supérieur** : F1 id1 sans département reçoit
un département/faculté locaux sous gardes ;
`formation_department_link_added={"formation_id":1,"departement_id":1}`.
Ne pas présenter cette adaptation comme aucune mutation de la structure académique,
ni comme provisioning LMS ou qualification complète du portail enseignant.

Les **47 artefacts lus puis hachés** sont répartis en quatre campagnes documentaires :
backend/portails/baseline, enseignants navigateur/qualité E2E, régressions projets,
fixtures/persistance. API/nginx27 arrêtés explicitement selon le parent ;
codes137 observés après arrêt, **sans diagnostic OOM supplémentaire**.
PostgreSQL/Redis privés conservés. Aucun service partagé touché ou sondé ici.
**10.5 reste partielle**, avec interdiction de **lecture ET écriture des livrables
privés d'une autre équipe** intacte. Compétences, notes officielles, LMS réel,
recette multirôles/institutionnelle et restauration globale restent ouverts.
Pas de nouvelle charge500 : **500 timeouts,262 écritures indéterminées** restent
rouges ; pas de déploiement partagé/pilote, aucun lot28 qualifié,100 % non atteint.
Historiques/cutoffs26 et antérieurs intacts ; aucun test/service/commit/push/agent
pour cet import documentaire.

**Vague 28, publiée et qualifiée au cutoff du 7 novembre 2026 à
19:20:43 UTC :** `8cf8002bfa9b9192f8d1bd222c35041a60075dcd`, vérifié égal
à `HEAD` et `origin/main` sur le principal propre avant import, commit horodaté
19:17:54 UTC ; provenance publiée capturée à19:18:05 UTC.
**Les45 anciens updates, leurs cutoffs, les94 IDs/statuts et critères sont
intacts : 1 vérifiée,72 partielles,19 absentes,2 non vérifiées.**
Seul le périmètre courant10.5 est enrichi, aucun statut ni F-lot clos.

**Clarification de portée après relecture :** la source originale
`paste-1793818759374.txt:918` porte sur les projets individuels/collectifs,
leurs étapes, livrables et évaluations. `required_behaviors` et
`acceptance_checks` sont inchangés. **La lacune identifiée pour10.5 est
l'absence de parcours navigateur INDIVIDUEL complet livré/qualifié au cutoff** :
l'API individuelle couvre surtout cohérence/refus, seuls les collectifs ont
des parcours complets qualifiés. Acquisition, notes officielles et
provisioning/synchronisation LMS restent hors de ce périmètre obligatoire ;
leur non-réalisation dans le programme n'ajoute aucune nouvelle condition
à10.5. Les limites de concurrence et de qualification institutionnelle
ci-dessous ne sont pas non plus de nouveaux critères d'acceptation.

Les **compétences visées sont des objectifs facultatifs, pas des acquis**.
Leur source exclusive est `classe.offre_configuration` au secondaire et
`formation.offre_configuration` au supérieur, **pas la maquette**, ni un
catalogue courant de substitution. Le sélecteur paginé exige droits projets
et cours, intersection acteur/responsable, scopes et affectations non staff27.
Les modes `numeric`, `pass_fail` ou offre absente donnent une liste vide
explicite ; une offre corrompue donne400, sans repli sur un autre catalogue.

Le contrat accepte **0 à100 codes uniques** : omission conserve en configuration,
`[]` retire ; `null`, types/codes/labels client invalides donnent400 sans mutation
ni audit de succès. Migration `0012_project_competencies` des deux SIS :
snapshot privé, libellés choisis conservés à l'usage et dans les preuves historiques.
La projection publique est uniquement `null`, `{disponible:false}` ou
`{version:1,disponible:true,criteria}` ; **jamais `_offre` ou `_contexte`**.
Perte d'accès ou déplacement académique masque codes/libellés, y compris
l'historique, sans réécrire les anciennes preuves.

Changement de cours/responsable/offre revalidé, retrait explicite possible même
si la source est corrompue. Une nouvelle sélection capture l'offre courante
sous verrou de source ; **aucun jeton client de révision d'offre**.
Ne pas assimiler ces verrous/revalidations à une qualification de concurrence
offre/sélection ou d'édition d'affectation contre rattachement. L'UI bloque
la confirmation pendant chargement/pagination/erreur, conserve les choix pour
réessayer, distingue retrait explicite et nouvelle sélection ;409 conserve le
brouillon et exige rechargement puis nouvelle confirmation, sans rejeu automatique.

Image standard **`lms-sis:local-20261107-8cf8002`**, digest
`sha256:c789651e2582c850a01ef8613f928fffbb4ef19bdbcb5ae7a520e475cbc72436`.
`wave28-published-source-provenance.json` rapproche **huit Python
committés/source/image**, vérifiés ici au commit publié. Dockerfile standard,
aucun overlay applicatif backend pour les campagnes finales ; navigateurs
avec seul settings synthétique monté en plus du volume privé. Les correctifs
ultérieurs du sélecteur ont modifié seulement l'UI, pas ces Python.

`wave28-secondaire-standard.log` : **87 passés,1 skip,26 sous-tests en143,09 s** ;
`wave28-superieur-standard.log` : **88 passés/29 sous-tests en163,83 s**.
Sélection projets/cours/compétences/modules/registre/profils, **pas intégrales28**.
Le skip secondaire reste spécifique au contrat UE/ECUE supérieur.
Checks sans erreur, migrations sans dérive, **avertissement `guardian.W001` connu**
conservé ; ne pas ajouter les backends standards pour le masquer.
Les logs de migration des fixtures confirment0012 dans les deux SIS.

Qualité Python finale verte selon le parent ; `wave28-python-quality-final.log`
montre Black «8 fichiers inchangés», sans inventer de sortie des outils silencieux.
`wave28-eslint-final.log` est **vide** : succès attesté par le parent, pas preuve
autonome de code de sortie. Le lint ciblé du sélecteur enregistre explicitement0.
`wave28-projects-ui-parent.log` passe **40/40 sur deux suites en251,676 s** :
34 projets et6 navigation, avec dépréciations connues.
Les **deux régressions UI initialement rouges** sont préservées dans
`wave28-ui-selector-regression-before-20261107-1946.log`
(2 échecs,32 ignorés sur34,80,558 s) : chargement/400 et pagination/erreur
ne devaient pas autoriser une confirmation ni perdre les choix.
Après correction UI, `wave28-ui-selector-jest-after-20261107-1946.log`
passe **34/34 en202,102 s**, puis la campagne parent40/40 ci-dessus.
Ce34 recouvre les40 : **ne pas les sommer**, ni transformer le premier rouge en vert.
`wave28-frontend-browser-build.log` est le **bundle final28**, vert avec
**3 avertissements en78,185 s**, utilisé par tous les navigateurs28 selon le parent.

Les nouveaux `wave28-browser-competencies-{secondaire,superieur}.log`
passent **2/2 chacun** :54,1 s/50,9 s au secondaire,54,5 s/51,1 s au supérieur.
Parcours admin : sélectionA/B, source numérique vide, omission sans codes,
409 sans relance automatique puis confirmation, historiqueA conservé,
code inconnu400 et retrait de cours incompatible400 sans mutation,
retrait explicite puis rétablissementA avec équipe conservée.
Parcours enseignant28 non staff : créationA, apprenant masqué, vraie suppression
et restauration d'affectation par admin HTTP dans la **même session** ;
compétences/historique masqués, modification400, jalon autonome encore possible,
administration LMS403. Aucune réponse réseau simulée.

Régressions **réellement rejouées sur28** : `wave28-browser-projects-*`
**2/2 par SIS** (cours26 et collectif privé25), `wave28-browser-teachers-*`
**1/1 par SIS** (enseignants27), soit **cinq cas par SIS** avec les deux nouveaux.
Les six répertoires contiennent **dix reçus navigateur** et six `.last-run.json`
verts : **aucun rouge navigateur28**. Les logs projets, aux durées arrondies,
ont les mêmes octets que27 ; leur hash seul ne distingue pas les exécutions.
Les nouveaux IDs de projets/reçus, les captures d'image et l'attestation parent
les rattachent à28, sans réattribuer les anciennes preuves25–27.

Quatre `wave28-{secondaire,superieur}-{before,after}-restart.json` :
IDs réellement différents, même image et mêmes montages/volumes28 par variante.
**Dix reçus HTTP après recréation** sont rapprochés aux dix reçus navigateur :
projets/version/cours/objectifs/équipes, masquage apprenant, absence d'empreintes
internes, refus admin LMS pour enseignants ; anciens scénarios PDF au même SHA,
évaluation publiée et contribution propre préservés.
Le checker `wave28-competency-after-restart.cjs` est nouveau ; les scripts27
enseignant,26 cours,25 projets sont **inchangés**, empreintes précédentes confirmées.
Pour le collectif secondaire, **seul**
`wave28-projects-secondaire-persistence-recheck.json` est le reçu vert final.

**Incidents de harness préservés**, sans correctif produit :
`wave28-restart-harness-incidents.json` et
`wave28-api-secondaire-restart.log` gardent le mauvais point d'entrée
`wave15_browser_settings:application`, sortie Gunicorn4.
Correction vers `config.wsgi:application`, recheck API conservé.
Le cinquième checker secondaire reçoit429 après dix logins (throttle10/min) :
**`wave28-projects-secondaire-persistence.json` vide n'est pas une preuve verte**.
Attente61 s puis checker inchangé réussi ; son log de recheck est vide également,
la preuve positive est le JSON final et les GET authentifiés. La trace API
conserve429 puis les requêtes de reprise et l'arrêt normal.
Au supérieur, pauses61 s explicites selon le parent, sans changer throttle/cache.
Ces incidents ne constituent ni défaut produit déduit, ni qualification de charge.

Fixtures : DB/volumes28 clonés de27 **au repos selon le parent**, migration0012,
cours locaux4/5/6 (A/B compétences,N numérique), nouvel enseignant28 non staff.
Script et reçus attestent anciens comptes/cours/affectations et preuves
officielles/LMS/projets/audit inchangés pendant la préparation ; les IDs
d'affectations27 sont actualisés dans le JSON de fixture depuis les reçus27
avant les nouveaux parcours. Aucun fichier credentials/env lu ou dupliqué ici.
Ancien backend secondaire arrêté explicitement, code137 sans diagnostic OOM ;
APIs recréées Gunicorn arrêtées normalement, API/nginx28 arrêtés après
qualification selon le parent ; PostgreSQL/Redis privés conservés.

**63 artefacts immuables utiles lus puis hachés**, dont trois fichiers vides
explicitement non probants seuls, répartis en cinq campagnes documentaires.
**10.5 reste partielle**, avec interdiction de **lecture ET écriture des
livrables privés d'une autre équipe** intacte. Manque propre à la preuve10.5 :
**parcours navigateur individuel complet**, non livré/qualifié au cutoff
(API individuelle surtout cohérence/refus ; collectifs complets seuls).
Objectifs ≠ acquisition ; notes officielles et LMS distant restent non réalisés,
mais **ne sont pas de nouvelles obligations ajoutées à10.5**. Acquisition,
intégrations officielles/LMS, réception multirôles/institutionnelle et restauration
globale restent des travaux des autres F-lots du programme. Les concurrences
exactes non qualifiées restent des limites des preuves, pas des critères ajoutés.
Pas de services partagés, pilote prestataire ou production ; dernier500
toujours rouge : **500 timeouts,262 écritures indéterminées**.
IAM/F07/F09 restent ouverts, aucun F-lot clos,100 % non atteint.
Cet import documentaire n'a lancé aucun test/service/agent/broadcast,
ni commit/push ; aucun lot29 ou ultérieur qualifié.

**Vague 29, publiée et qualifiée au cutoff du 7 novembre 2026 à
20:05:28 UTC :** `0bb4766275f74ea1ba0a563ee4608f1b7c606dea`, égal à
`HEAD` et `origin/main` sur main propre avant import ; comparaison distante
attestée par le parent. Commit horodaté20:01:12 UTC, provenance publiée
capturée à20:01:26 UTC. **46 anciens updates/cutoffs,94 IDs/statuts et critères
intacts : 1 vérifiée,72 partielles,19 absentes,2 non vérifiées.**
Seule la portée courante10.5 est actualisée, sans promotion ni clôture de F-lot.

**Le cycle individuel complet n'est plus une lacune de preuve10.5.**
La source `paste-1793818759374.txt:918` exige projets individuels/collectifs,
étapes, livrables et évaluations. Le nouveau test backend et le navigateur
dédié prouvent ce cycle dans les deux SIS ; les scénarios cours26/collectif25
sont réellement rejoués29. La séparation gestion/évaluation est explicite :
gestionnaire `wave28-teacher` non staff sans permission d'évaluer, évaluateur
`wave29-evaluator` distinct non staff avec seulement le droit d'évaluer,
scopé au responsable. Alice4 et Bob5 ont chacun une équipe d'un membre.
Ajouter un deuxième membre est bloqué dans l'UI et refusé par POST400 atomique.
Jalon, deux révisions PDF privées de SHA distincts, téléchargements vérifiés ;
autre équipe : **GET et POST404**, sans mutation de version/historique.
Le gestionnaire reçoit403 pour brouillon/publication. Brouillon invisible à
l'apprenant, publication humaine par l'évaluateur distinct, contribution
d'Alice seule visible. CoursA4 et objectif «analyse A» conservés pour le
gestionnaire, masqués pour apprenant/évaluateur. Le backend compare les lignes
officielles `Note`/`Evaluation` avant/après et les trouve inchangées.

**10.5 reste partielle à cause de la règle commune déjà présente**, non d'une
nouvelle obligation d'acquisition, notes officielles ou provisioning LMS.
`wave29-project-acceptance-scope.json` la confronte au commit
`b898347b1a7eb2776752d5e93781e779c79b65f4`, lignes1517–1528 :

- **Deux établissements réellement peuplés** restent à exercer par HTTP
  authentifié. `test_projects.py:703–717` crée un objet établissement avec
  `auto_create_schema=False` ; le test de refus à719 ne constitue donc pas
  deux schémas peuplés. Le navigateur29 utilise un tenant effectif par SIS.
- **Restauration isolée de sauvegardes base/fichiers** encore à démontrer :
  recréer l'API sur son volume existant n'est pas restaurer une sauvegarde dans
  un stockage indépendant. Les clones antérieurs aux parcours ne prouvent
  pas la restauration des nouveaux projets.
- **Comparaison explicite comptes/MFA/droits/données protégées** à travers
  migration applicable et restauration encore à établir. Les gardes de fixture,
  anciennes migrations et preuves de redémarrage ne remplacent pas cette preuve.

La matrice sépare désormais `top_missing_pieces` fonctionnels (vide pour les
parcours identifiés couverts) et `common_closure_pending` relié à cette règle.
Les critères métier et bilans historiques27/28 ne sont pas réécrits.
Objectifs ≠ acquis ; acquisition/notes officielles/LMS distant restent travaux
du programme, **pas nouvelles conditions10.5**. Aucun achèvement global inféré.

**Cinq fichiers tests/harness seulement** dans le commit29 ; aucun produit,
migration ou UI produit modifié. Helper PDF collectif extrait, contenu par
défaut identique octet par octet selon `wave29-author-harness-check.log`.
Image standard **`lms-sis:local-20261107-0bb4766`**, digest
`sha256:ee2a9bc8a4a6f77e65805f190ab01bee4a179f4978866a5fc4520121419cf2c0`.
`wave29-published-source-provenance.json` : **neuf Python commit/source/image
identiques**, hashes du commit revérifiés ici. Dockerfile standard, aucun
overlay backend ; seuls settings synthétiques et volume privé montés.
`wave29-frontend-base-provenance.json` :171 entrées frontend et23 fichiers
du bundle28 inchangés selon le parent. Ici170 entrées non-env et les23 fichiers
bundle rapprochés par hash ; fichier env volontairement non lu.
**Bundle28 réutilisé, aucun nouveau build frontend29.**

`wave29-{secondaire,superieur}-standard-recheck.log` : **17/17 par SIS**,
104,81 s /126,05 s, uniquement `sis_common/tests/test_projects.py`.
Checks sans erreur, migrations sans dérive, avertissement `guardian.W001` connu.
**Pas intégrales29**, ni réattribution des campagnes SQL cours/compétences28.
Premier secondaire `wave29-secondaire-standard.log` : **1 échec,16 passés
en107,02 s**, image initiale `1075f2df…`. Assertion UUID natif contre sa chaîne,
même valeur ; seul le test devient `str(delivery['jalon'])`, puis image reconstruite
`ee2a9bc…`. Le supérieur initial n'a pas été exécuté après ce rouge.
Qualité Python/ESLint finale verte attestée par le parent ; Black indique
deux fichiers inchangés, log ESLint vide **non probant seul**, aucune sortie
d'outil silencieux inventée.

Auteur : `wave29-author-jest.log` **20 passés/14 échecs timeout5000ms**,
196,279 s ; `wave29-author-jest-30s.log` **34/34 en196,127 s** avec
`--testTimeout=30000`, sans changement produit ou tests UI.
Ne pas additionner ces34 aux40 de28, ni déclarer le premier run vert.
`wave29-author-delivery.json` décrit un livrable initial avant qualification
d'exécution parent ; découverte de scénarios/checks statiques ≠ navigateur exécuté.

Premier navigateur individuel secondaire : **1 échec en55,6 s**, heading attendu
seulement5 s pendant chargement ; trace conservée, GET détail/équipes200,
jalon encore en attente. Correction du seul harness : attente explicite20 s.
`wave29-browser-individuals-secondaire-recheck.log` passe **1/1≈2,0 min** ;
`wave29-browser-individuals-superieur.log` passe **1/1≈2,1 min**.
`wave29-browser-projects-{secondaire,superieur}.log` : **2/2 chacun**,
cours26 et collectif25 effectivement rejoués avec le helper PDF extrait.
Total **trois cas par SIS**, six nouveaux reçus navigateur, sans mock réseau :
**pas six cas par SIS**, ni requalification automatique des enseignants27 ou
compétences28. Premier rouge et ses trace/contexte restent rouges.

Fixtures29 : bases/volumes clonés de28 au repos selon le parent.
Premier `wave29-browser-fixture-secondaire.log` : `KeyError: user_id` dans
la table through du compte, transaction atomique. Correction du harness par
résolution de la clé réelle via métadonnées ; rechecks des deux SIS verts.
Seule modification déclarée d'identité préexistante : retrait de la permission
**et** du scope d'évaluation de `wave28-teacher`, nécessaires à la séparation
réelle des rôles ; gestion/lecture/affectation/mot de passe conservés.
Les autres comptes/permissions/cours/affectations/projets/notes/outbox sont
vérifiés inchangés. Nouveau seul compte `wave29-evaluator`,15 secondaire/13
supérieur. Affectations réelles27A6/B2 et28A5 résolues, sans ID périmé.
Aucun fichier credentials/env lu ou dupliqué.

**Quatre captures avant/après recréation**, IDs différents, même image/mêmes
volumes29 ; **six reçus HTTP authentifiés** concordent avec les six reçus
navigateur. Mode/version/équipes/jalon, deux SHA, évaluateur/contribution,
cours/objectifs et masquage persistants ; ancien collectif PDF/évaluation/
contribution préservés. Nouveau checker `wave29-individual-after-restart.cjs` :
quatre sessions, GET/PDF et POST refusés403/404, **aucune commande de mutation
projet réussie**, état/historique inchangés après refus.
Scripts26 cours et25 projets réutilisés **sans modification**, hashes confirmés.
Tous les reçus de persistance29 sont verts, pas429 ; ceci prouve la recréation,
**pas une restauration isolée de sauvegardes**. API/nginx29 arrêtés normalement
selon le parent, PostgreSQL/Redis privés conservés.

**50 artefacts utiles lus puis hachés**, dont le log ESLint vide identifié,
en cinq campagnes documentaires. `wave29-parent-harness-incidents.json`
conserve les trois incidents parent (UUID test, clé fixture, délai navigateur),
sans les transformer en bugs produit ni effacer leurs premiers rouges.
Les14 timeouts Jest auteur sont également conservés.
**177 campagnes documentaires non sommées** au total,25 exigences avec preuves.
Aucun service partagé, pilote réel ou déploiement production ; aucune nouvelle
charge500, dernier résultat rouge inchangé : **500 timeouts,262 écritures
indéterminées**. IAM/F07/F09 ouverts,10.7 partielle, aucun statut/F-lot clos.
Concurrences exactes offre/sélection et affectation/rattachement non qualifiées ;
aucun lot30 ou ultérieur qualifié. Import documentaire sans test/service/agent,
commit ou push.

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
  (`iam-role-authoring`, F02/F03/F05). L'API possède des groupes Django et
  un catalogue de permissions ; une console de création, édition et
  affectation des groupes existe, avec copie en brouillon éditable ajoutée
  par `63949d1` (16 tests UI, dont 4 nouveaux). Elle ne copie pas les membres
  et ne modifie pas le groupe source. `2ade295` ajoute l'ajout/retrait transactionnel et
  audité de 1 à 100 comptes dans les deux SIS, avec UI batch et refus des
  scopes même vides ; tests API/UI ciblés qualifiés. `c8e2348` ajoute
  **un parcours navigateur réel par SIS** : création, copie sans membres,
  lots ajout/retrait, cible invalide 404 sans écriture partielle et apprenant
  authentifié refusé 403. Multi-tenant, parents/enseignants, MFA/SoD et
  versionnement non exhaustifs ; **IAM reste en cours**.
  `5a90d45`/`e495418` ajoutent l'audit transactionnel du cycle de vie **API**
  et son historique filtré/paginé, avec contrôle d'accès, snapshots et
  différentiel ; le navigateur vérifie trois événements du groupe source
  et le refus apprenant. L'historique persiste après suppression API ; la
  console ne propose pas de suppression. `9f432e3` ajoute la désactivation
  réversible API/UI, sans retrait des membres/permissions, audit avant/après
  et PATCH des seuls champs modifiés. Image finale `12bd…` : intégrales
  814/496 et 818/430 vertes, 31 tests UI et deux parcours navigateur par SIS, dont
  session déjà ouverte passant 200→404→200 avec retrait/rétablissement de
  permission et nom du groupe. Warning `guardian.W001` documenté, anciennes
  sessions à reconnecter, caches par instance et migration de tous les
  schémas avant trafic ; pas d'audit ORM/Django admin universel ni de
  versionnement optimiste complet ; la qualification projets25 est distincte.
  **Les groupes ne sont pas des rôles métier** :
  le formulaire utilisateurs conserve ses rôles fixes.
  **Reste :** le cycle complet de rôle métier permettant à l'admin *habilité* d'un établissement
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

### Exigences encore absentes ou non vérifiées (21 sur 94) et domaines devenus partiels

Le reste des 94 exigences est **partiel**, sauf 1.2 déjà vérifiée. Leurs
conditions propres (deux ou trois contrôles par exigence) sont conservées dans
`requirements[].acceptance_checks` de la
[matrice](functional-acceptance-matrix.json) ; le lot F correspondant
ci-dessus ne remplace jamais leur validation individuelle. Les lacunes les
plus nettes sont détaillées ici, avec les identifiants **du cahier initial**
(indépendants des sections 1–10 du cahier complémentaire ci-dessous).
Le tableau conserve aussi 10.5 et 10.7, désormais partielles, pour suivre
leurs limites ; elles ne sont pas comprises dans les 21 absentes/non vérifiées.

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
| 10.5 Projets — partiels | Créer des projets individuels/collectifs avec équipes, jalons, livrables et évaluations du groupe/contributions ; refuser à une autre équipe la lecture **et** la modification des livrables privés. Acquis25–28 conservés, objectifs facultatifs/snapshots privés sans acquisition induite. `0bb4766` qualifie désormais le cycle INDIVIDUEL complet : équipes d'un membre, jalon, deux PDF privés/SHA, gestionnaire et évaluateur non staff distincts, brouillon confidentiel/publication humaine/contribution propre, GET/POST autre équipe404. Collectif et cours réellement rejoués29, trois cas par SIS, six reçus HTTP après recréation. Plus de lacune fonctionnelle identifiée sur ces parcours ; restent les conditions de la règle commune préexistante (`b898347:1517–1528`) : deux établissements effectivement peuplés, restauration isolée base/fichiers, comparaison comptes/MFA/droits/données. Objet établissement sans schéma ≠ deuxième établissement peuplé ; recréation API sur volume conservé ≠ restauration de sauvegarde. Acquisition/notes officielles/LMS distant ne sont pas de nouvelles obligations10.5. Concurrences exactes offre/sélection et affectation/rattachement non qualifiées, pas de jeton client de révision d'offre. Statut partiel inchangé, aucun lot30 qualifié. |
| 10.7 Recherche globale — partielle | Preuves de recherche au cutoff vague 18 : apprenants, factures, vrais cours et évaluations SIS reliées au LMS dans les deux SIS, documents sources universitaires et bulletins scolaires `BUL-<id>` ; palette/fiches sans cache partagé, parcours staff et apprenant qualifiés sur fixtures, facture d'autrui absente de la recherche et détail 404 sans numéro. Restent catalogue LMS natif exhaustif et parcours parents/enseignants/multi-tenant/révocations exhaustifs ; la garde Studio ciblée de vague 19 ne clôt pas la recherche, aucun statut promu. |
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
