# Plan directeur : de LMS_SIS à la plateforme éducative cible

Date du bilan : **2 novembre 2026**. Référence du code examiné : **`b9ad1b9`**.

Ce plan répond aux deux documents fournis par le demandeur, qui sont identiques.
Ils définissent 20 domaines fonctionnels, huit familles d'établissements et sept
piliers : SIS, LMS, ERP, IA, certifications, intégrations, gouvernance.
Ce document est un planning proposé, pas l'annonce de fonctionnalités déjà livrées.

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

Les phases **P1 à P6** sont détaillées plus bas. Un domaine peut traverser
plusieurs phases ; cela évite de considérer un module comme « terminé » après
la seule livraison de ses premières listes.

| # | Domaine et état | Déjà présent | Reste pour atteindre la cible | Phases |
|---|---|---|---|---|
| D01 | Établissements et organisations — **Partiel** | Tenants, années/périodes, structures, modules ; offres mixtes avec simulation et raccordement aux classes/formations, inscriptions et contrôle continu. | Gouvernance de réseaux, hiérarchie groupe/campus/annexe, provisioning, partenaires, déclinaisons pays et capacités mesurées. | P1, P6 |
| D02 | Apprenants — **Partiel** | Dossiers élèves/étudiants, matricules, liens familiaux, imports et inscriptions. | Identité pérenne inter-systèmes, cycle préinscription/réinscription/transfert/suspension/abandon, dossier documentaire complet, historique consolidé et Alumni. | P2, P5, P6 |
| D03 | Enseignants et personnel — **Partiel** | Comptes, dossiers et affectations ; création de personnel dans le parcours secondaire. | Recrutement, contrats, disponibilités et charges cohérentes, congés/remplacements, compétences, formation continue et évaluations professionnelles. | P2, P4 |
| D04 | Pédagogie et académique — **Partiel** | Classes/matières, formations, UE/ECUE, maquettes, crédits, prérequis et configuration de règles. | Parcours entièrement administrables, référentiels de compétences/objectifs, équivalences, règles locales versionnées et simulables, progression pédagogique reliée au LMS. | P1, P2, P3 |
| D05 | Cours et contenus LMS — **Externe / à intégrer** | Code Open edX dans le dépôt ; mappings et mécanismes d'intégration SIS. Le pack Compose ne déploie pas le LMS. | Distribution Open edX compatible, parcours Studio/apprenant unifié, cours multimédias, ressources interactives, forums, projets/équipes, parcours conditionnels, versions et bibliothèques partagées. | P3 |
| D06 | Évaluations et examens — **Partiel + externe** | Saisie d'évaluations et notes ; API de sessions, épreuves, convocations, résultats et correction anonymisée. | Relier création, soumission, correction, jury et publication ; devoirs/remises/rubriques ; banque de questions/QCM via LMS ; gestion des examens physiques/oraux/pratiques, PV, antivirus des dépôts. Surveillance distante seulement après choix juridique et pédagogique. | P2, P3, P5 |
| D07 | Notes et bulletins — **Partiel** | Saisie transactionnelle de notes/compétences/décisions simples en contrôle continu, règles historisées ; modèles/API de moyennes, bulletins, crédits et rattrapages ; PDF. | Qualifier coefficients, arrondis, absences, compensation, classement et passages ; agrégation des compétences, carnet enseignant, validations avant publication et rectifications. | P2, P3, P5 |
| D08 | Emplois du temps — **Partiel** | Créneaux/salles, vues de consultation, contraintes et endpoint de détection de conflits ; création secondaire. | Achever les actions supérieures, tester tous les chevauchements, calendriers unifiés, événements, remplacements, planification hybride/multi-campus et affectation automatique. | P2, P4, P6 |
| D09 | Finance — **Partiel** | Frais, factures, paiements, bourses et workflows de validation/remboursement côté API ; interface de consultation. | Parcours de facturation/encaissement complet, réductions/échéanciers, paiements partiels, reçus, dettes, connecteurs bancaires/mobile money, rapprochement, multidevise, comptabilité/budget/dépenses et paie via ERP. | P4, P6 |
| D10 | Communication — **Partiel** | Notifications in-app, email, SMS et webhook ; préférences et suivi de livraison dans le socle. | Qualifier les fournisseurs réels ; messagerie et annonces, conversations autorisées, notifications push/temps réel, urgences, calendrier partagé, traduction assistée et politique de conservation. | P2, P3, P4, P6 |
| D11 | Parents et tuteurs — **Partiel** | Portail secondaire avec enfants autorisés, notes/absences et factures ; portail apprenant supérieur. | Justificatifs et autorisations de sortie, devoirs, communication enseignants, paiement en ligne, consentements et délégations ; parcours complets avec comptes parents réels. | P2, P3, P4 |
| D12 | Bibliothèque — **Partiel** | Modèles/API d'ouvrages, exemplaires, emprunts et réservations ; écran supérieur. | Interfaces complètes emprunt/retour/réservation, pénalités, fonds numérique, licences, accès documentaires scientifiques, archives et connecteurs spécialisés. | P4, P6 |
| D13 | Vie scolaire/universitaire — **Partiel** | Présences, discipline, clubs et conseils ; modèles/API et écrans pour stages, mémoires, soutenances, recherche et mobilité. | Finaliser les parcours de bout en bout, récompenses/sports/associations/événements, placement en stage, conventions, signatures, encadrement et publication des décisions. | P2, P4, P5 |
| D14 | Ressources et infrastructures — **Partiel** | Salles ; transport, cantine, internat et équipements décrits dans certaines données métier. | Capacités/réservations sans conflits, inventaire et maintenance, parc informatique/laboratoires, logements universitaires, coûts logistiques et contrôle d'accès via connecteurs. | P4, P6 |
| D15 | Admissions — **À construire comme parcours complet** | Les inscriptions et dossiers permettent de réutiliser les données de l'apprenant après admission. | Portail candidat, campagnes/formulaires, pièces, vérification, concours/tests, entretiens, classement, décisions, notifications et conversion en inscription sans double saisie. | P2 |
| D16 | Diplômes et certifications — **Partiel** | Diplômes, attestations/relevés, PDF, numéro de série, date/signataire et action de vérification. | Signature cryptographique, registre vérifiable/révocable, vraie URL publique et QR, équivalences, Open Badges/CLR et portefeuille de compétences. | P2, P5 |
| D17 | RH et gouvernance — **Partiel** | Personnel, rôles, groupes d'accès, validations et historique de certaines décisions. | Postes/organigrammes, processus RH, contrats et paie, conseils d'établissement, séparation des responsabilités et rapports de gouvernance ; intégrer un ERP plutôt que recréer la législation salariale. | P1, P4, P5 |
| D18 | Reporting et BI — **Partiel** | Tableaux de bord, statistiques et rapports configurables sur des jeux de données connus ; exports CSV/XLSX/PDF. | Définitions d'indicateurs fiables, constructeur de rapports utilisable, tableaux personnalisés, données financières consolidées, entrepôt analytique, comparaisons interétablissements autorisées et prédiction évaluée. | P2, P4, P5 |
| D19 | Sécurité et conformité — **Partiel, socle livré** | Authentification locale, fédération prévue, MFA TOTP, RBAC et ABAC léger, journaux, chiffrement de champs, sauvegardes/restauration. | Qualification complète des périmètres et relations, SoD, MFA imposé selon politique et secours, consentements, droits sur les données, rétention/purge, incidents, supervision réelle, audit indépendant et règles par pays. | Toutes |
| D20 | IA éducative — **À construire** | Aucun parcours intégré d'assistance IA SIS identifié dans le périmètre examiné. | Assistants par rôle, recherche documentaire, résumés/traduction, cours/QCM/devoirs assistés, aide à la correction, tutorat/recommandations, rapports et détection de difficultés ; contrôle humain, évaluation et confidentialité obligatoires. | P5, P6 |

