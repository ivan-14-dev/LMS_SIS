# Plan directeur : de LMS_SIS à la plateforme éducative cible

Date du bilan : **2 novembre 2026**. Référence du code examiné : **`b9ad1b9`**.
Actualisation : **3 novembre 2026**, code local compris. Le calendrier P0–P8
de la section 6 reprend la nouvelle feuille de route ; les identifiants
P0–P6 des anciens détails restent historiques et leur correspondance est donnée.

**TODO actualisée le 4 novembre 2026 :**
la [section 13](#13-todo-fonctionnelle-de-bout-en-bout) définit les travaux
restants, leurs dépendances et critères de sortie après les livraisons edX/MUI 7.
Elle fait référence pour le prochain ordre d'exécution ; les anciens calendriers
et inventaires ne doivent pas faire remettre à zéro les incréments déjà livrés.

Ce plan répond aux deux documents fournis par le demandeur, qui sont identiques.
Ils définissent 20 domaines fonctionnels, huit familles d'établissements et sept
piliers : SIS, LMS, ERP, IA, certifications, intégrations, gouvernance.
Ce document est un planning proposé, pas l'annonce de fonctionnalités déjà livrées.

### Priorité active : cahier fonctionnel universel — 4 novembre 2026

Le cahier fonctionnel fourni devient la référence des prochains incréments.
**Le design ERP livré est figé** : conserver le plein écran, la navigation,
les rubriques, tableaux, formulaires, couleurs et composants actuels. Les travaux
suivants ajoutent ou raccordent des fonctions métier dans ce cadre, sans nouvelle
refonte graphique. Cette instruction remplace les anciennes orientations
edX/benchmark du document lorsqu'elles concernent la présentation.

La correspondance ci-dessous conserve les lots existants plutôt que créer un
second backlog. Les fonctions partielles ou absentes restent à réaliser :
un écran, un profil configurable ou une API isolée ne valent pas livraison.

| Chapitre du cahier | Lots de réalisation |
|---|---|
| 1. Établissements, organisation, périodes et habilitations | F02, F04, F12, F14, F28 |
| 2. Candidatures, inscriptions, dossiers, parcours et familles | F11–F14, F17, F20 |
| 3. Cours, contenus, activités, résultats et compétences | F06–F10, F13, F25 |
| 4. Facturation, paiements, RH, achats et ressources | F15, F16, F19, F20 |
| 5. IA, tutorat, correction supervisée, OCR et analytics | F05, F23, F25, F26 |
| 6. Diplômes, certificats, badges, portefeuille et alumni | F22, F24 |
| 7. API, imports/exports, extensions, notifications et standards | F03, F04, F17, F23, F24 |
| 8. Accès, protection, audit, exploitation, licences et pilotage | F02, F05, F23, F28–F32 |
| 9. Portails adaptés aux rôles | F10, F17, F19, F20, F27, sans modifier la charte |
| 10. Mobile, hors ligne, stages, recherche et fonctions avancées | F11, F18, F20, F22–F27 |
| 11. Cycle complet candidature → alumni | Recette transversale F30, puis acceptation F32 |

Premier parcours repris : identité et inscription SIS → accès limité au vrai
LMS → enseignant affecté au cours → publication explicite → activité et
correction → résultat officiel validé. Les chantiers backend suspendus pendant
la refonte doivent être terminés et qualifiés avant toute nouvelle livraison.
Les prestataires de paiement/IA/messagerie, règles nationales, dispositifs
biométriques éventuels et engagements réglementaires ne sont pas inventés.

#### Boucle de réalisation et critères de preuve

Chaque exigence doit avoir une correspondance dans la matrice de recette :
comportements attendus, champs et validations, rôles autorisés/interdits,
parcours navigateur, endpoints, données persistées et résultat observé.
Les trois copies du cahier reçues sont identiques ; elles ne créent pas trois
backlogs. La présence de code ou d'un test non exécuté ne coche aucune exigence.

Le circuit de travail est : analyse du manque → implémentation sans changement
de design → tests ciblés → revue indépendante et cas négatifs → parcours réel
sur données synthétiques → sauvegarde et livraison → contrôle après redémarrage.
Un échec revient à l'implémentation ; une dépendance manquante reste explicitement
bloquée. Les agents d'analyse/documentation, sécurité, charge et réalisation
travaillent sur des périmètres séparés. Les résultats sont consolidés par lot,
sans assimiler un incrément validé à la clôture du lot F01–F32 entier.

La recette transversale doit couvrir les deux variantes, les rôles, les
frontières entre établissements, tous les formulaires/actions du périmètre et
les erreurs attendues. La couverture fonctionnelle (exigences exécutées),
la couverture du code mesurée et le taux de réussite sont trois indicateurs
distincts. Une couverture de 100 % ne garantit pas l'absence de toute faille
ou défaillance : les limites et exclusions doivent être visibles.

La charge demandée est de **500 sessions authentifiées concurrentes**, avec
identités synthétiques distinctes et scénarios métier, sur une installation
isolée explicitement autorisée. Enregistrer concurrence réellement atteinte,
durée, débit, erreurs, latences et intégrité des données après le test.
Ne pas assimiler 500 requêtes successives, des pages publiques ou 500 utilisateurs
configurés mais non connectés à cette cible. Les parcours navigateur complets
complètent cette charge HTTP ; ils ne sont pas remplacés par celle-ci.

La sortie globale reste conditionnée à la matrice entièrement vérifiée,
aux régressions et revues résolues, à la charge exécutée avec succès et au
déploiement local persistant utilisable. Les identifiants externes absents sont
signalés séparément ; aucune intégration simulée n'est annoncée opérationnelle.

### Actualisation UX : accueil ERP commun — 4 novembre 2026

La référence visuelle ERP fournie remplace la charte edX pour l'interface SIS :
cadre clair arrondi sur fond lavande, navigation compacte à sélection sombre,
recherche centrale, cartes arrondies et accents pastel. Les tokens partagés
harmonisent les pages MUI 7 et Paragon, y compris les tableaux, formulaires,
portails et écrans d'administration, en modes clair et sombre.

L'administration, les enseignants, les apprenants et les familles partagent
désormais la même composition d'accueil. Seuls les modules, données et actions
autorisés changent. Les portails détaillés restent accessibles depuis les cartes
et la navigation ; un apprenant conserve également ses accès supplémentaires
attribués par permissions, sans recevoir de nouveaux privilèges.
Les compteurs et notifications proviennent des API. Le calendrier permet de
parcourir les dates : il n'affiche pas d'événements scolaires fictifs et ne
constitue pas encore un agenda métier consolidé.

Le header SIS remplace aussi le double en-tête en mode SSO ; son menu de compte
conserve les cours LMS, le compte LMS et la déconnexion native.
La livraison est **frontend uniquement** : images `local-20261104-erp`
et `local-20261104-erp-sso`, cette dernière compilée séparément pour le pilote SSO.
Le backend livré reste `local-20261104-courses`. Les nouvelles inscriptions,
habilitations enseignantes et publications LMS bornées présentes dans le
chantier de code ne sont **pas livrées ni qualifiées** par cette refonte.

Les composants couvrent les différents rôles, les droits supplémentaires, les
erreurs, les favoris et les contrastes. La recette navigateur couvre les pages
de gestion des deux variantes, les thèmes persistés, la navigation au clavier
et les formats 1440, 1024, 390 et 320 px. Le scénario SSO réel conserve le dossier
apprenant, le cours et son résultat 1/1, puis vérifie la déconnexion.
Les comptes, secrets MFA, inscriptions, notes, offres et l'image backend
utilisateur sont préservés. La sauvegarde après livraison comprend 27 snapshots
contrôlés en lecture intégrale ; les deux SIS sont accessibles après sa reprise.
Les services de qualification ERP/SSO sont ensuite arrêtés sans supprimer leurs
données. Le lint ciblé est vert ; le lint global conserve des erreurs
préexistantes hors de ce lot.

#### Affinage de la référence et plein écran

La livraison suivante conserve le plein écran, sans marge extérieure ni plafond
de largeur. Les surfaces reprennent les couleurs relevées dans la référence :
fond `#F7F6F9`, panneaux `#F9F9FB`, contours blancs de 4 px et rayons de 24 px.
Les dégradés lavande, rose et jaune, le relief des boutons sombres, les icônes
contour et la typographie compacte sont partagés entre les pages. Les cartes de
modules et le calendrier s'alignent ; les contenus restent réels et autorisés.

Les champs, tableaux, dialogues, menus MUI 7 et composants Paragon suivent cette
charte, avec conservation du focus clavier et des états d'erreur/désactivation.
Les selects HTML utilisent le sélecteur personnalisable lorsque le navigateur
supporte `appearance: base-select` ; sinon, leur liste système reste utilisable.
Les deux flèches superposées issues du CSS directionnel ont été corrigées.
Les contrastes couvrent également les extrémités des dégradés.

Images frontend : `local-20261104-erp-reference` pour l'installation locale,
`local-20261104-erp-sso-reference` pour le pilote SSO. Le backend reste
`local-20261104-courses`. La recette couvre les pages de gestion des deux SIS,
les menus ouverts, leur usage au clavier, les thèmes et les largeurs de 320 à
2560 px. Le parcours SSO conserve le dossier, le résultat LMS 1/1 et le logout.
Les pilotes sont arrêtés après qualification, sans suppression des volumes.

#### Rubriques et tableaux épurés

Les espaces regroupant plusieurs ressources proposent des cartes d'accès :
une rubrique sélectionnée n'affiche que son contenu. Le paramètre `rubrique`
conserve le contexte SIS, les liens directs et le retour navigateur. Le centre
workflow distingue notifications, historique, livraisons et statistiques.
Les portails administratifs séparent également leurs différentes vues.

Les listes de classes, signatures, missions et réclamations laissent place au
détail choisi, avec retour explicite. Les formations se parcourent par maquette,
puis UE, puis ECUE ; les historiques disposent de leur propre onglet.
Les tableaux partagent leurs en-têtes lavande, lignes alternées et contours.
Les badges utilisent des couleurs sémantiques contrastées en clair et sombre,
conservent les libellés métier et rendent les statuts inconnus en neutre.
Les statuts calculés, notamment les diplômes signés/préparés, sont préservés.

La recette couvre les rubriques des deux SIS à 1440, 390 et 320 px, les détails
réels sur données synthétiques isolées, la création d'ECUE, les missions des
apprenants et les réclamations privées. Les accès autorisés, formulaires,
exports et actualisation des dossiers restent disponibles.
Images frontend : `local-20261104-erp-tables` et
`local-20261104-erp-sso-tables`. Le backend reste `local-20261104-courses` ;
aucune migration ni mise à jour des comptes/MFA n'accompagne ce lot.

### Incréments réalisés : configuration et raccordement des offres

Le socle dispose maintenant d'un catalogue partagé de profils versionnés,
d'offres combinables dans un tenant, de calendriers et libellés personnalisables,
de trois modes d'évaluation, de crédits facultatifs et d'une simulation serveur.
L'onglet **Profils et offres** permet de les modifier et enregistrer sans écrire
du JSON. Primaire, secondaire, supérieur et formation professionnelle peuvent
coexister ; un profil personnalisé complète ces modèles.

Les offres sont désormais sélectionnables sur les classes/formations.
Les nouvelles inscriptions et évaluations conservent une copie de leurs règles ;
les anciennes données ne sont pas converties rétroactivement. Le contrôle
continu enregistre notes, compétences et décisions simples, sans convertir
les résultats non chiffrés en notes et sans attribuer automatiquement de crédits.

**Cela ne termine pas P1 et ne rend pas encore le système universel en production.**
Les deux variantes techniques restent en place. Les parcours sans classe/UE,
transferts historisés, agrégation des compétences, examens/jurys, publication
des résultats et attribution des crédits doivent encore être généralisés.
Voir le [périmètre et les commandes API](INSTALLATION_ETABLISSEMENT.md#profils-institutionnels-et-offres-mixtes).

### Premier incrément UX-01 : espaces SIS raccordés

La chaîne React active partage maintenant une charte claire, une navigation
filtrée par capacités/rôles, une recherche de modules autorisés, un menu
rétractable et un tiroir mobile. La barre supérieure affiche l'établissement,
le contexte secondaire/supérieur, le compte et les notifications. Le contexte
des écrans d'administration reste explicite lors du changement de variante.

L'accueil de gestion propose des accès métier et des compteurs réellement
chargés depuis les listes paginées ; les statistiques et années fictives ont
été supprimées. Les apprenants/familles et enseignants accèdent directement
aux portails existants. Les erreurs de chargement des capacités, du dossier,
des compteurs et des notifications ne sont plus présentées comme des résultats
vides réussis.

La recette dual isolée couvre les parcours de gestion existants, le menu
ordinateur/mobile, sa fermeture au clavier avec retour du focus, et de vraies
connexions élève/étudiant dans des sessions distinctes. Des captures des deux
variantes sont produites. Les branches parent et enseignant sont couvertes par
les tests de composants ; leur recette complète avec données métier reste à
étendre.

Le socle d'apparence utilise désormais les mêmes tokens pour MUI et SCSS,
avec la police Inter auto-hébergée, un thème clair/sombre et la marque réelle
de l'établissement. Les préférences et favoris sont locaux, isolés par compte,
établissement et API ; ils ne changent aucun droit. La palette Ctrl+K / ⌘K
ne recherche que les modules autorisés. Le catalogue installé distingue
activation effective, modification non publiée, dépendances, permissions et
conséquences d'une désactivation.

**UX-01 reste partiel :** espace plateforme multi-établissements,
affiliations multiples, vues enregistrées et actions groupées autorisées,
recherche globale, traduction, catalogue Storybook, TypeScript progressif,
qualification WCAG complète et parcours pédagogiques intégrés restent à réaliser.
EXP-01, REC-01 et SIG-01 disposent désormais des premiers parcours décrits ci-dessous.
Aucun bouton factice ne présente les fonctions
restantes comme disponibles. Ces incréments n'actualisent pas automatiquement
une installation locale déjà conservée.

### Premier incrément EXP-01 : documents personnels autorisés

**Mes documents** réutilise les dossiers et documents existants : bulletins
publiés pour les élèves et les enfants autorisés au secondaire ; relevés,
transcripts et attestations validés pour les étudiants/doctorants au supérieur.
Les brouillons et les documents d'autrui restent exclus, y compris lors d'un
accès direct par identifiant. Les gestionnaires conservent les listes de travail
et leur historique, dans leurs périmètres autorisés.

Les téléchargements PDF passent par le client authentifié et les contrôles
serveur, sans URL publique ; ils sont tracés et leurs réponses interdisent la
mise en cache. La recherche et la pagination sont effectuées côté serveur.
L'export CSV reprend toutes les pages de la liste filtrée autorisée, et non
seulement les lignes affichées. Les erreurs restent visibles.

**EXP-01 reste partiel :** les PDF ordinaires restent des synthèses régénérées,
pas un calcul exhaustif de toutes les UE. Les versions explicitement signées
disposent désormais de l'archivage décrit ci-dessous. Les diplômes ne sont pas
encore raccordés à cet espace. Filtres structurés année/période, exports
personnels XLSX/JSON et traitement asynchrone des gros exports restent à réaliser.
Le CSV est produit dans le navigateur ;
son téléchargement n'ajoute pas d'événement d'audit métier. La validation
administrative existante n'est pas présentée comme une signature numérique.

### Incrément SIG-01, missions et disposition des espaces

Après retour utilisateur, les présentations Pinterest/iSpring puis Quizlet sont
remplacées par la charte edX/Paragon : navigation claire limitée à sept espaces
de gestion, onglets contextuels, titres hiérarchisés, tableaux avec barre
d'actions intégrée et absence de cadres imbriqués. Le portail apprenant adopte
la même charte avec cinq entrées au maximum. Les favoris restent sur l'accueil
et dans la palette, plutôt que d'allonger le menu. Inter est auto-hébergée.
L'en-tête traverse toute la page ; les dossiers apprenants utilisent des onglets
pleine largeur. Les thèmes, le logo institutionnel, les URL et le tiroir mobile
sont conservés. La couleur institutionnelle identifie le monogramme sans
remplacer les couleurs communes des actions. Aucun logo edX n'est incorporé.

Les dashboards actifs des deux variantes utilisent maintenant MUI 7, y compris
les portails élèves, familles, étudiants, doctorants et staff, leurs cartes,
notifications et navigation. Les grilles utilisent l'API `size` de MUI 7.
Les données, erreurs, liens métier et contrôles d'accès sont conservés ; aucune
statistique fictive de l'ancien `ModernDashboard` n'est réintroduite. Paragon
reste utilisé dans certaines pages hors dashboards, avec les mêmes tokens edX.

Les missions donnent aux apprenants des accès de consultation explicites,
datés et révocables à des résumés de dossiers sélectionnés, sans modifier
leur rôle. Les droits et périmètres du responsable sont revérifiés lors
des consultations. Ce n'est pas une délégation universelle de tous les métiers.

SIG-01 couvre maintenant demande personnelle, approbation indépendante,
suspension/révocation, mandats bornés et appositions Ed25519 avec notification
interne obligatoire au titulaire. Les versions PDF, manifestes, preuves et
révocations sont conservés en base et protégés contre UPDATE/DELETE. Le
bénéficiaire peut télécharger et vérifier une version archivée ; les usages
et décisions possèdent des historiques privés.

**SIG-01 reste partiel :** preuve institutionnelle détachée, sans signature
qualifiée, certificat externe, PAdES, horodatage tiers ou stockage WORM garanti
contre l'administrateur d'infrastructure. La confiance hors ligne exige une
empreinte de clé institutionnelle obtenue indépendamment du document.

Les admissions utilisent désormais des décisions contrôlées et une réinscription
vers une année postérieure ouverte, y compris depuis une année clôturée.
Cette transition conserve dossiers, résultats et règles antérieurs et crée une
nouvelle demande à valider. Les équivalences dans la même année, la sélection
de candidats sans dossier et les transferts inter-établissements restent hors
de cet incrément ; aucune conversion d'acquis n'est implicite.

### Incrément F02/F03 : synchronisation et module de missions

La création d'utilisateurs dans les deux connecteurs respecte désormais le
contrat `full_name` du client Open edX. Les comptes privilégiés du SIS ne sont
plus automatiquement créés comme administrateurs globaux du LMS : les droits
pédagogiques et les comptes d'exploitation doivent être attribués explicitement.
Ce correctif ne qualifie pas encore les API d'un vrai LMS ni le SSO.

Chaque compte possède maintenant un UUID d'intégration persistant. Les nouveaux
identifiants LMS sont opaques et ne dépendent plus des clés numériques locales,
qui peuvent se répéter entre établissements. Un rejeu ou un changement d'adresse
ne change pas cette identité ; les mappings LMS historiques restent inchangés.
La migration attribue une valeur distincte aux comptes existants sans changer
leurs mots de passe ni leur MFA. Le défaut PostgreSQL permet aussi aux anciens
binaires de créer un compte après un retour arrière applicatif.

Les clients demandent également une signature OAuth asymétrique, vérifiable
avec le seul JWKS public du LMS. La recette des deux API SIS avec un véritable
jeton Open edX confirme l'association au compte existant et le refus après
désactivation du compte ou du mapping. Les jetons LMS restreints ne donnent
pas accès au SIS. Le MFA local reste obligatoire lorsqu'il est activé :
un jeton LMS seul est refusé et la connexion locale reste nécessaire.
Cette qualification des jetons API ne vaut pas livraison du SSO navigateur
ni d'une fédération du second facteur.

Le catalogue passe de trois à quatre modules installés : **Missions et accès
délégués** est facultatif et activé par défaut, comme les réclamations. Sa
simulation et son changement de révision utilisent le circuit existant.
Sa désactivation bloque toutes ses API et retire ses entrées de navigation ;
les dossiers, rôles et historiques sont conservés. La réactivation ne contourne
ni expiration, ni révocation, ni perte d'habilitation du responsable.

Cet incrément est livré localement aux deux variantes avec conservation des
comptes, du MFA et des dossiers. **F02 et F03 restent partiels** : identité
canonique/fédération, affiliations et catalogue d'extensions externes ne sont
pas rendus complets par ces corrections.

### Incrément F06 : véritable LMS en qualification isolée

Open edX et Studio sont maintenant initialisés séparément avec Tutor 22.0.4.
La recette navigateur couvre deux comptes synthétiques, la création d'un cours,
la publication d'un quiz, une inscription apprenant et une correction à 1/1.
Le cours, l'inscription et la réponse corrigée persistent après redémarrage,
sans nouvelle soumission. Une sauvegarde froide chiffrée de la racine Tutor
a été contrôlée par lecture intégrale, puis restaurée dans un autre projet,
source arrêtée, avec relecture du résultat apprenant. Le Compose SIS reste distinct, avec ses
comptes, MFA et dossiers préservés ; son apparence edX/MUI 7 n'est pas remplacée.

**F06 reste partiel :** il s'agit d'une qualification locale, avec routage
Chromium dédié et thème LMS fourni par Tutor. Le raccordement complet SIS/LMS,
dont le SSO et le provisioning, reste ouvert ; le quiz non noté ne produit pas
de résultat académique officiel. Le contrat de provisioning des comptes du connecteur
diffère de celui de cette distribution : l'API comptes ne prend pas en charge
son `POST` de création. DNS/TLS institutionnels, copie hors machine, reprise
institutionnelle et capacité de production ne sont pas homologués.

### Incrément F07 : inscriptions compatibles avec le LMS réel

Les deux connecteurs utilisent maintenant le contrat natif d'Open edX :
inscription par objet `POST`, désinscription par `is_active=false` sans modifier
le mode, et liste des inscriptions d'un cours avec pagination. Ils vérifient
la confirmation reçue et refusent les liens de pagination hors du périmètre
autorisé avant de transmettre le jeton OAuth.

Les lots réutilisent le circuit unitaire : les succès précédant une panne
sont conservés, l'échec est enregistré dans l'outbox et le rejeu ne crée pas
de doublon. Le lot s'arrête à l'échec ; les éléments suivants ne sont pas
automatiquement mis en file.

La recette avec le vrai LMS couvre OAuth, inscription répétée, désinscription
répétée, réactivation et refus des opérations d'administration par l'apprenant.
Une base SIS jetable, pour chaque variante, vérifie aussi l'API administrateur,
le refus apprenant, une coupure réseau puis la reprise réelle de l'outbox,
sans doublon local ou LMS et sans inventer d'identifiant distant. Le cours et
la réponse corrigée à 1/1 ont été conservés.

**F07 reste partiel :** les comptes et le cours de cette recette sont
préexistants et explicitement associés. Le SSO, le provisioning des comptes,
les cours/enseignants et les transitions institutionnelles de suspension ou
de départ ne sont pas livrés par ce seul correctif de connecteur. Les secrets
de qualification ne sont pas activés dans l'installation SIS utilisateur.

### Incrément F07 : parcours navigateur SSO en pilote secondaire

Un SIS isolé avec données synthétiques est raccordé aux cookies JWT du vrai LMS.
Le plugin Tutor `sis_sso` autorise uniquement les origines déclarées pour les
redirections, CORS et CSRF, sans élargir le domaine des cookies. Sa configuration
est facultative ; la procédure d'installation et de restauration figure dans
le guide établissement.

Le navigateur effectue une connexion LMS depuis le SIS, affiche le dossier
élève, ouvre son cours sans seconde connexion et retrouve la réponse corrigée
à 1/1. Le retour au SIS puis la déconnexion effacent les cookies JWT ; revenir
au dossier exige une nouvelle connexion. Cette recette a également révélé et
fait corriger les références à un champ de niveau inexistant dans les trois
portails secondaire. Les builds frontend n'injectent plus New Relic sans
configuration. Ces correctifs sont livrés aux deux SIS locaux, avec comptes,
MFA, inscriptions, notes et règles conservés, sans bascule en mode SSO.

**F02/F06/F07 restent partiels :** ce pilote ne qualifie ni le navigateur
supérieur, ni les autres rôles, ni le DNS/TLS institutionnel, ni la fédération
MFA. L'erreur native de déconnexion du LMS 22.0.4 dans `jquery.allLoaded`
a depuis été corrigée par un patch de construction avec régénération des
assets. La recette complète réussit dans l'image reconstruite sans exception
JavaScript tolérée, avec redirection finale, cookies effacés et reconnexion
obligatoire. Le provisioning des comptes et des cours est décrit dans les
incréments suivants ; les équipes enseignantes et transitions de suspension
ou de départ restent à implémenter et qualifier.

### Incrément F07 : provisioning réel et reprise sans doublon

Les deux clients utilisent maintenant une extension Django Open edX dédiée,
installée dans une image dérivée de la distribution officielle. Un registre
associe les comptes provisionnés à leur service technique propriétaire ;
aucun rattachement automatique par email ou nom n'est effectué.
L'autorisation repose sur une permission dédiée et un JWT explicite :
les comptes ordinaires, jetons restreints et services révoqués sont refusés.
Le provisioning n'attribue aucun privilège global aux utilisateurs SIS.

Le parcours réel des deux SIS couvre création, modification du profil,
perte de réponse après création effective et reprise outbox conservant le
même compte LMS. L'identité distante est contrôlée avant la mise à jour.
Les mots de passe et le MFA SIS restent inchangés. Une synchronisation relit
et verrouille le compte et son association ; elle ne réactive pas un compte
SIS désactivé ou une association révoquée.

L'extension propose également une commande opérateur de rattachement explicite
des comptes historiques non privilégiés. Les nouveaux comptes doivent définir
leur mot de passe par la récupération native du LMS ; aucun secret initial
n'est partagé avec le SIS. Un lien de récupération destiné au bon compte a
été qualifié sans envoi à un fournisseur externe.

**F07 demeure ouvert :** ce contrat des comptes ne gère pas les équipes
ou les affiliations. Il ne constitue pas encore une orchestration automatique
de tous les changements du cycle de vie institutionnel. SMTP institutionnel,
fédération MFA et autres parcours SSO restent à qualifier.
L'installation de l'extension et l'attribution
de la permission sont explicites, pas une promotion automatique des comptes.

### Incrément F07 : cours Studio, identités et reprise native

Les deux SIS créent, relisent et renomment désormais des cours via une
extension CMS explicite, et non les anciennes routes fictives. Les cours ont
un service propriétaire ; aucun cours préexistant n'est adopté par collision
de nom. Les nouveaux identifiants proviennent d'UUID durables des matières,
classes et ECUE ; les associations historiques restent inchangées. Les
migrations conservent les données et permettent encore les insertions par
l'ancien binaire. Les reprises ne réactivent pas une association révoquée et
les demandes anciennes ne remplacent pas les modifications récentes réussies.

La recette réelle de chaque SIS couvre création, perte de réponse, modification
du code source local, reprise outbox sans doublon, renommages répétés et refus
apprenant. L'extension respecte la politique de création Studio et n'attribue
au service que les droits natifs du cours créé, sans privilège global.
Les nouveaux cours restent vides et hors catalogue.

Une panne interne après création MongoDB a révélé la nécessité de conserver
l'index SQL en autocommit. Une intention persistante et un verrou nommé MySQL
protègent maintenant la reprise des initialisations natives. Le rattachement
opérateur des cours historiques exige un accès d'auteur préexistant et
préserve contenus, réponses, notes et équipe. Le cours de qualification a
effectivement suivi ce parcours.

**F07 reste partiel :** attribution automatique des enseignants, contenus et
publication, règles d'inscription, affiliations et orchestration des
suspensions/départs restent ouverts. Les droits du provisioning ne remplacent
pas la qualification des autres API natives, notamment les inscriptions.
Le guide établissement décrit les permissions, la reconstruction de l'image
et les commandes explicites de rattachement.

La livraison `local-20261104-courses` est active et persistée sur les deux SIS
et le LMS de qualification. Les sauvegardes chiffrées ont été relues
intégralement ; celle de Tutor comprend le contexte de construction et les
identités d'images. Le pilote SSO a reçu ses migrations et le parcours
dossier/cours/déconnexion a réussi après redémarrage à froid, avec la réponse
et le score 1/1 préservés sans nouvelle soumission.

**Points ouverts de qualification :** un HTTP 404 de rendu d'exercice a été
observé lors du premier passage puis n'a pas été reproduit, y compris après
redémarrage complet. Sa cause n'est pas établie : il reste à surveiller avant
homologation, et n'est pas présenté comme un correctif livré. Par ailleurs,
l'API native refuse effectivement l'inscription d'autrui par le service
non-staff, même propriétaire du cours et du compte. Le contrôle OAuth réel
confirme HTTP 404 sans mutation, contre HTTP 200 pour la lecture Studio.
L'étape suivante exige un contrat d'inscription à droits limités et une
orchestration des révocations, pas une promotion globale du service.

### Premier incrément REC-01 : réclamations privées

Les variantes secondaire et supérieur partagent maintenant le dépôt personnel,
un numéro de suivi, les échanges, les justificatifs PDF privés, l'affectation
à un agent explicitement habilité, la demande de complément, la décision
motivée, la clôture et le recours avec réouverture. Le menu et les actions
suivent les habilitations ; les notifications internes renvoient au dossier.

L'apprenant ne voit que ses demandes ; l'agent de traitement ne voit que ses
affectations ; le coordinateur habilité reçoit et affecte celles de son
établissement. Le rôle enseignant ou le seul indicateur `is_staff` n'ouvrent
pas l'API des réclamations. Les détails et pièces ne sont pas publiés dans
l'audit global. Toute modification et ses notifications sont enregistrées
ensemble ; une version périmée est refusée plutôt que d'écraser un échange.
Aucune note, inscription ou facture n'est automatiquement rectifiée.

**REC-01 reste à compléter :** délais et relances configurables, services
organisationnels, politique institutionnelle des recours, délégations
parentales, analyse antivirus et conservation/purge des justificatifs.
Le premier parcours accepte jusqu'à dix PDF de 25 Mo et conserve l'historique ;
il ne prétend pas résoudre ces exigences de production.
Voir le [mode d'emploi et les droits](INSTALLATION_ETABLISSEMENT.md#réclamations-privées-des-apprenants).

### Corrections académiques et premier contrat de modules

Les résultats sont protégés contre les suppressions en cascade et les
publications par simple modification de statut. Les gardes de clôture couvrent
les parents d'origine/destination ; les transferts simples sont motivés,
atomiques et audités. Les dossiers avec acquis, choix pédagogiques ou règles
historisées restent soumis à un futur circuit d'équivalences. Examens,
maquettes/UE/ECUE et emploi du temps supérieur disposent maintenant de
formulaires raccordés ; le journal filtre réellement par acteur et dates.

Le premier incrément **EXT-01** utilise un registre partagé de modules
préinstallés, avec identifiant, éditeur, version, contrat, variantes,
dépendances, permissions, points API/UI/événements et conservation des données.
Identité et notifications sont obligatoires ; les réclamations constituent
le premier module facultatif. Leur activation par établissement possède une
simulation, une révision, un motif et un historique atomique. La désactivation
est appliquée par le serveur et la navigation, sans supprimer les dossiers.

Ce catalogue ne représente pas encore tous les modules du SIS. Il ne permet
ni téléchargement de packages, ni exécution de code tiers, ni installation
à chaud. L'héritage pays/organisation/campus, les dates d'effet, l'outbox
générique et deux extensions externes de référence restent à construire.
Les six anciennes options pédagogiques ne deviennent pas des plugins.

## 1. Conclusion et hypothèses de travail

**Nous ne repartons pas de zéro.** Le dépôt possède un socle SIS exploitable en
pilote local, du code Open edX, de nombreux modèles/API métier et plusieurs
parcours complets. Il ne constitue pas encore le produit universel décrit.

Le principal travail est de terminer et relier les parcours, de généraliser la
configuration, puis d'ajouter les domaines encore absents. Avoir un modèle Django,
une route API ou un bouton ne signifie pas qu'un utilisateur peut terminer une
opération.

Hypothèses retenues pour ce planning :

- Conserver Django/Python et React ; utiliser Open edX pour le moteur pédagogique.
  Java/Spring Boot, cité comme technologie possible dans le document cible,
  n'est pas interprété comme une obligation de réécriture.
- Commencer par un établissement secondaire et un établissement supérieur pilotes,
  dans un premier cadre réglementaire choisi avec leurs responsables. Ces pilotes
  ne limitent pas le modèle : confronter le noyau dès P1 au primaire, au secondaire,
  au supérieur et à la formation professionnelle.
- Construire des modules et profils configurables, pas huit applications séparées.
- Privilégier un monolithe métier modulaire et des services externes spécialisés.
  Ne pas imposer Kafka, Kubernetes ou des microservices sans besoin mesuré.
- Réutiliser ou intégrer les moteurs spécialisés : LMS, visioconférence,
  paiement, comptabilité, paie et signature électronique.
- Ne pas promettre une capacité « illimitée » : fixer et mesurer effectifs,
  nombre de tenants, simultanéité, stockage et objectifs de disponibilité.
- Aucun déploiement public, migration technologique, achat de service ou
  développement fonctionnel n'est déclenché par la rédaction de ce plan.

Si Java/Spring Boot devient une contrainte ferme, ajouter avant développement
une décision d'architecture et un chiffrage de migration. Les estimations
ci-dessous ne couvrent pas la réécriture des deux SIS ni celle d'Open edX.

### Exigence centrale : un système adaptable à tout type d'établissement

L'objectif confirmé est **une plateforme commune que chaque établissement
configure**, et non un produit limité à deux catégories ni une application
spécifique pour chaque client. Les modes `secondaire` et `superieur` décrivent
l'existant technique ; ils ne doivent pas devenir une limite du futur produit.

Le parcours d'ouverture cible est : créer l'organisation, choisir ou composer
un profil, activer les modules nécessaires, définir les règles et rôles, importer
les données, puis commencer à travailler. Un assistant guide l'administrateur
sans lui demander de modifier le code ou les fichiers de configuration courants.

| À rendre configurable | Exemples de variations à supporter |
|---|---|
| Organisation | École indépendante, réseau, campus, faculté, département ou centre ; ne pas imposer une hiérarchie universitaire à une petite école. |
| Personnes et affiliations | Élève, étudiant, stagiaire, salarié, enseignant, formateur, parent ; une personne peut avoir plusieurs rôles autorisés. |
| Organisation des apprentissages | Classe annuelle, groupe, promotion, formation, atelier ou session courte ; semestres et UE ne sont pas obligatoires partout. |
| Calendriers | Année/trimestre/semestre, session de quelques jours, inscriptions continues et parcours à rythme libre. |
| Évaluation | Notes sur des barèmes différents, coefficients, acquis/non acquis, compétences, crédits facultatifs et certification. |
| Modules | Un établissement peut n'utiliser que cours/présences ; un autre ajoute finance, internat, recherche ou services scolaires. |
| Dossiers et processus | Champs typés, pièces, formulaires, validations, délégations et documents selon le profil. |
| Contexte local | Langue, fuseau, devise, libellés, documents et règles réglementaires qualifiées. |

**Critère de conception P1 :** quatre configurations contrastées doivent être
représentables par le même noyau, sans branche de code par établissement :
une école primaire sans crédits, un lycée avec coefficients, une université
avec UE/crédits et un centre professionnel évaluant des compétences sur des
sessions courtes. Tester aussi qu'un même établissement peut combiner plusieurs
offres, par exemple diplômes universitaires et formation continue.

Cette recette valide la flexibilité du socle, pas l'achèvement de tous les
modules propres à ces établissements. Les profils livrés et leurs limites
doivent être visibles ; une option non prise en charge ne doit pas être
présentée comme disponible.

La configuration assemble les capacités déjà implémentées. Une nouvelle
fonction métier peut nécessiter un module partagé supplémentaire, mais pas un
fork par client. De même, « tout établissement » ne signifie pas conformité
automatique à toutes les législations : les adaptations pays sont qualifiées
progressivement.

## 2. Comment lire l'état d'avancement

| État | Signification |
|---|---|
| **Livré localement** | Parcours ciblé exercé dans l'installation locale ; périmètre précisé. |
| **Partiel** | Modèles, API, interface ou règles présents, mais couverture fonctionnelle ou qualification incomplète. |
| **Externe** | Fonction à fournir par Open edX ou un autre service, non qualifiée dans l'installation SIS actuelle. |
| **À construire** | Pas de parcours intégré identifié répondant à cette exigence dans le périmètre SIS examiné. |

« Partiel » ne signifie pas « inutilisable », et « à construire » n'exclut pas
la réutilisation d'une bibliothèque ou d'un module existant. Ce bilan n'est pas
une certification exhaustive de chaque API. Les fonctions hors des parcours
déjà exercés devront passer une recette métier.

Les anciennes cases de `TODO_PRODUIT.md` et certaines affirmations du README
ne constituent pas un état à jour. Par exemple, le déploiement Docker et les
parcours navigateur existent désormais, tandis que certaines promesses de
conformité ou de multilinguisme restent à démontrer.

### Acquis à conserver

| Acquis | Périmètre réellement disponible |
|---|---|
| Installation et exploitation | Compose secondaire, supérieur ou dual ; initialisation répétable ; configuration privée ; stockage persistant ; contrôles de disponibilité. |
| Identité locale | Comptes, sessions, CSRF, MFA TOTP et récupération de compte ; une configuration de messagerie réelle reste nécessaire pour l'usage des emails. |
| Base institutionnelle | Établissements, années, périodes, structures ; paramétrage académique et activation de fonctionnalités. |
| Dossiers et inscriptions | Formulaires d'apprenants, imports CSV/XLSX avec prévisualisation, inscriptions supérieures ; pas encore un cycle complet d'admission. |
| Travail scolaire courant | Classes, personnel et créneaux secondaires, appels/présences ; saisie réelle d'évaluations et de notes dans les deux SIS. |
| Services secondaires | Formulaires reliés aux API pour clubs, cantine, transport, internat, discipline, conseils de classe et infirmerie. |
| Socle transversal | Permissions, attributs d'accès, événements workflow, notifications, exports et génération de PDF ; profondeur variable selon le module. |
| Livraison technique | CI et recettes locales ; sauvegarde/restauration chiffrée, redémarrage et persistance exercés. |

La recette locale ne valide ni une intégration LMS/SMTP réelle, ni une capacité
de production, ni l'ensemble des droits par rôle, ni la conformité réglementaire.

## 3. Matrice des 20 domaines

Les phases **P1 à P6 historiques** sont détaillées plus bas ; leur correspondance
avec le calendrier révisé P0–P8 figure en section 6. Un domaine peut traverser
plusieurs phases ; cela évite de considérer un module comme « terminé » après
la seule livraison de ses premières listes.

| # | Domaine et état | Déjà présent | Reste pour atteindre la cible | Phases |
|---|---|---|---|---|
| D01 | Établissements et organisations — **Partiel** | Tenants, années/périodes, structures, modules ; offres mixtes et snapshots ; unités campus/département/programme avec héritage d'offre, verrous, publications datées et simulation. | Gouvernance de réseaux multi-tenant, affiliations et autorisations par campus, provisioning, partenaires, déclinaisons pays et capacités mesurées. | P1, P6 |
| D02 | Apprenants — **Partiel** | Dossiers élèves/étudiants, matricules, liens familiaux, imports et inscriptions. | Identité pérenne inter-systèmes, cycle préinscription/réinscription/transfert/suspension/abandon, dossier documentaire complet, historique consolidé et Alumni. | P2, P5, P6 |
| D03 | Enseignants et personnel — **Partiel** | Comptes, dossiers et affectations ; création de personnel dans le parcours secondaire. | Recrutement, contrats, disponibilités et charges cohérentes, congés/remplacements, compétences, formation continue et évaluations professionnelles. | P2, P4 |
| D04 | Pédagogie et académique — **Partiel** | Classes/matières, formations, UE/ECUE, maquettes, crédits, prérequis et configuration de règles. | Parcours entièrement administrables, référentiels de compétences/objectifs, équivalences, règles locales versionnées et simulables, progression pédagogique reliée au LMS. | P1, P2, P3 |
| D05 | Cours et contenus LMS — **Externe / à intégrer** | Code Open edX dans le dépôt ; mappings et mécanismes d'intégration SIS. Le pack Compose ne déploie pas le LMS. | Distribution Open edX compatible, parcours Studio/apprenant unifié, cours multimédias, ressources interactives, forums, projets/équipes, parcours conditionnels, versions et bibliothèques partagées. | P3 |
| D06 | Évaluations et examens — **Partiel + externe** | Saisie d'évaluations et notes ; API de sessions, épreuves, convocations, résultats et correction anonymisée. | Relier création, soumission, correction, jury et publication ; devoirs/remises/rubriques ; banque de questions/QCM via LMS ; gestion des examens physiques/oraux/pratiques, PV, antivirus des dépôts. Surveillance distante seulement après choix juridique et pédagogique. | P2, P3, P5 |
| D07 | Notes et bulletins — **Partiel** | Saisie transactionnelle de notes/compétences/décisions simples en contrôle continu, règles historisées ; modèles/API de moyennes, bulletins, crédits et rattrapages ; PDF. | Qualifier coefficients, arrondis, absences, compensation, classement et passages ; agrégation des compétences, carnet enseignant, validations avant publication, réclamations étudiantes et rectifications tracées ; téléchargement des relevés et transcripts autorisés. | P2, P3, P5 |
| D08 | Emplois du temps — **Partiel** | Créneaux/salles, vues de consultation, contraintes et endpoint de détection de conflits ; création secondaire. | Achever les actions supérieures, tester tous les chevauchements, calendriers unifiés, événements, remplacements, planification hybride/multi-campus et affectation automatique. | P2, P4, P6 |
| D09 | Finance — **Partiel** | Frais, factures, paiements, bourses et workflows de validation/remboursement côté API ; interface de consultation. | Parcours de facturation/encaissement complet, réductions/échéanciers, paiements partiels, reçus, dettes, connecteurs bancaires/mobile money, rapprochement, multidevise, comptabilité/budget/dépenses et paie via ERP. | P4, P6 |
| D10 | Communication — **Partiel** | Notifications in-app, email, SMS et webhook ; préférences et suivi de livraison dans le socle. | Qualifier les fournisseurs réels ; messagerie et annonces, conversations autorisées, notifications push/temps réel, urgences, calendrier partagé, traduction assistée et politique de conservation. | P2, P3, P4, P6 |
| D11 | Parents et tuteurs — **Partiel** | Portail secondaire avec enfants autorisés, notes/absences et factures ; portail apprenant supérieur ; premiers parcours « Mes réclamations » et « Mes documents ». | Justificatifs et autorisations de sortie, devoirs, communication enseignants, paiement en ligne, consentements et délégations ; étendre les parcours personnels et l'accès parental selon les droits accordés. | P2, P3, P4 |
| D12 | Bibliothèque — **Partiel** | Modèles/API d'ouvrages, exemplaires, emprunts et réservations ; écran supérieur. | Interfaces complètes emprunt/retour/réservation, pénalités, fonds numérique, licences, accès documentaires scientifiques, archives et connecteurs spécialisés. | P4, P6 |
| D13 | Vie scolaire/universitaire — **Partiel** | Présences, discipline, clubs et conseils ; modèles/API et écrans pour stages, mémoires, soutenances, recherche et mobilité. | Finaliser les parcours de bout en bout, récompenses/sports/associations/événements, placement en stage, conventions, signatures, encadrement et publication des décisions. | P2, P4, P5 |
| D14 | Ressources et infrastructures — **Partiel** | Salles ; transport, cantine, internat et équipements décrits dans certaines données métier. | Capacités/réservations sans conflits, inventaire et maintenance, parc informatique/laboratoires, logements universitaires, coûts logistiques et contrôle d'accès via connecteurs. | P4, P6 |
| D15 | Admissions — **À construire comme parcours complet** | Les inscriptions et dossiers permettent de réutiliser les données de l'apprenant après admission. | Portail candidat, campagnes/formulaires, pièces, vérification, concours/tests, entretiens, classement, décisions, notifications et conversion en inscription sans double saisie. | P2 |
| D16 | Diplômes et certifications — **Partiel** | Diplômes, attestations/relevés, PDF, numéro de série, date/signataire et action de vérification. | Signatures administratives validées avant activation, délégations explicites et notification du titulaire à chaque utilisation ; signature cryptographique, registre vérifiable/révocable, vraie URL publique et QR, équivalences, Open Badges/CLR et portefeuille de compétences. | P1, P2, P5 |
| D17 | RH et gouvernance — **Partiel** | Personnel, rôles, groupes d'accès, validations et historique de certaines décisions. | Postes/organigrammes, processus RH, contrats et paie, conseils d'établissement, séparation des responsabilités et rapports de gouvernance ; intégrer un ERP plutôt que recréer la législation salariale. | P1, P4, P5 |
| D18 | Reporting et BI — **Partiel** | Tableaux de bord, statistiques et rapports configurables sur des jeux de données connus ; exports CSV/XLSX/PDF. | Centre d'export simple avec filtres, formats et téléchargement des données propres à l'étudiant ; définitions d'indicateurs fiables, constructeur de rapports utilisable, tableaux personnalisés, données financières consolidées, entrepôt analytique, comparaisons interétablissements autorisées et prédiction évaluée. | P2, P4, P5 |
| D19 | Sécurité et conformité — **Partiel, socle livré** | Authentification locale, fédération prévue, MFA TOTP, RBAC et ABAC léger, journaux, chiffrement de champs, sauvegardes/restauration. | Qualification complète des périmètres et relations, SoD, MFA imposé selon politique et secours, consentements, droits sur les données, rétention/purge, incidents, supervision réelle, audit indépendant et règles par pays. | Toutes |
| D20 | IA éducative — **À construire** | Aucun parcours intégré d'assistance IA SIS identifié dans le périmètre examiné. | Assistants par rôle, recherche documentaire, résumés/traduction, cours/QCM/devoirs assistés, aide à la correction, tutorat/recommandations, rapports et détection de difficultés ; contrôle humain, évaluation et confidentialité obligatoires. | P5, P6 |

### Exigences complémentaires prioritaires : réclamations, exports et signatures

Ces exigences complètent la cible à la demande du responsable produit.
**REC-01 et EXP-01 disposent de premiers parcours fonctionnels**, décrits en tête
de ce document ; leurs exigences avancées restent à terminer.
SIG-01 dispose également du premier circuit de signatures et d'archives décrit
en tête de ce document ; les garanties juridiques et intégrations avancées
restent à compléter.

#### REC-01 — Réclamations et revendications des apprenants

- Ajouter « Mes réclamations » au portail : contestation de note/résultat,
  inscription, frais ou autre demande administrative. Prévoir objet, motif,
  référence du dossier concerné et justificatifs soumis aux contrôles de fichiers.
- À l'envoi, délivrer un numéro de suivi et un accusé de réception. Afficher
  statut, échanges, pièces autorisées, décisions motivées et historique.
- Prévoir réception, affectation au service habilité, examen, demande de
  complément, réponse et clôture ; paramétrer délais, relances et possibilité
  de recours/réouverture selon l'établissement.
- Notifier les changements utiles à l'apprenant et au service chargé du dossier.
  Une réclamation n'est pas visible par les autres étudiants ni par tout le
  personnel. Les accès des parents/tuteurs restent soumis aux délégations.
- Une contestation ne modifie jamais automatiquement une note : la décision
  humaine déclenche, si nécessaire, le circuit autorisé de rectification,
  avec conservation du résultat initial et du motif.

**Recette :** un étudiant dépose une contestation et suit sa réponse ; un agent
habilité la traite ; un autre étudiant et un agent non habilité ne peuvent ni
la consulter, ni télécharger ses pièces, ni modifier sa décision.

#### EXP-01 — Exports simplifiés et espace « Mes documents »

- Centraliser relevés semestriels, transcripts pluriannuels, attestations et
  diplômes disponibles ; permettre le téléchargement PDF des versions
  officielles autorisées, sans intervention technique ni ressaisie.
- Distinguer clairement brouillon, document validé/publié, document signé et
  document remplacé/révoqué. Un export de notes n'est pas présenté comme un
  transcript officiel ; conserver les résultats non chiffrés et les vrais barèmes.
- Proposer des exports de données propres à l'étudiant en CSV/XLSX/JSON selon
  le jeu de données : inscriptions, notes et historique académique autorisé.
  Prévoir filtres par année/période et explication des colonnes.
- Pour les gestionnaires, proposer choix du périmètre, filtres, colonnes et
  formats ; traiter les exports volumineux en tâche de fond avec statut,
  notification de disponibilité et téléchargement privé à durée limitée.
- Appliquer les droits aux fichiers comme aux API, limiter les données aux
  champs nécessaires et tracer les exports. Aucun lien public vers un dossier
  étudiant, aucune exportation des secrets d'authentification ou de signature.

**Recette :** un étudiant obtient son transcript et ses données dans les formats
annoncés ; les filtres et résultats sont exacts ; changer un identifiant ou
réutiliser le lien d'un autre compte ne donne pas accès à ses documents.

#### SIG-01 — Signatures administratives approuvées et usages notifiés

- Permettre aux administrateurs habilités d'enregistrer une demande de
  signature liée à leur identité, fonction et établissement. La signature
  reste inutilisable avant validation par un autre responsable autorisé.
- Prévoir les états en attente, validée, refusée, suspendue, expirée et révoquée,
  avec auteur, date et motif des décisions. Réserver l'usage aux types de
  documents et périodes autorisés.
- Toute utilisation par une autre personne exige une délégation explicite,
  bornée et révocable ; distinguer le titulaire de la signature de l'opérateur
  qui l'appose. Interdire le libre partage d'une image ou d'une clé privée.
- À chaque nouvelle apposition ou réémission signée, enregistrer document et
  version, empreinte, titulaire, opérateur, autorisation et horodatage.
  Créer obligatoirement une notification persistante au titulaire dans la
  même opération ; proposer email/push en complément, avec suivi des échecs
  et reprises. Un échec de création de la notification interne bloque l'usage.
- Le titulaire consulte l'historique de ses usages et peut signaler un usage
  inattendu. Un rejeu technique de la même opération ne crée pas une nouvelle
  signature ; un simple téléchargement d'un PDF inchangé n'est pas une nouvelle
  apposition et relève d'un journal d'accès distinct.
- Conserver la version signée ; toute correction produit une nouvelle version
  soumise aux validations requises. Prévoir vérification d'intégrité et statut
  de validité/révocation sans exposer publiquement les données de l'étudiant.
- Une image manuscrite n'est qu'une représentation visuelle : fournir une
  preuve cryptographique vérifiable. Choisir le mécanisme ou prestataire selon
  le niveau juridique requis ; ne pas revendiquer une signature qualifiée
  sans les garanties et qualifications correspondantes.

**Recette :** refus avant validation, sans délégation, après expiration ou
révocation ; usage autorisé avec preuve vérifiable, journal et notification du
bon titulaire ; rejet d'un document altéré ; aucun succès silencieux si la
notification obligatoire ne peut pas être enregistrée.

**Ordre de réalisation :** cadrer les droits et validations en P1 ; livrer
REC-01 et EXP-01 en priorité dans P2, puis le circuit SIG-01 sur les documents
officiels. Les certifications interopérables et qualifications spécialisées
restent en P5. Ces lots ne suppriment aucun des chantiers déjà prévus.

### Écarts concrets qui empêchent de déclarer ces domaines terminés

- Les examens disposent maintenant de formulaires sessions/épreuves/convocations/
  résultats et du circuit de publication ; jurys, équivalences et agrégations
  officielles ne sont pas terminés pour autant.
- L'emploi du temps supérieur permet de créer les créneaux et de décider les
  réservations ; les chevauchements complexes et la planification multi-campus
  restent à qualifier.
- La page supérieure des paiements fournit surtout consultation et historique,
  pas un parcours complet de facturation et d'encaissement.
- La page des stages est une liste, pas tout le circuit offre/candidature/
  convention/suivi/évaluation.
- La signature actuelle d'un diplôme enregistre un signataire et une date.
  Son URL de vérification est construite avec un domaine fixe :
  ce n'est pas encore une signature cryptographique ni un registre public
  institutionnel opérationnel.
- Les portails parents/apprenants existent : ils sont à compléter et qualifier,
  pas à recréer comme s'ils étaient absents.
- Les notifications et les rapports configurables existent aussi ; ils ne
  constituent pas encore une messagerie complète ou un outil BI généraliste.

## 4. Moteurs transversaux à terminer ou construire

| Moteur cible | Point de départ | Travaux nécessaires |
|---|---|---|
| Configuration institutionnelle | Catalogues, dimensions, groupes ; offres composables et simulation ; règles conservées dans les inscriptions et évaluations de contrôle continu. | Héritage réseau/établissement/campus, gouvernance des révisions, migrations de configuration et extension aux examens/publications/crédits. |
| Workflow Engine | Transitions spécialisées, événements et historique ; paramètres de validation et financiers. | Définitions versionnées, étapes/acteurs/conditions, délais, délégations, escalades, reprise après erreur et éditeur utilisable. Ne pas modifier rétroactivement les dossiers en cours. |
| Rules Engine | Barèmes, critères et résolution de certaines politiques. | Priorités explicites, dates d'effet, simulation sur jeux d'exemples, explication du calcul et règles de pays/profil. Pas d'exécution libre de code utilisateur. |
| Form Builder | Formulaires développés et paramètres administratifs existants. | Champs personnalisés typés, validations, sections conditionnelles, droits par champ, pièces jointes, versions et stratégie de conservation des données après retrait d'un champ. |
| Report Builder | Exports et rapports sur schémas de données autorisés. | Sélection de champs/filtres/agrégations, modèles sauvegardés, planification, permissions et limites de coût. Pas de SQL arbitraire depuis l'interface. |
| Document Engine | Génération de PDF et métadonnées de validation. | Gabarits institutionnels, traduction, génération asynchrone, signature, horodatage, vérification, révocation et archivage selon les règles applicables. |
| Notification Engine | In-app/email/SMS/webhooks, préférences et suivi. | Déploiement fournisseur, délivrabilité, files/reprises, dédoublonnage, push, urgences, messages multilingues et règles de consentement. |
| Identité numérique | Comptes distincts dans les deux SIS ; mapping Open edX. | Identité canonique et affiliations, SSO partagé, délégations et gestion du départ/changement de rôle. Ne pas fusionner automatiquement des personnes sur leur seul email. |
| Integration Hub / API | REST, OpenAPI, webhooks et outbox Open edX. | Contrats versionnés, gestion des identifiants externes, rejeu, réconciliation, suivi et connecteurs standards. Le proxy actuel n'est pas un portail de développeurs complet. |
| Recherche et données analytiques | Recherche par liste et tableaux métier. | Recherche globale avec les mêmes permissions que les API, données analytiques séparées, provenance, dictionnaire d'indicateurs et agrégations autorisées. |
| Hors ligne | Pas de mécanisme de synchronisation SIS identifié. | Identifiants/versionnement dès P1 ; cache autorisé, file locale chiffrée, idempotence, conflits et révocation. Interdire par défaut la mise en cache des données médicales/financières sensibles. |
| Plugins et écosystème | Modules internes. | API d'extension stable, permissions explicites, compatibilité/versionnement, signature des packages, installation/désinstallation et procédure de revue. Marketplace seulement après stabilisation. |
| IA | À construire. | Accès documentaire filtré par tenant/rôle, choix fournisseurs, limites de coût, journalisation, évaluation, sources citées et validation humaine. |

Le workflow de soutenance demandé sera un scénario de référence :
**dépôt → validation du directeur → autorisation du département →
planification/jury → décision humaine → PV et archivage**.
Le même moteur devra ensuite exécuter une admission et une délivrance de
certificat avec d'autres configurations, sans dupliquer son code.

## 5. Architecture : conserver les acquis et préparer l'évolution

Trois niveaux restent distincts : **noyau obligatoire**, **modules activables**
et **plugins spécialisés**. Credential possédera les versions des justificatifs
délivrés ; le SIS reste propriétaire des résultats officiels, le LMS des
activités pédagogiques et l'ERP des écritures comptables. Aucune extension ne
doit entretenir un dossier concurrent.

La configuration cible suit **plateforme → pays → organisation/tenant →
établissement/campus → département/programme**. Chaque paramètre aura type,
défaut, portée, validation, droit de modification, version et date d'effet.
Les verrous supérieurs, la valeur effective et son origine doivent être
visibles, avec simulation avant publication et conservation des règles des
dossiers engagés. EXT-01 fournit le défaut du registre et la surcharge
d'activation du tenant. Le premier incrément **CFG-02** ajoute des unités
tenant-locales (campus, département, programme), des publications datées
immuables, des verrous, une simulation et la consultation historique.
Son premier paramètre effectif est `learning.offering`, copié avec sa provenance
sur les nouvelles classes/formations ; les dossiers existants restent inchangés.
Les choix explicites autorisés sont distingués de l'héritage. Une publication
parent peut neutraliser des valeurs descendantes : la simulation et la résolution
les signalent. Les niveaux plateforme/pays/réseau, les affiliations multiples,
les autorisations par campus et les autres paramètres restent à construire.

Les contrats futurs doivent couvrir SIS, LMS, ERP, IA, Credential,
intégrations et gouvernance. Les packages internes sont déployés par
l'exploitant ; le code tiers s'exécute hors du processus Django avec API et
autorisations limitées. Signature de package et isolation sont complémentaires.
La désactivation d'un abonnement ou plugin ne supprime jamais automatiquement
les données institutionnelles.

| Sujet | Proposition |
|---|---|
| Noyau métier | Conserver Django, les deux variantes et `sis_common` pendant la transition. Identifier les doublons, extraire progressivement des services partagés et maintenir la compatibilité des données/API. Un noyau configurable est une cible, pas l'état actuel. |
| LMS | Garder Open edX comme moteur de contenu, quiz et progression ; qualifier la version de déploiement, Studio et les interfaces apprenantes nécessaires. Ne pas reconstruire son moteur d'évaluation dans le SIS. |
| Source de vérité | SIS : personnes, affiliations, inscriptions et résultats officiels. LMS : activités, remises et progression. ERP : écritures comptables/paie. Documenter les responsabilités et règles de résolution des conflits. |
| Frontend | Conserver React ; introduire TypeScript progressivement dans les composants modifiés et rationaliser MUI/Paragon. Appliquer la direction UX-01 définie en section 8 : expérience pédagogique simple, administration structurée et composants cohérents, plutôt qu'une copie de plusieurs produits. |
| Identité | Définir les contrats de fédération dès P1. Keycloak est une option d'IdP, non un remplacement automatique obligatoire des mécanismes existants. Prévoir OIDC/SAML selon les établissements. |
| Asynchrone | Conserver Celery/Redis et l'outbox. Ajouter un bus distinct seulement si débit, découplage ou exploitation le justifient. |
| Documents | Passer du stockage privé local à une abstraction compatible S3/MinIO quand nécessaire ; maintenir autorisations, antivirus, chiffrement et rétention. |
| Recherche | Commencer par la recherche autorisée sur les données disponibles ; décider d'OpenSearch après mesure des volumes et besoins de recherche documentaire. |
| Vidéo | Intégrer BigBlueButton ou un fournisseur LTI. Ne pas développer un serveur de visioconférence WebRTC maison. |
| Finance/RH | Garder les processus éducatifs dans le SIS, intégrer comptabilité/paie à un ERP et les encaissements à des prestataires qualifiés. |
| Mobile | Web responsive accessible, puis PWA avec synchronisation ciblée ; applications React Native si les usages nécessitent une application native. |
| Observabilité | Compléter métriques et journaux par supervision/alertes effectives, traces utiles, tableaux de bord et procédures d'incident. |

## 6. Planning de réalisation

### Hypothèses d'estimation

Fourchettes de cadrage, **pas engagement de livraison** : quatre développeurs
expérimentés, une personne QA, un DevOps à mi-temps, un responsable produit et
des référents métier disponibles. Expertise sécurité, droit, comptabilité et
IA mobilisée sur les phases concernées.

Les durées ci-dessous sont celles d'un lot concentré avec cette équipe, pas des
jours de travail d'un agent IA. Les phases peuvent se chevaucher partiellement,
mais pas toutes avec les mêmes personnes. Rechiffrer après le cadrage et deux
sprints de réalisation. Les licences, intégrations, migrations de données et
délais de validation des établissements peuvent déplacer les jalons.

| Phase | Priorité et durée indicative | Livrable principal | Dépendances / sortie |
|---|---|---|---|
| **P0 — Cadrage et état réel** | Immédiate ; 2–3 semaines | Backlog traçable, périmètre pilote, architecture et risques | Sortie : scénarios et règles validés par les deux établissements pilotes. |
| **P1 — Noyau configurable** | Critique ; 6–10 semaines | Identités/affiliations, organisation, configuration hiérarchique, politiques et contrats d'extension | Après P0. Quatre profils contrastés et une offre mixte, sans fork. |
| **P2 — Extensions et catalogue privé** | Critique ; 4–6 semaines | Registre, dépendances, permissions, activation et deux extensions de référence | Après P1. Installation/mise à jour/désactivation sans perte de données ni contournement des droits. EXT-01 est un premier incrément, pas la sortie de P2. |
| **P3 — SIS prioritaire complet** | Critique ; 10–16 semaines | Candidature → décision → inscription → scolarité → résultats | Contrats P1 ; peut avancer avec P2. Parcours par rôle sans intervention technique normale. |
| **P4 — LMS intégré** | Critique ; 8–14 semaines | Open edX/Studio, connexion commune, activités et résultats | Contrats d'identité/inscription ; validation explicite avant résultat officiel. |
| **P5 — Finance et administration** | Haute ; 12–20 semaines | Facturation, encaissement, reçus, rapprochement et connecteurs ERP/RH | Dossiers stabilisés et fournisseurs qualifiés ; reprise sans double opération. |
| **P6 — Diplômes et compétences** | Haute ; 8–12 semaines | Conditions d'obtention, signature, vérification/révocation et portefeuille | Résultats officiels stabilisés ; ne dépend pas obligatoirement du LMS. |
| **P7 — IA et pilotage** | Progressive ; 8–12 semaines | Indicateurs autorisés, assistant documentaire et génération validée | Données fiables ; sources, droits, coûts et intervention humaine traçables. Pas de sanction automatique. |
| **P8 — Écosystème et commercialisation** | Extension ; 16–32 semaines pour un premier lot | SDK, portail développeur, marketplace contrôlée, provisioning, packs pays et mobile ciblé | Catalogue privé éprouvé ; extensions partenaires exploitables selon des contrats stables. |

**Correspondance des détails historiques ci-dessous :** P0/P1 inchangés ;
ancien P2 → nouveau P3 ; ancien P3 → P4 ; ancien P4 → P5 ; ancien P5 →
P6/P7 et contrats d'intégration transversaux ; ancien P6 → P8. Le nouveau P2
est avancé avant la marketplace publique, sans attendre la fin des métiers.

| Exigence de l'incrément | Responsable fonctionnel attendu | Critère d'acceptation | État |
|---|---|---|---|
| CAL-01 : clôtures et résultats | Scolarité / responsable des examens | Refuser modifications après clôture, conserver résultats, imposer les transitions de publication | Implémenté sur les parcours corrigés ; pas homologation universelle |
| PAR-01 : transfert simple | Scolarité | Motif, cohérence dossier/inscription et historique ; refus explicite si équivalences nécessaires | Implémenté ; conversion des acquis non livrée |
| AUD-01 : journaux | Responsable habilitations / exploitation | Même acteur et bornes inclusives dans liste, bilan et export ; confidentialité des réclamations | Implémenté |
| EXT-01 : catalogue installé | Administration / exploitation | Simuler puis activer/désactiver ; conflits de révision rejetés ; dossiers intacts à la réactivation | Premier module facultatif implémenté |
| CFG-02 : configuration hiérarchique | Produit / référents pays | Origine effective, verrous, date d'effet et snapshots sur quatre profils et offre mixte | Premier incrément tenant/campus/département/programme implémenté pour l'offre des nouveaux groupes ; plateforme/pays et paramètres supplémentaires restent à construire |
| EXT-02 : deux extensions externes | Exploitation / responsables des données | Versions compatibles, permissions et tâches contrôlées, suspension et conservation testées | Reste à construire ; fournisseurs à qualifier |

Ces responsabilités sont des rôles à attribuer par l'établissement, pas une
équipe déjà engagée. Pays pilote, personnes référentes, systèmes externes,
volumétrie et RPO/RTO nécessitent encore une validation institutionnelle.

**Jalons d'ordre de grandeur :** pilote SIS + LMS limité en **6–9 mois** ;
première plateforme institutionnelle élargie en **12–18 mois** ;
vision globale du document en **24–36 mois ou davantage**. Ces horizons supposent
réutilisation des moteurs externes, périmètres bornés et équipe disponible.
Ils ne garantissent pas la prise en charge de tous les pays ou métiers.

### P0 — Cadrage et remise à plat du backlog

- [ ] Identifier les deux établissements pilotes, leurs effectifs, pays, langues,
  devises, calendriers, acteurs et systèmes existants.
- [ ] Attribuer des identifiants d'exigences sous D01–D20 et relier chaque exigence
  à une interface, une API, des règles, une recette et un responsable.
- [ ] Reprendre les anciens TODO : conserver l'historique, retirer les doublons
  du backlog actif et distinguer terminé, partiel, absent et dépendance externe.
- [ ] Tester les écrans historiques avec les vrais rôles ; inventorier les
  boutons sans action, contrats non alignés et passages obligés par Django Admin.
- [ ] Valider les maquettes UX-01 des espaces apprenant, enseignant et gestionnaire,
  sur ordinateur et mobile, à partir des références documentées en section 8.
- [ ] Choisir la version Open edX/Tutor compatible et les fournisseurs pilotes :
  SMTP, vidéo, paiement, identité et ERP si retenu.
- [ ] Définir volumétrie, disponibilité, RPO/RTO, confidentialité et budget.
- [ ] Valider les frontières SIS/LMS/ERP et les règles de migration du code existant.

**Recette de sortie :** backlog priorisé et scénario pilote signé par le
responsable produit et les référents métier. Aucun pourcentage global fictif.

### P1 — Consolider le noyau commun

- [ ] Définir identité canonique, affiliations, groupes/campus et périmètres.
- [ ] Concevoir le modèle commun sans imposer classe, semestre, crédits ou
  département à tous les profils ; préserver les données des variantes existantes.
- [x] Livrer un catalogue versionné et un éditeur de configurations d'offres
  combinables pour primaire, secondaire, supérieur et formation professionnelle,
  avec crédits facultatifs et simulation des règles.
- [x] Relier les offres aux classes/formations, inscriptions et évaluations
  de contrôle continu, avec conservation des règles appliquées aux résultats.
- [ ] Étendre ces liens aux transferts, examens, jurys, publications et crédits ;
  compléter la gouvernance et l'historique des révisions de règles.
- [ ] Permettre plusieurs types d'offres dans une même institution et un
  assistant de configuration avec modules, règles, rôles et import de données.
- [ ] Uniformiser le contrôle des droits : rôle, attribut, relation et séparation
  des responsabilités ; couvrir les exports et téléchargements également.
- [ ] Encadrer les comptes de secours, politique MFA, récupération, sessions
  et historique des connexions/appareils.
- [ ] Définir les habilitations SIG-01 : validation indépendante des signatures,
  délégations bornées, révocation et notification obligatoire de chaque usage.
- [ ] Livrer le premier socle des moteurs workflow/règles/formulaires :
  définitions versionnées et contrat de simulation, sans attendre la phase IA.
- [ ] Fixer les contrats d'événements, idempotence et versions nécessaires au
  futur hors ligne ; ne pas développer tout le mobile à ce stade.
- [ ] Définir stockage documentaire, analyse antivirus, rétention et suppression.
- [ ] Industrialiser installation, mises à jour, migrations, retour arrière,
  images distribuables, sauvegardes hors machine et alertes.
- [x] Livrer le premier incrément UX-01 : shell commun, navigation par
  capacités/rôles et contexte, menu mobile et accueils raccordés aux API.
- [x] Étendre le socle UX-01 : marque de l'établissement, thèmes clair/sombre,
  favoris et palette de navigation, catalogue privé et impacts des activations.
- [ ] Compléter UX-01 : parcours quotidiens par espace, filtres/vues enregistrées,
  composants internationalisables et qualification complète d'accessibilité.

**Recette de sortie :** démontrer les quatre configurations du noyau et une
institution combinant plusieurs offres, sans fork ni champs obligatoires
inadaptés ; vérifier l'isolation sur au moins deux institutions ; mettre à jour
puis restaurer un environnement de préproduction avec les procédures documentées.

### P2 — Terminer la scolarité de bout en bout

- [ ] Admissions : campagne, candidature, pièces, entretien/test, décision et
  conversion en inscription ; règles configurables via les premiers moteurs.
- [ ] Dossiers : familles, réinscription, transfert, abandon/suspension,
  documents et historique.
- [ ] Personnel : affectations, disponibilités et remplacements nécessaires
  aux cours ; réserver la paie complète à P4.
- [ ] Organisation : classes/groupes ou formations/UE/ECUE, prérequis, crédits,
  inscriptions pédagogiques et emplois du temps.
- [ ] Assiduité : appel, justification, validation et notification aux personnes
  autorisées ; calendrier et vues enseignant/apprenant/parent.
- [ ] Résultats : saisie, corrections, calculs, conseils/jurys, validation,
  publication, bulletins/relevés et procédure de contestation/rectification.
- [x] Livrer le premier parcours REC-01 : dépôt et suivi privés, justificatifs
  PDF, échanges, affectation, décision motivée, clôture, recours et notifications.
- [ ] Compléter REC-01 : délais/relances et recours configurables, délégations
  familiales, services, antivirus et cycle de conservation des pièces.
- [ ] Livrer EXP-01 : « Mes documents », transcripts et relevés autorisés,
  exports filtrés des données étudiantes et parcours d'export des gestionnaires.
- [ ] Raccorder SIG-01 aux documents officiels : validation préalable,
  utilisation autorisée, preuve, version figée et notification du titulaire.
- [ ] Appliquer UX-01 à ces trois parcours : suivi de réclamation, documents
  téléchargeables et centre de signatures/notifications, avec tous leurs états.
- [ ] Achever les actions manquantes des interfaces et les erreurs de parcours.
- [ ] Livrer les portails utiles au pilote, avec comptes nominatifs par rôle.
- [ ] Finaliser un premier rapport institutionnel et les exports de migration.

**Recette de sortie :** un agent de scolarité traite un candidat jusqu'à son
inscription ; l'enseignant fait l'appel et saisit des notes ; la direction
valide ; l'apprenant ou son parent consulte seulement les résultats autorisés.
Tester également refus, doublon, changement d'année, transfert et rectification.

### P3 — Livrer le LMS intégré

- [ ] Déployer et maintenir une distribution Open edX compatible avec ce dépôt,
  incluant les composants réellement nécessaires à Studio et aux apprenants.
- [ ] Relier SSO, affiliations, classes/cours, enseignants, inscriptions et rôles.
- [ ] Exposer une navigation cohérente entre portail SIS, cours et Studio.
- [ ] Décliner UX-01 dans le parcours de cours : structure, travail à rendre,
  correction, progression et retour au portail, sans recréer le moteur Open edX.
- [ ] Cours : contenus multimédias et interactifs, progression, conditions,
  groupes, bibliothèques partagées et réutilisation/versionnement.
- [ ] Expérience quotidienne : annonces, échéances, devoirs, remises en retard,
  nouvelle soumission, rubriques, commentaires et calendrier.
- [ ] Évaluations : questions/banques/QCM, notation automatique ou manuelle,
  intégrité académique et adaptation aux besoins pédagogiques.
- [ ] Relier les examens physiques/numériques au jury SIS sans dupliquer le
  moteur LMS ; distinguer note provisoire et résultat officiel.
- [ ] Classes virtuelles via un fournisseur, présence, enregistrements,
  sous-titres et rétention.
- [ ] Tester webhooks, idempotence, déconnexion/reconnexion, panne temporaire
  du LMS et réconciliation des écarts.

**Recette de sortie :** un cours créé dans Studio est accessible aux seuls
inscrits ; un devoir est remis, corrigé, synchronisé puis publié dans le SIS.
Rejouer les événements ne crée ni double inscription ni double note.

### P4 — Finance, RH et services de l'établissement

- [ ] Terminer les interfaces de frais/factures, réductions, échéanciers,
  paiements partiels, justificatifs, reçus, impayés et remboursements.
- [ ] Intégrer d'abord un prestataire de paiement du pays pilote ; valider
  webhooks signés, répétitions, échecs, remboursements et rapprochement.
- [ ] Relier budget, dépenses, comptabilité et paie à un ERP ; préciser la
  source de vérité et éviter la double tenue comptable.
- [ ] RH : contrats, postes, organigrammes, congés, charges, évaluations et formation.
- [ ] Bibliothèque : prêts/retours/réservations et pénalités ; fonds numériques
  et licences selon le périmètre de l'établissement.
- [ ] Cantine/transport/internat : capacités, conflits, tarifs, réservations
  et facturation ; ne pas se limiter aux formulaires CRUD.
- [ ] Inventaire, maintenance et équipements ; connecteurs d'accès physique
  seulement si requis.
- [ ] Stages, mémoires, soutenances, recherche et mobilité : circuits complets,
  acteurs externes limités et archives.
- [ ] Messagerie institutionnelle et communication parents/personnel,
  préférences, délivrabilité et gestion des urgences.

**Recette de sortie :** un cycle réel de facturation est rapproché avec le
prestataire/ERP ; les services scolaires ne dépassent pas leurs capacités ;
un dossier de stage ou soutenance parcourt toutes les validations prévues.

### P5 — Interopérabilité, certifications, BI et IA

- [ ] Mettre en production les connecteurs prioritaires du tableau des standards.
- [ ] Transformer la validation documentaire actuelle en émission vérifiable :
  signature, registre, QR, révocation et vérification respectueuse des données.
- [ ] Publier Open Badges/CLR selon les besoins du pilote et conserver la
  distinction entre conformité technique et certification d'un organisme.
- [ ] Stabiliser dictionnaire des indicateurs, qualité des données et rapports
  personnalisables ; alimenter un entrepôt analytique si nécessaire.
- [ ] Mesurer réussite, assiduité, abandon, finances et programmes avec des
  définitions communes et des agrégations autorisées.
- [ ] Livrer d'abord une recherche documentaire assistée et un assistant
  enseignant, avec sources et validation humaine.
- [ ] Étendre ensuite aux cours/QCM/devoirs, résumés, traduction, tutorat,
  recommandations, aide à la correction et rapports administratifs.
- [ ] Évaluer tout signal de risque de décrochage : erreurs, biais, explication,
  droit de contestation et utilité pédagogique ; pas de décision automatique.

**Recette de sortie :** un système tiers échange les données choisies sans
ressaisie ; un document révoqué n'est plus annoncé valide ; l'IA ne consulte
pas de documents hors périmètre et ne publie pas une décision sensible seule.

### P6 — Mobile, hors ligne et extension internationale

- [ ] Étendre les profils institutionnels selon l'ordre indiqué ci-dessous.
- [ ] Livrer les packs pays : règles académiques, langues/RTL, devises,
  calendriers, documents et obligations de conservation.
- [ ] Introduire une PWA hors ligne : cours autorisés téléchargés, emplois du
  temps, présence et notes autorisées en file d'attente.
- [ ] Définir la résolution de conflits avec visualisation, arbitrage,
  traçabilité, idempotence et retrait d'accès d'un appareil.
- [ ] Tester perte de connexion, appareil perdu, données périmées, révocation
  d'un rôle et reconnexion après clôture d'une période.
- [ ] Développer les applications natives si le besoin est confirmé.
- [ ] Stabiliser SDK/API d'extension, gestion des versions et sécurité des
  plugins ; lancer ensuite un catalogue et un processus de publication.
- [ ] Étendre Alumni, compétences/certifications, partenaires et connecteurs
  locaux ; former les intégrateurs et organiser le support.
- [ ] Qualifier charge, capacité multi-tenant, reprise et exploitation pour
  chaque niveau de service proposé.

**Recette de sortie :** un nouvel établissement d'un profil pris en charge
se configure sans fork ; les opérations hors ligne autorisées se synchronisent
sans écrasement silencieux ; une extension peut être retirée proprement.

## 7. Profils institutionnels : ordre proposé

Les vagues ci-dessous concernent la complétude métier et la qualification
opérationnelle, pas le début de la conception d'un profil. Le noyau doit déjà
être confronté aux quatre configurations de référence en P1.

| Vague | Profil | Adaptations spécifiques |
|---|---|---|
| Pilote P1–P3 | Collèges/lycées | Matières, coefficients, conseils, discipline, orientation et examens ; qualifier les règles nationales retenues. |
| Pilote P1–P3 | Universités/grandes écoles | UE/ECUE, crédits, semestres, inscriptions pédagogiques, jurys ; compléter recherche/stages/mémoires en P4. |
| Extension P4–P6 | Formation professionnelle | Compétences, ateliers, périodes pratiques, insertion et certification. |
| Extension P3–P6 | Formation en ligne | Parcours autonomes, abonnements, accès conditionnels, paiement et certificats. |
| Extension P6 | Maternelles/primaires | Enseignants polyvalents, suivi adapté à l'âge, responsabilités parentales, autorisations et services scolaires. |
| Extension P6 | Formation d'entreprise | Salariés/départements, formations obligatoires, conformité et intégration RH. |
| Extension P6 | Établissements internationaux | Plusieurs programmes, langues, calendriers, notes/crédits et équivalences. |
| Extension P6 | Établissements spécialisés | Stages cliniques, laboratoires, ateliers, exigences professionnelles et accès sensibles propres au domaine. |

Chaque profil doit fournir configuration, rôles, gabarits, jeux de recette et
documentation. Ajouter une valeur dans une liste « type d'établissement »
ne suffit pas à prendre ce profil en charge.

## 8. Espaces utilisateurs à livrer

| Espace demandé | Base actuelle et objectif | Phase principale |
|---|---|---|
| Super administrateur plateforme | Les comptes privilégiés existent ; ajouter une console réseau/provisioning distincte de l'administration d'un tenant. | P1 |
| Administrateur institutionnel | Consolider configuration, utilisateurs, modules et délégations existants. | P1 |
| Directeur / responsable académique | Compléter tableaux de bord, programmes, validations, résultats et pilotage. | P2, P5 |
| Secrétaire / scolarité | Admissions, inscriptions, pièces et dossiers sans passage normal par l'administration technique. | P2 |
| Enseignant / formateur | Classes, cours, appel, devoirs, correction, compétences et communication dans un espace cohérent. | P2, P3 |
| Étudiant / élève | Compléter les portails existants avec cours, devoirs, progression, agenda et démarches. | P2, P3 |
| Parent / tuteur | Compléter le portail multi-enfants avec autorisations, devoirs, échanges et paiements. | P2–P4 |
| Comptable | Facturation, encaissement, rapprochement, remboursement et exports autorisés. | P4 |
| Responsable RH | Contrats, affectations, charges, congés et intégration paie. | P4 |
| Bibliothécaire | Catalogue, prêts, retours, réservations et accès numériques. | P4 |
| Responsable informatique | Exploitation, assistance et diagnostics sans accès métier illimité par défaut. | P1, P4 |
| Auditeur | Lecture contrôlée de preuves et historiques, sans capacité de modifier les opérations. | P1, P5 |
| Partenaire externe | Tuteur de stage, jury ou fournisseur avec périmètre et durée d'accès explicites. | P4 |
| Ancien étudiant | Diplômes, attestations, compétences et services Alumni. | P5, P6 |

Une politique de droits doit aussi préciser les relations : enseignant de cette
classe, parent de cet enfant, correcteur de cette copie. L'existence d'un rôle
dans une liste ne prouve pas l'existence de l'espace de travail correspondant.

### UX-01 — Direction de design et références demandées

**Exigence :** viser la qualité d'organisation et d'utilisation des LMS/SIS
cités par le demandeur. Construire une identité LMS_SIS cohérente, configurable
par établissement, et non seize thèmes incompatibles ni une reproduction des
marques, illustrations ou écrans propriétaires.

La comparaison ci-dessous est **documentaire**, établie le 2 novembre 2026 à
partir des sources publiques liées. Les guides permettent de relever des
interactions ; les pages produit et brochures décrivent des intentions et
capacités, pas une ergonomie mesurée. Ce n'est ni un audit pratique de ces
produits, ni une preuve de leur accessibilité, ni une garantie que toutes leurs
éditions ont la même interface. Le premier shell SIS est implémenté ; les
maquettes et parcours métier détaillés ci-dessous restent à compléter.

#### Références et principes à adapter

| Référence et source | Organisation documentée | Application proposée à LMS_SIS |
|---|---|---|
| [Moodle — Dashboard](https://docs.moodle.org/en/dashboard) | Vue des cours, échéances, calendrier et blocs personnalisables. | Accueil pédagogique centré sur les cours et les prochaines actions, plutôt que sur des statistiques seules. |
| [Canvas LMS — Dashboard](https://community.instructure.com/en/kb/articles/664620-how-do-i-use-the-dashboard) | Navigation globale ; vues cartes, liste/agenda et activité récente ; tâches à faire. | Cartes de cours et agenda cohérents, avec accès stable aux espaces principaux. |
| [Blackboard Learn — navigation](https://help.anthology.com/blackboard/student/en/getting-started/navigate-outside-a-course.html) | Navigation de base persistante vers cours, activité, calendrier, messages et résultats. | Séparer navigation institutionnelle et navigation interne d'un cours sans perdre le contexte. |
| [D2L Brightspace — navigation](https://community.d2l.com/brightspace/kb/articles/5787-navigate-brightspace-and-find-your-course) | Accueil à widgets, sélection de cours et navigation configurable par l'organisation. | Tableaux de bord adaptés au profil, avec mêmes repères d'un module à l'autre. |
| [Google Classroom — prise en main étudiant](https://support.google.com/edu/classroom/answer/9582544?hl=en-GB) | Séparation entre fil d'annonces, travaux du cours et participants. | Peu d'actions simultanées pour l'apprenant ; séparer annonces, contenu et travail à remettre. |
| [Schoology — annonces de cours](https://uc.powerschool-docs.com/en/schoology/latest/course-updates-instructors) | Annonces dans le cours et sur l'accueil ; mise en avant d'une annonce importante. | Communication contextualisée, sans mélanger une notification administrative et un devoir. |
| [Open edX — guide apprenant](https://docs.openedx.org/en/ulmo/learners/index.html) | Tableau de bord, sections de cours, reprise d'apprentissage et consultation de la progression. | Harmoniser l'accès au moteur pédagogique existant, la progression et le retour vers le dossier SIS. |
| [Blackbaud — rôles et personas](https://webfiles-sc1.blackbaud.com/files/support/helpfiles/education/k12/panel/content/bb-core-roles-personas.html) | Regroupement des tâches selon rôles, personas et domaines fonctionnels. | Un compte avec plusieurs affiliations autorisées ; un espace de travail adapté au rôle actif. |
| [Sakai — Home Dashboard](https://sakai.screenstepslive.com/s/sakai_help/a/1916851-what-information-is-displayed-on-the-home-dashboard) | Accueil réunissant cours, annonces, discussions, calendrier et résultats ; disposition personnalisable. | Synthèse transversale utile sans multiplier les pages d'accueil déconnectées. |
| [TalentLMS — guide de refonte](https://help.talentlms.com/hc/en-us/articles/14758084707228-TalentLMS-redesign-guide) | Tableaux de bord distincts, menu rétractable, recherche et changement de rôle autorisé. | Même structure visuelle, mais raccourcis et densité adaptés aux apprenants, formateurs et administrateurs. |
| [PowerSchool SIS — recherche étudiant](https://ps.powerschool-docs.com/pssis-admin/latest/student-basic-search) | Recherche puis sélection d'un étudiant ou d'un ensemble d'étudiants. | Dossier central facilement retrouvable, filtres et actions groupées contrôlées pour la scolarité. |
| [Infinite Campus — planification et portail](https://kb.infinitecampus.com/help/academicplannersystemsetup-studyguide) | Progression du parcours académique et options du portail paramétrables par école. | Afficher les étapes utiles du parcours et les services effectivement activés pour l'établissement. |
| [Ellucian Banner — brochure Self-Service](https://www.ellucian.com/sites/default/files/uploads/files/en/brochure/brochure-learn-more-about-ellucian-banner-self-service.pdf) | Profil académique consolidé et fonctions distinctes pour étudiants, enseignants et conseillers. | Dossier académique, inscriptions, résultats et documents reliés, sans obliger l'étudiant à naviguer dans l'administration. |
| [Workday Student — expérience étudiante](https://www.workday.com/en-us/products/student/student-experience.html) | Parcours guidés et regroupement des informations/actions dans les espaces académique et financier. | Accueil orienté « ce que je dois faire », demandes et validations suivies jusqu'à leur résultat. |
| [iSAMS — portails](https://www.isams.com/platform/portals/) | Portails distincts pour élèves, parents et admissions, avec informations ciblées. | Vues familiales et apprenantes dédiées ; ne pas exposer un menu de gestionnaire aux parents. |
| [Arbor — navigation du dossier étudiant](https://support.arbor-education.com/hc/en-us/articles/211750965-Student-Profile-Introduction-Navigation) | Profil consolidé, sections selon les permissions et accès rapide aux informations pertinentes. | Fiche apprenant structurée, actions contextuelles et informations sensibles visibles uniquement aux personnes habilitées. |

Ces références guident les interactions, pas l'annonce de fonctionnalités déjà
présentes. Les quiz, rubriques, classes virtuelles, connecteurs, analytics et
plugins restent soumis aux livraisons métier P2–P6 et à leurs propres recettes.

#### Charte et navigation communes

- Une palette neutre claire, des surfaces lisibles et une couleur principale
  d'établissement ; logo et libellés personnalisables sans changer les
  significations des statuts. Définir typographie, espacements, bordures,
  icônes et états de composants dans une charte commune.
- Une barre supérieure avec contexte établissement/campus, période, compte
  et notifications ; une navigation latérale rétractable, puis un fil d'Ariane
  et des onglets contextuels. La recherche globale sera proposée uniquement
  lorsque son index et ses permissions seront réellement implémentés.
- Composer le menu selon rôle, relations, offres et modules activés. Changer
  de rôle ne doit jamais accorder un droit supplémentaire. Les protections
  serveur restent obligatoires même si un bouton est masqué.
- Privilégier cartes, prochaines échéances et actions simples côté apprenant ;
  tableaux filtrables, colonnes choisies, pagination serveur et actions groupées
  explicites côté gestionnaire. Ne pas imposer le même niveau de densité partout.
- Garder des formulaires structurés, erreurs près des champs, état de sauvegarde
  visible et confirmations adaptées aux opérations irréversibles. Conserver
  filtres et contexte au retour d'un dossier.
- Prévoir chargement, liste vide, aucun résultat, accès refusé, erreur,
  opération en cours et réussite. Pas de chiffres fictifs, boutons sans action
  ou modules indisponibles présentés comme utilisables.
- Cibler WCAG 2.2 AA : clavier, focus visible, libellés explicites, contraste,
  erreurs annoncées et information indépendante des seules couleurs.
  Adapter les écrans au mobile et préparer traduction/RTL ; valider ces
  propriétés plutôt que déduire une conformité du choix d'une bibliothèque.

**Chaîne utilisée :** `SISLayout.jsx` utilise `Sidebar.jsx` et le registre
`navigation.js` pour les menus par variante et capacités ; `WorkspaceHome.jsx`
raccorde l'accueil aux portails et compteurs réels. `theme/tokens.js` alimente
le thème MUI et les variables de `index.scss` via `AppearanceProvider`.
Les nouveaux composants du socle et le catalogue utilisent MUI ; les
composants Paragon actifs reçoivent les mêmes couleurs, sans refonte des routes.
Continuer de faire évoluer cette chaîne active
et les composants partagés, sans créer une seconde interface décorative non
raccordée. Le filtrage du menu ne remplace pas les autorisations serveur.

#### Harmonisation des cartes, formulaires et sections

La charte est appliquée aux composants des routes actives, pas uniquement à
l'accueil : typographie Inter commune, titres hiérarchisés, surfaces adaptées au thème,
bordures sobres, rayon de 6 px pour les cartes et dialogues, marges internes de
24 px sur ordinateur et 16 px sur mobile. Les champs et boutons sont rectangulaires,
avec libellés persistants au-dessus des champs ; les panneaux imbriqués n'ajoutent
pas de bordure. Les couleurs
d'erreur, d'attente et de réussite restent distinctes et accompagnées de texte.
Les boutons et barres d'actions se replient, les tableaux défilent dans leur
propre conteneur et les fenêtres de saisie gardent leurs actions accessibles.

| Principes du comparatif | Application dans les écrans existants |
|---|---|
| Moodle, Canvas, Blackboard, Brightspace : organisation et hiérarchie des sections | Titres de page/section, onglets contextuels, cartes et groupes de saisie cohérents ; résultats chiffrés et compétences lisibles dans le même dialogue. |
| Classroom, Schoology, TalentLMS : simplicité et action principale identifiable | Accueil par rôle, cartes sans ombres excessives, démarches privées, formulaires de connexion et compte structurés. |
| PowerSchool, Banner, Workday, iSAMS, Arbor, Infinite Campus : gestion et dossier consolidé | Tableaux filtrables/paginés, barre d'actions adaptable, grilles de dossier responsive, configuration institutionnelle par sections. |
| Références transversales : lisibilité et usage mobile | Libellés de champs persistants, focus visible aussi dans les dialogues, réduction des animations, titres longs pouvant revenir à la ligne. |

Les treize en-têtes Paragon qui transmettaient leurs titres/actions comme
enfants sont corrigés pour utiliser les propriétés `title` et `actions`.
Cela rétablit notamment les boutons d'ajout de la configuration académique.
Les grilles MUI des dossiers étudiants et de l'intégration LMS utilisent
l'API responsive de la version installée, plutôt que des propriétés ignorées.

La recette visuelle est portée par `e2e/presentation.js` et les parcours réels
dual : connexion, compte, configuration Paragon, offres, tableaux de gestion,
formulaires CRUD, notes/compétences, dossiers, workflows, réclamations et
supervision de l'intégration LMS (sans LMS connecté dans cette recette).
Elle contrôle les surfaces rendues, les débordements aux largeurs 1440, 390
et 320 px, ainsi que l'affichage et le focus des actions des dialogues.
Les captures ordinateur/mobile servent à examiner le rendu, pas à affirmer
une correspondance pixel par pixel avec les produits de référence.
Cette inspection a également corrigé les mots fragmentés dans les tableaux
mobiles, les boutons comprimés dans les rangées de champs et le statut
« Inscrit » incorrectement coloré comme une erreur dans le dossier élève.

**Limites :** ce lot ne constitue ni une certification WCAG, ni une validation
de chaque donnée réelle ou de chaque combinaison de permissions. Les anciens
écrans `ModernLayout`/`ModernDashboard`, non montés, sont exclus. Les actions
métier encore partielles de certains écrans historiques ne deviennent pas
opérationnelles par un changement de style. Les transcripts officiels,
signatures vérifiables et parcours LMS manquants conservent leurs lots dédiés.

#### Vues de référence et critères de recette

| Vue | Contenu/action à rendre immédiatement compréhensible |
|---|---|
| Accueil apprenant | Reprendre un cours, voir les travaux à rendre, l'agenda, les résultats autorisés et les démarches en attente. |
| Espace enseignant | Classes/cours, appel, travaux à corriger, carnet de résultats et communication contextualisée. |
| Dossier de scolarité | Identité, inscriptions, résultats, documents et historique ; prochaine action et périmètre visibles. |
| Mes réclamations — REC-01 | Nouvelle demande, numéro de suivi, statut, échanges, réponse motivée et recours disponible. |
| Mes documents — EXP-01 | Année/type/statut, distinction export personnel/document officiel, format et téléchargement autorisé. |
| Centre de signatures — SIG-01 | Validation en attente, délégations, document à signer, identité du titulaire et historique des usages/notifications. |

Pour chaque vue, produire une maquette ordinateur/mobile puis une réalisation
raccordée aux vraies API. Faire exercer les opérations par les rôles concernés :
trouver une échéance, traiter un dossier, suivre une réclamation, télécharger
un transcript et consulter une notification d'utilisation de signature.

La recette comprend navigation clavier, petits écrans, chargement/erreurs,
longs libellés et jeux de données volumineux. Elle vérifie aussi l'absence de
fuite de données lors d'un changement de compte, rôle ou établissement.
Des captures et tests de parcours documentent le résultat ; une ressemblance
visuelle avec un concurrent ne suffit pas à déclarer la vue terminée.

## 9. Interopérabilité : couvrir tous les standards sans les développer d'un coup

| Standard / intégration | Priorité proposée | Résultat attendu |
|---|---|---|
| Open edX + identité fédérée | P1/P3 | Comptes/affiliations, inscriptions, cours, notes et réconciliation ; recette avec un vrai LMS. |
| LTI 1.3 | P3 | Lancement sécurisé d'outils ; rôles, contexte et retour de notes selon les services retenus. |
| OneRoster | P5, contrat préparé en P1 | Échange d'utilisateurs, classes, inscriptions et notes avec un système tiers choisi. |
| Edu-API | P5/P6 | Échange des données académiques supérieures selon les besoins des partenaires. |
| QTI | P3/P5 | Import/export d'évaluations et questions via le moteur LMS ; annoncer les versions/types réellement supportés. |
| SCORM | P3/P5 | Compatibilité des paquets et suivi via un composant LMS compatible ; ne pas supposer que tout Open edX le fournit nativement. |
| xAPI | P5/P6 | Événements d'apprentissage et dépôt LRS si nécessaire ; gouvernance des traces. |
| CASE | P5/P6 | Référentiels de compétences et correspondances. |
| Open Badges | P5 | Émission, preuve et vérification des badges selon la version choisie. |
| CLR | P5/P6 | Dossier portable des acquis, lié aux identités et aux certifications. |
| Caliper Analytics | P5/P6 | Événements standardisés pour les analyses autorisées. |
| Calendriers | P2/P3 | Export/abonnement iCalendar et connecteurs Google/Microsoft si retenus. |
| Finance, vidéo, bibliothèque, ERP | P3/P4/P6 | Connecteurs bornés, observables et remplaçables ; reprise en cas de panne. |

Pour chacun : version explicite, périmètre d'import/export, mappings, jeu de
conformité, limites et maintenance. Une API REST ou un champ « LTI » ne suffit
pas à revendiquer la conformité à un standard. Le protocole SSO n'autorise pas
à lui seul l'accès aux données d'un autre établissement.

## 10. Première tranche concrète

Ne pas commencer par l'IA, la marketplace ou une réécriture de framework.

| Ordre | Travail | Livrable vérifiable |
|---|---|---|
| 1 | Cadrer les deux pilotes et leurs règles | Scénarios, données de recette, acteurs, seuils et responsabilités validés. |
| 2 | Inventorier et terminer les parcours critiques incomplets | Liste des écrans/actions et backlog ; traitement prioritaire des examens, EDT supérieur, résultats et droits. |
| 3 | Formaliser le noyau configurable et les contrats de données | Quatre profils représentables, offres mixtes, schémas versionnés, source de vérité et compatibilité avec les données existantes. |
| 4 | Qualifier Open edX/Tutor et le SSO sur préproduction | Connexion et inscription d'un utilisateur dans un vrai cours. |
| 5 | Livrer le parcours admission/inscription | Candidat converti en apprenant sans doublons, pièces et décision historisées. |
| 6 | Relier cours, devoir, correction et note officielle | Parcours enseignant/apprenant/direction complet, rejouable et testé. |
| 7 | Ouvrir le pilote avec exploitation supervisée | Formation, support, sauvegarde externe, alertes, procédure d'incident et critères de retrait. |

Les premières semaines servent à estimer sur des tâches réellement terminées.
Les lots de développement ne doivent pas être tous ouverts simultanément :
un parcours livré vaut mieux que vingt nouveaux menus.

## 11. Conditions de livraison et risques

### Définition de « terminé » pour chaque fonctionnalité

- [ ] Modèle et migration compatibles avec les données existantes.
- [ ] Règles métier validées sur des exemples, y compris les refus et corrections.
- [ ] API documentée, permissions et isolation vérifiées.
- [ ] Interface utilisable par le rôle cible, avec états vide/erreur/chargement.
- [ ] Parcours navigateur et tests de non-régression adaptés.
- [ ] Accessibilité, traductions et confidentialité du périmètre vérifiées.
- [ ] Imports/exports, traces, reprise et performances vérifiés lorsque pertinents.
- [ ] Exploitation, assistance et procédure de retour arrière documentées.
- [ ] Acceptation par un utilisateur métier du pilote.

### Dépendances externes et arbitrages

| Sujet | Condition à lever |
|---|---|
| Règles académiques | Validation par la direction pédagogique : notes, crédits, passage, jury et recours. |
| Déploiement LMS | Version compatible, ressources serveur, domaines, certificats et identité. |
| Communications | Fournisseurs email/SMS/push, délivrabilité, consentement et coût. |
| Paiements/comptabilité/paie | Pays et devises pilotes, prestataires, environnement de test, ERP et expert comptable. |
| Signature et documents | Niveau juridique attendu, fournisseur/clés, révocation et procédure de vérification. |
| Données personnelles | Responsable de traitement, durées, droits, mineurs, données médicales et hébergement. |
| IA | Fournisseurs, données autorisées, évaluation, budget, exclusions et validations humaines. |
| Internationalisation | Traductions professionnelles, référents pays et règles locales ; aucune conformité mondiale automatique. |
| Capacité et disponibilité | Charge mesurée, RPO/RTO, sauvegarde indépendante, alertes et exercices de restauration. |

Les admissions, sanctions, notes définitives et diplômes restent soumis à une
décision humaine autorisée. Un indicateur de décrochage ne doit pas produire
automatiquement une exclusion ou une décision défavorable.

## 12. Sources du bilan dans le dépôt

Ce plan s'appuie sur le code actuel, le guide d'installation et les recettes
déjà réalisées, et non uniquement sur les listes d'intentions historiques.

- [`INSTALLATION_ETABLISSEMENT.md`](INSTALLATION_ETABLISSEMENT.md) :
  distribution réellement installée, parcours et limites connues.
- [`compose.yaml`](../compose.yaml) et
  [`verify_installation.py`](../scripts/verify_installation.py) :
  déploiement, parcours navigateur, redémarrage et restauration.
- [`App.jsx`](../frontend-app-sis/src/App.jsx) :
  pages et espaces disponibles dans le frontend.
- [`academic_configuration.py`](../sis_common/academic_configuration.py) :
  configuration, catalogues, politiques, rapports et règles.
- [`authorization.py`](../sis_common/authorization.py),
  [`workflow_tracking.py`](../sis_common/workflow_tracking.py),
  [`notification_channels.py`](../sis_common/notification_channels.py) et
  [`reporting.py`](../sis_common/reporting.py) : mécanismes transversaux existants.
- [`ExamensPage.jsx`](../frontend-app-sis/src/superieur/examens/ExamensPage.jsx),
  [`EmploiDuTempsPage.jsx`](../frontend-app-sis/src/superieur/emploi-du-temps/EmploiDuTempsPage.jsx),
  [`PaiementsPage.jsx`](../frontend-app-sis/src/superieur/paiements/PaiementsPage.jsx) et
  [`StagesPage.jsx`](../frontend-app-sis/src/superieur/stages/StagesPage.jsx) :
  exemples de parcours encore partiels.
- [`PortailApprenantFamille.jsx`](../frontend-app-sis/src/secondaire/portails/PortailApprenantFamille.jsx) :
  base du portail élève/parent existant.
- [`diplomes/api.py`](../sis_superieur/apps/diplomes/api.py) :
  différence entre validation métier, PDF et certification cryptographique.
- [`messages.js`](../frontend-app-sis/src/i18n/messages.js) :
  base d'internationalisation à étendre à l'ensemble des écrans.

Les produits cités dans le cahier des charges sont des références fonctionnelles,
pas un engagement de reproduire leurs offres commerciales, leurs certifications
ou toutes leurs extensions. L'objectif est une plateforme cohérente et
configurable, avec des parcours fiables, plutôt qu'une addition de menus.

## 13. TODO fonctionnelle de bout en bout

Mise à jour : **4 novembre 2026**. Cette liste est un **backlog à réaliser**,
pas une déclaration de livraison. Les identifiants F01–F32 sont propres à cette
liste ; ils ne renumérotent pas les anciennes phases P0–P8.

**Acquis à conserver :** installation dual persistante, comptes et MFA,
configuration hiérarchique et offres, inscriptions/réinscriptions et transferts
simples, protections des périodes clôturées, premiers examens/publications,
journaux filtrés, réclamations privées, documents, missions et signatures
archivées, dashboards MUI 7 et charte ERP figée. Compléter leurs limites, sans recréer
ces fonctions ni effacer les dossiers existants.

**Direction produit :** Canvas/Classroom pour les actions pédagogiques,
Moodle pour les contrats d'extension, Workday/Classe365 pour les parcours
institutionnels, Brightspace/Docebo pour la progression et la personnalisation,
Blackboard pour la navigation transversale et Ellucian pour la continuité
académique. Garder Open edX comme moteur pédagogique à déployer réellement :
le pack Compose actuel ne l'installe pas. Le SIS conserve les résultats
officiels ; le LMS conserve activités/remises/progression ; l'ERP conserve
comptabilité/paie. Ne pas installer plusieurs LMS pour reproduire ce benchmark.

### Règles d'exécution et jalons

- Les cases restent ouvertes jusqu'à la validation du résultat, pas seulement
  jusqu'à la création d'un écran ou d'une API. Les dépendances ci-dessous
  sont des prérequis de réalisation, pas un ordre arbitraire entre tous les lots.
- Commencer par F01, puis engager les fondations utiles et le déploiement LMS.
  Avancer par parcours verticaux : données, règles, permissions, interface,
  erreurs, historique et recette dans le même incrément.
- **Premier jalon SIS–LMS :** inscription autorisée → accès à un vrai cours →
  remise d'un travail → correction avec retour → validation humaine →
  publication dans le dossier. Il mobilise F02–F09 et les règles de F12–F13 ;
  F10 donne ensuite une expérience unifiée. Ce jalon ne termine pas le produit.
- **Cible institutionnelle complète :** F01–F31 validés pour les packs annoncés,
  puis F32 accepté. Les lots avancés restent dans la TODO ; ils ne deviennent
  pas « terminés » parce qu'ils sont désactivés dans un premier pilote.
- Une livraison intermédiaire annonce exactement ses modules disponibles.
  Aucune fonction absente n'est présentée comme utilisable. Pas de migration
  destructive, de fusion de comptes automatique ni de réinitialisation du MFA.
- Droits, accessibilité, journalisation, migrations et exploitation sont
  transversaux dès chaque lot ; F30 consolide leur recette, sans la remplacer.
  Pas de nouvelle refonte graphique : conserver exactement le cadre ERP/MUI 7
  livré, y compris les pages hors dashboards.

### A. Cadrer et consolider les fondations

- [x] **F01 — Fixer la matrice de couverture et de recette.**
  Réconcilier les 20 domaines avec les incréments livrés ; classer chaque
  parcours en livré/partiel/absent/non applicable au pack. Définir acteurs,
  pays/règles pilotes, données, volumes, critères d'acceptation et responsabilités.
  **Sortie :** chaque exigence correspond à un scénario positif et aux refus
  importants, sans annoncer un profil complet sur la seule base d'un réglage.
  **Prérequis :** aucun.
  **Livrable :** matrice de la section 14 ; les validations institutionnelles,
  pays et objectifs de charge non fournis restent explicitement réservés à F32.
- [ ] **F02 — Compléter identité, affiliations et habilitations.**
  Relier SIS/LMS par identifiants stables ; traiter multi-rôles, campus,
  relations parent/enfant et enseignant/groupe, départs et accès temporaires des
  stagiaires/partenaires. Préparer la fédération en conservant comptes et MFA.
  **Sortie :** création, changement de fonction et révocation fonctionnent ;
  les accès directs hors périmètre sont refusés. Pas de fusion par seul email.
  **Prérequis :** F01.
- [ ] **F03 — Étendre les contrats de modules et d'intégration.**
  Compléter le registre au-delà des trois entrées actuelles : dépendances,
  permissions, versions/migrations, activation et conservation. Formaliser
  API/événements, identifiants externes, idempotence, reprises et réconciliation ;
  qualifier les extensions tierces hors du processus Django.
  **Sortie :** mise à jour, désactivation/réactivation et rejeu sans perte,
  doublon ou contournement des droits ; catalogue privé effectivement installable.
  **Prérequis :** F01.
- [ ] **F04 — Compléter les règles, formulaires et circuits configurables.**
  Réutiliser la configuration héritée et les transitions existantes ; ajouter
  paramètres utiles, champs typés/conditionnels, étapes, responsables, délais,
  délégations et simulations. Conserver la version applicable au dossier.
  **Sortie :** admission et soutenance exécutent des configurations distinctes
  du même mécanisme ; une nouvelle règle ne réécrit pas les dossiers engagés.
  **Prérequis :** F02, F03.
- [ ] **F05 — Compléter protection des données, fichiers et journaux.**
  Étendre les filtres acteur/date/périmètre et la traçabilité des nouveaux
  métiers ; ajouter analyse antivirus/quarantaine, quotas, stockage privé,
  consentements et conservation/purge contrôlée selon le pack.
  **Sortie :** aucun téléchargement avant autorisation/contrôle requis,
  exports tracés, erreurs explicites et exercice des droits documenté ;
  les preuves réglementaires ne sont pas supprimées arbitrairement.
  **Prérequis :** F02.

### B. Rendre le LMS réellement utilisable

- [ ] **F06 — Déployer un vrai Open edX/Studio compatible.**
  Qualifier une distribution maintenue et son intégration avec le SIS sur
  environnement isolé : ressources, versions, domaines, TLS, stockage,
  configuration, sauvegarde et procédure reproductible.
  **Sortie :** Studio publie un cours accessible à un apprenant après
  redémarrage ; aucune modification de l'installation utilisateur sans sauvegarde.
  **Prérequis :** F01.
- [ ] **F07 — Raccorder connexion, utilisateurs, cours et inscriptions.**
  Brancher le SSO et les mappings/outbox existants sur le vrai LMS ; gérer
  enseignants, inscriptions, changements de groupe, suspensions et départs.
  Rendre visibles les erreurs, états de synchronisation et reprises.
  **Sortie :** un compte autorisé accède à ses seuls cours ; une coupure puis
  un rejeu ne crée ni compte ni inscription en double.
  **Prérequis :** F02, F03, F06.
- [ ] **F08 — Compléter les parcours cours et activités.**
  Relier Studio, sections/modules, ressources, vidéos, quiz, devoirs,
  consignes, pièces, échéances, tentatives, discussions et travaux collectifs
  selon les capacités LMS retenues ; gérer brouillon/publication et droits.
  **Sortie :** un enseignant publie une activité, un apprenant la réalise
  et remet un travail, sans bouton factice ni contournement par l'admin technique.
  **Prérequis :** F05, F07.
- [ ] **F09 — Relier correction et résultat officiel.**
  Fournir copie, barème/rubrique, feedback et nouvelle remise selon les règles ;
  lier l'activité à l'évaluation SIS et traiter doublons, corrections et conflits.
  **Sortie :** un résultat LMS passe par la validation autorisée avant
  publication ; un événement tardif ne remplace pas une note officielle clôturée.
  **Prérequis :** F05, F08, F13.
- [ ] **F10 — Compléter les espaces pédagogiques et les tâches.**
  Ajouter « Mes cours », « Reprendre », travaux à rendre/à corriger, progression
  sourcée et agenda commun ; relier chaque action à son vrai dossier.
  Alléger les parcours enseignant/apprenant/parent plutôt que multiplier les menus.
  **Sortie :** échéances, compteurs et actions correspondent aux données réelles,
  sur ordinateur/mobile, avec chargements, erreurs et accès cohérents.
  **Prérequis :** F09, F14, F17.

### C. Terminer le cycle académique

- [ ] **F11 — Construire le parcours candidat complet.**
  Ajouter campagnes, formulaire public maîtrisé, pièces, vérification,
  compléments, concours/entretiens si applicables, décisions motivées et suivi ;
  convertir la candidature acceptée en dossier/inscription sans ressaisie.
  **Sortie :** candidature → décision → inscription rejouable sans doublon ;
  refus, pièces manquantes et admissions hors période sont explicitement traités.
  **Prérequis :** F04, F05.
- [ ] **F12 — Compléter programmes et changements de parcours.**
  Étendre classes/formations, années/périodes, groupes et inscriptions
  pédagogiques aux profils annoncés ; traiter équivalences, suspension,
  abandon, réorientation et transfert avec décisions et conservation des acquis.
  **Sortie :** changement de filière/réinscription depuis une année close
  sans modifier ses résultats ; aucun ajout dans une période verrouillée.
  **Prérequis :** F04, F05.
- [ ] **F13 — Finaliser calculs, examens, jurys et publications.**
  Qualifier coefficients, arrondis, absences, rattrapages, compensation,
  compétences/crédits, passage, jurys, PV, rectification et publication.
  Étendre les règles historisées plutôt que remplacer les circuits existants.
  **Sortie :** résultat reproductible à partir des règles applicables,
  validation nominative et documents cohérents ; aucun brouillon visible
  aux apprenants ni modification silencieuse après clôture.
  **Prérequis :** F04, F12.
- [ ] **F14 — Compléter emplois du temps, présences et remplacements.**
  Consolider les deux variantes : salles/capacités, enseignants/groupes,
  chevauchements, vacances, annulations, replanification, appel et justificatifs.
  **Sortie :** conflits refusés ou arbitrés explicitement, emploi du temps
  cohérent et changements notifiés aux bonnes personnes.
  **Prérequis :** F04, F12.

### D. Relier les services de l'établissement

- [ ] **F15 — Terminer la finance côté établissement et famille.**
  Raccorder tarifs, factures, bourses/réductions, échéanciers, paiements
  partiels, reçus, impayés, annulations/remboursements et validations.
  **Sortie :** inscription → facture → encaissement → reçu → solde exact,
  avec séparation des responsabilités, historique et absence de double opération.
  **Prérequis :** F04, F12.
- [ ] **F16 — Intégrer paiements et ERP avec rapprochement.**
  Choisir les prestataires du pays pilote ; connecter banque/mobile money
  et comptabilité/paie selon le périmètre, avec signatures des callbacks,
  références externes, devises explicites et reprise sur incident.
  **Sortie :** succès, échec, attente, doublon et remboursement rapprochés ;
  aucune facture déclarée payée sur le seul retour du navigateur.
  **Prérequis :** F03, F05, F15. Accès prestataires et validation comptable requis.
- [ ] **F17 — Compléter communications et portail familles.**
  Relier annonces, conversations autorisées, notifications et calendrier ;
  qualifier e-mail, SMS, push et WhatsApp autorisé avec leurs fournisseurs réels
  et leurs reprises. Ajouter consentements,
  autorisations et suivi multi-enfants selon les relations accordées.
  **Sortie :** destinataires exacts, contenu privé, échecs visibles et aucun
  élargissement implicite des droits d'un parent ou partenaire.
  **Prérequis :** F02, F03, F05.
- [ ] **F18 — Terminer stages, mémoires, soutenances et recherche.**
  Relier offres/candidatures, convention, tuteurs, missions temporaires,
  suivi, livrables, évaluation, jury, décision et archivage.
  **Sortie :** un dossier traverse toutes les étapes ; le partenaire n'accède
  qu'à sa mission et perd cet accès à son expiration/révocation.
  **Prérequis :** F04, F05, F12.
- [ ] **F19 — Compléter personnel, RH et gouvernance.**
  Relier recrutement/dossier, postes, contrats, affectations, charges,
  disponibilités, congés/remplacements, formation et décisions institutionnelles.
  Intégrer la paie à l'ERP retenu plutôt que recoder une législation salariale.
  **Sortie :** circuit RH utilisable par ses seuls responsables, charges
  cohérentes et données échangées/rapprochées avec le système retenu.
  **Prérequis :** F02, F04, F05, F16.
- [ ] **F20 — Compléter vie scolaire, bibliothèque et ressources.**
  Terminer prêts/retours/réservations, clubs/discipline/événements et, selon
  le pack, cantine, transport, internat, équipements, inventaire et maintenance.
  Raccorder demandes d'achat, validations, fournisseurs/offres, commandes,
  réceptions, factures et règlements avec mouvements de stock traçables.
  Relier capacités, autorisations, réservations et frais sans dossiers parallèles.
  **Sortie :** chaque service annoncé possède son parcours complet,
  ses contrôles de conflit/stock/capacité et ses responsables.
  **Prérequis :** F05, F12, F14, F15.
- [ ] **F21 — Compléter les réclamations existantes.**
  Ajouter services responsables, délais/relances, politique de recours,
  délégations parentales et conservation des pièces ; relier une décision
  favorable au circuit de rectification autorisé, sans modification automatique.
  **Sortie :** recours suivi jusqu'à résolution avec notification,
  confidentialité et conservation du résultat/dossier initial.
  **Prérequis :** F04, F05, F17.
- [ ] **F22 — Compléter documents officiels, diplômes et Alumni.**
  Relier calculs complets, gabarits, filtres année/période, génération asynchrone,
  diplômes, conditions d'obtention, archives et portefeuille personnel.
  Étendre signature/vérification/révocation existantes avec URL institutionnelle
  et QR minimal ; qualifier le prestataire si une garantie juridique est requise.
  **Sortie :** document exact, versionné, téléchargeable par son bénéficiaire ;
  vérification sans fuite de dossier et statut de révocation à jour.
  **Prérequis :** F04, F05, F13.

### E. Ajouter les capacités transversales avancées

- [ ] **F23 — Compléter recherche, exports et pilotage.**
  Ajouter recherche globale autorisée, filtres structurés, rapports enregistrés,
  exports CSV/XLSX/PDF/JSON adaptés, tâches volumineuses et historique.
  Définir provenance, formule, période et fraîcheur des indicateurs.
  **Sortie :** rapports académiques/financiers réconciliables avec les sources ;
  aucune donnée hors périmètre, aucune limite de pagination silencieuse.
  **Prérequis :** F03, F05, F09, F16, F22.
- [ ] **F24 — Qualifier les standards et connecteurs retenus.**
  Prioriser LTI 1.3 et calendriers ; ajouter selon les packs OneRoster/Edu-API,
  QTI/SCORM, xAPI/CASE/Caliper, Open Badges/CLR, vidéo et fonds documentaires.
  Inclure OneRoster, Caliper Analytics et W3C Verifiable Credentials du cahier ;
  distinguer badges internes et justificatifs réellement conformes.
  Déclarer versions, sens des échanges et limites ; ne pas présumer du support
  natif de tous les standards par Open edX.
  **Sortie :** échanges réussis avec outils de conformité/systèmes partenaires,
  erreurs et rejeux observables ; aucune conformité annoncée sans preuve.
  **Prérequis :** F03, F08, F22. Partenaires et licences éventuelles à qualifier.
- [ ] **F25 — Construire progression et recommandations explicables.**
  Relier compétences/objectifs, prérequis, activités et acquis validés ;
  proposer un prochain travail ou parcours avec sa justification.
  **Sortie :** progression calculée sur des événements réels, recommandation
  compréhensible et absence de sanction ou classement opaque automatique.
  **Prérequis :** F08, F13, F23.
- [ ] **F26 — Ajouter une IA pédagogique supervisée.**
  Commencer par recherche documentaire permissionnée avec sources, puis
  brouillons de contenus/QCM, résumés/traductions et aide pédagogique/correction.
  Ajouter l'OCR avec préremplissage proposé et vérification humaine avant
  enregistrement officiel ; aucun document sensible transmis sans autorisation.
  Prévoir consentement lorsque requis, exclusions, évaluation, coûts et arrêt.
  **Sortie :** réponses sourcées évaluées, frontières tenant/rôle respectées,
  indisponibilités explicites et validation humaine avant toute décision officielle.
  **Prérequis :** F05, F25. Fournisseur/hébergement et données autorisées requis.
- [ ] **F27 — Compléter mobile, accessibilité et packs institutionnels.**
  Qualifier clavier/lecteur d'écran, responsive, traductions, fuseaux et formats ;
  compléter les scénarios primaire, secondaire, supérieur, professionnel et
  autres profils annoncés. Ajouter une PWA/hors ligne seulement sur les données
  autorisées, avec conflits, expiration et révocation explicitement traités.
  Qualifier également la distribution Android/iOS demandée, sans présenter
  une simple page responsive comme une application mobile native livrée.
  **Sortie :** tâches prioritaires réalisables sur mobile et connexion faible ;
  aucune promesse de conformité universelle ni cache sensible incontrôlé.
  **Prérequis :** F05, F10, F15, F22.
- [ ] **F28 — Compléter administration réseau et provisioning.**
  Ajouter console plateforme distincte du tenant, affiliations multiples,
  périmètres campus/établissement, packs/configurations et gestion des versions
  installées ; provisionner sans accès métier illimité pour l'exploitant.
  Gérer plans, essais, licences, quotas, renouvellements, suspension/réactivation
  et facturation des établissements, distincte des frais des apprenants.
  Une suspension ne supprime pas les dossiers ni leurs preuves officielles.
  **Sortie :** créer, mettre à jour et suspendre un établissement sans exposer
  les autres ni supprimer ses dossiers ou archives.
  **Prérequis :** F02, F03, F04, F05, F06.

### F. Qualifier et livrer une installation exploitable

- [ ] **F29 — Compléter installation et exploitation de l'ensemble.**
  Étendre les scripts existants au vrai LMS et aux connecteurs ; vérifier
  prérequis/ressources, secrets, domaines/TLS, installation neuve, montée de
  version, sauvegarde hors machine, restauration cohérente SIS/LMS/fichiers,
  alertes, files en erreur, capacité et procédures d'incident.
  **Sortie :** installation et mise à jour reproductibles, panne/reprise
  exercées, restauration mesurée selon RPO/RTO retenus et diagnostic utilisable.
  **Prérequis :** F05, F06, F28.
- [ ] **F30 — Exécuter la recette complète et corriger les écarts.**
  Utiliser données isolées et comptes distincts pour chaque rôle ; couvrir
  les deux variantes, les profils annoncés et les offres mixtes, puis refus,
  clôtures, doublons, concurrence, coupures, migrations, accessibilité,
  charge et contrôle indépendant des accès/confidentialité.
  **Sortie :** chaque parcours annoncé possède ses preuves ; pas d'anomalie
  critique ouverte, de succès factice ni de modification des données utilisateur.
  **Prérequis :** F10, F11, F16, F18, F19, F20, F21, F22, F24, F26, F27, F29.
- [ ] **F31 — Livrer la version documentée et reproductible.**
  Finaliser guides installation/mise à jour/restauration et guides par rôle,
  données de démonstration séparées, notes de version, limites connues,
  support, formation et procédure de retour arrière ; produire les artefacts
  versionnés et déployer d'abord dans l'environnement autorisé.
  **Sortie :** installation neuve et mise à jour depuis la version conservée
  préservent comptes, MFA et dossiers ; les utilisateurs réalisent leurs tâches
  courantes sans console technique.
  **Prérequis :** F30.
- [ ] **F32 — Faire accepter le pilote institutionnel réel.**
  Réutiliser la tâche existante `external-pilot`, toujours **bloquée** :
  infrastructure/domaines autorisés, prestataires et référents métier nécessaires.
  Faire exécuter les scénarios par scolarité, enseignants, apprenants/familles,
  comptabilité et exploitation ; consigner écarts, formation et décision d'ouverture.
  **Sortie :** acceptation institutionnelle, restauration et alertes réelles
  démontrées ; aucun label « prêt pour la production » sur la seule recette locale.
  **Prérequis :** F31 et levée des dépendances externes.

### Définition finale de « tout fonctionnel »

Une fonction est terminée quand le rôle prévu peut l'exécuter de bout en bout
dans l'installation livrée, avec données persistantes, refus corrects, erreurs
visibles et preuves de recette. Un établissement doit pouvoir être installé,
configuré, exploité, mis à jour et restauré avec la documentation fournie.
Un champ, une liste, une API ou un écran isolé ne suffit pas.

La couverture est explicitement limitée aux packs, pays, prestataires, versions
et volumes qualifiés en F01/F30/F32. Étendre cette couverture exige une nouvelle
qualification ; ni cette TODO ni la présence d'un profil ne prouvent que tous
les établissements du monde sont déjà pris en charge.

## 14. Matrice de réalisation et de recette F01

Base de travail : code local du **4 novembre 2026**, incréments déjà livrés
compris. « Partiel » signifie qu'un acquis fonctionne mais que la cible du
domaine n'est pas complète ; ce n'est ni une absence ni une homologation.

| Domaine | Base actuelle | Scénario de sortie et refus indispensable | Lots |
|---|---|---|---|
| D01 Organisation | Partiel : tenants, unités, offres et héritage | Configurer deux établissements sans fuite entre eux ; respecter les verrous et droits campus. | F02, F04, F28 |
| D02 Apprenants | Partiel : dossiers, inscriptions et historique | Admission, réinscription et transfert sans doublon ; refuser une transition incohérente ou une mutation des années closes. | F11, F12 |
| D03 Personnel | Partiel : comptes, dossiers et affectations | Affectation, remplacement et départ avec droits actualisés ; refuser une consultation RH non habilitée. | F02, F19 |
| D04 Académique | Partiel : programmes, périodes et règles historisées | Administrer une offre chiffrée et une offre à compétences ; refuser prérequis non satisfaits et changements rétroactifs. | F04, F12, F13 |
| D05 Cours | Externe non déployé dans le pack SIS | Publier puis suivre une activité réelle ; refuser l'accès hors inscription ou avant publication. | F06, F07, F08 |
| D06 Évaluations | Partiel : examens et notes SIS | Remettre, corriger, valider ; refuser tentative hors fenêtre et intervention d'un correcteur non affecté. | F08, F09, F13 |
| D07 Résultats | Partiel : saisie, publications et protections | Recalculer un résultat avec sa version de règles ; aucun brouillon apprenant ni écrasement après clôture. | F09, F13 |
| D08 Calendrier | Partiel : créneaux, réservations et conflits | Replanifier et notifier ; refuser chevauchement salle/enseignant/groupe et dépassement de capacité. | F10, F14 |
| D09 Finance | Partiel : modèles/API et consultation | Facturer, payer partiellement, rembourser et rapprocher ; rejeter callback invalide et encaissement double. | F15, F16 |
| D10 Communication | Partiel : notifications et suivi de livraison | Annoncer/échanger avec les seuls destinataires autorisés ; rendre un échec fournisseur visible et rejouable. | F17 |
| D11 Familles | Partiel : enfants autorisés et portails | Suivre devoirs, justificatifs et démarches ; refuser l'accès à un enfant sans relation/délégation valable. | F02, F10, F17 |
| D12 Bibliothèque | Partiel : catalogue, emprunts et réservations | Prêter, réserver et retourner ; refuser exemplaire indisponible et emprunt hors droits. | F20 |
| D13 Vie scolaire/recherche | Partiel : listes et circuits spécialisés | Stage/soutenance jusqu'à décision et archivage ; refuser accès partenaire expiré et validation sans mandat. | F18, F20 |
| D14 Ressources | Partiel : salles et premiers services | Réserver/affecter un équipement ou une place ; refuser double réservation et dépassement de stock/capacité. | F14, F20 |
| D15 Admissions | Partiel : décisions et réinscriptions ; pas tout le portail candidat | Candidature avec pièces puis conversion unique ; refuser dossier incomplet et période close. | F11 |
| D16 Certifications | Partiel : documents et circuit de signature archivée | Obtenir et vérifier un diplôme autorisé ; refuser signature révoquée et accès public aux données privées. | F22, F24 |
| D17 RH/gouvernance | Partiel : personnel, rôles et historique | Valider un acte RH et le rapprocher avec l'ERP ; refuser auto-approbation lorsque la séparation est requise. | F19 |
| D18 Reporting | Partiel : compteurs, filtres et exports | Rapprocher indicateurs et sources, exporter toutes les lignes autorisées ; refuser dépassement de périmètre/coût. | F23 |
| D19 Protection/exploitation | Partiel : MFA, droits, journaux, sauvegardes | Révoquer un accès, contrôler un fichier et restaurer ; refuser données intertenant et téléchargement non contrôlé. | F02, F05, F29, F30 |
| D20 IA | Absent des parcours SIS intégrés | Réponse sourcée et suggestion validable ; refuser données hors rôle/tenant et décision académique automatique. | F25, F26 |

### Packs et responsabilités de recette

- Socle de non-régression : secondaire et supérieur, comptes élève/étudiant,
  famille, enseignant, scolarité/direction, administrateur et comptes sans droit.
  Ajouter comptable, RH, bibliothécaire, partenaire et auditeur au lot correspondant.
- Configurations déjà représentables : primaire, secondaire, supérieur,
  professionnel et offres mixtes. Leur prise en charge complète exige les
  parcours et preuves de F27/F30 ; les autres profils restent des extensions
  à qualifier, pas des capacités automatiquement acquises.
- Les référents scolarité/examens approuvent les calculs et transitions ;
  comptabilité/RH approuvent leurs écritures et décisions ; exploitation approuve
  reprise et alertes ; le responsable des données approuve accès et conservation.
  Aucun nom, pays ou prestataire non fourni n'est inventé.
- Les jeux automatisés restent synthétiques et isolés de l'installation
  utilisateur. Les règles de pays, taxes/devises, charge nominale, disponibilité,
  RPO/RTO et durées de conservation seront validés avant F32. Les essais locaux
  ne constituent pas une garantie de charge ni une validation juridique.

### Preuves et premier ordre de réalisation

Réutiliser les recettes `e2e/institution.e2e.js`, `workspace.e2e.js`,
`hierarchy.e2e.js`, `design.e2e.js` du frontend, les tests tenant des deux SIS
et les tests partagés de `sis_common/tests`. Chaque lot ajoute uniquement les
cas introduits/corrigés et les rapproche de cette matrice. Un lot avancé
ne peut pas être déclaré livré sur la seule présence d'un test simulant
un prestataire encore non raccordé.

Après F01, F02, F03 et F06 peuvent commencer indépendamment. F06 utilise une
distribution Tutor maintenue et isolée du Compose SIS ; ses prérequis matériels
sont contrôlés avant lancement. Les contrats de F02/F03 sont ensuite raccordés
au vrai LMS en F07, sans convertir les comptes ou données de l'installation
existante en données de démonstration.