### Écarts concrets qui empêchent de déclarer ces domaines terminés

- `ExamensPage.jsx` présente « Planifier un examen » sans action attachée.
- L'emploi du temps supérieur présente « Nouveau créneau » sans action attachée.
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

| Sujet | Proposition |
|---|---|
| Noyau métier | Conserver Django, les deux variantes et `sis_common` pendant la transition. Identifier les doublons, extraire progressivement des services partagés et maintenir la compatibilité des données/API. Un noyau configurable est une cible, pas l'état actuel. |
| LMS | Garder Open edX comme moteur de contenu, quiz et progression ; qualifier la version de déploiement, Studio et les interfaces apprenantes nécessaires. Ne pas reconstruire son moteur d'évaluation dans le SIS. |
| Source de vérité | SIS : personnes, affiliations, inscriptions et résultats officiels. LMS : activités, remises et progression. ERP : écritures comptables/paie. Documenter les responsabilités et règles de résolution des conflits. |
| Frontend | Conserver React ; introduire TypeScript progressivement dans les composants modifiés et rationaliser MUI/Paragon. Mettre l'accessibilité et la cohérence des interfaces avant une réécriture esthétique. |
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
| **P1 — Foundation Core** | Critique ; 6–10 semaines, à rechiffrer après cadrage | Noyau configurable multi-profils, identité, permissions et exploitation | Après P0. Sortie : quatre configurations de référence, offres mixtes et isolation vérifiées. |
| **P2 — SIS Core** | Critique ; 10–16 semaines | Candidat → inscription → scolarité → résultats | Après les contrats P1. Sortie : parcours métier par rôle terminé sans intervention technique normale. |
| **P3 — LMS Core** | Critique ; 8–14 semaines | Cours → activité → remise → correction → résultat SIS | Après identité/configuration P1 et contrats d'inscription P2 ; peut chevaucher la fin de P2. |
| **P4 — ERP et administration** | Haute ; 12–20 semaines | Finance et services institutionnels intégrés | Après identité et dossiers stabilisés ; dépend des fournisseurs et règles comptables. |
| **P5 — Intelligence et interopérabilité** | Haute puis évolutive ; 12–20 semaines pour un premier lot | Connecteurs, certifications vérifiables, BI et premiers assistants | Après contrats/données fiables ; les standards de base sont conçus dès P1/P3. |
| **P6 — Écosystème mondial** | Extension ; 16–32 semaines par premier lot structurant | Mobile/hors ligne, profils/pays supplémentaires et extensions | Après stabilisation du noyau ; plusieurs vagues et maintenances réglementaires nécessaires. |

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
- [ ] Livrer le premier socle des moteurs workflow/règles/formulaires :
  définitions versionnées et contrat de simulation, sans attendre la phase IA.
- [ ] Fixer les contrats d'événements, idempotence et versions nécessaires au
  futur hors ligne ; ne pas développer tout le mobile à ce stade.
- [ ] Définir stockage documentaire, analyse antivirus, rétention et suppression.
- [ ] Industrialiser installation, mises à jour, migrations, retour arrière,
  images distribuables, sauvegardes hors machine et alertes.
- [ ] Adopter une base UI accessible, internationalisable et cohérente.

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
