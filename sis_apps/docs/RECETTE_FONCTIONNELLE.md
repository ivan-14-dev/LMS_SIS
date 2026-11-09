# Recette fonctionnelle du cahier universel

État documentaire actualisé le **5 novembre 2026**. Ce bilan accompagne le
[plan directeur et son protocole de preuve](PLAN_DIRECTEUR_LMS_SIS.md#boucle-de-réalisation-et-critères-de-preuve),
sans créer un nouveau backlog ni modifier les lots F01–F32.

## Checklist de livraison intermédiaire F30 F31

Ajout du **9 novembre 2026** ; les bilans suivants, dont la première matrice
du 5 novembre, restent historiques. Le bilan courant est **7 vérifiées,
66 partielles, 19 absentes et 2 non vérifiées sur 94** ; voir la
[synthèse et les limites](RESTE_A_FAIRE_ET_VALIDATION.md#synthèse-de-livraison-institutionnelle--9-novembre-2026).
Cette checklist complète la recette existante, **sans valoir exécution ni
clôture de F30/F31/F32**. Elle s'applique à une livraison limitée explicitement
décrite ; une option désactivée ne devient pas une exigence terminée.

### Avant toute installation ou ouverture

- [ ] Le responsable de réception identifie la variante, l'établissement,
  les fonctions **ouvertes/exclues**, les rôles, les règles de résultats et les
  intégrations retenues. Il distingue environnement de démonstration, cible de
  recette et cible d'exploitation. Aucun domaine ou prestataire n'est supposé.
- [ ] Un opérateur autorise la cible et la fenêtre ; les ressources sont
  disponibles. **Pas de recette Docker, charge ou build sur un hôte partagé
  sans accord.** Les comptes/données de recette sont fictifs et séparés.
- [ ] La version source est un commit complet conservé ; les images backend,
  frontend et, si retenu, Tutor/Open edX sont identifiées par digest. La liste
  des migrations, les versions de configuration et les modules effectivement
  actifs sont relevées sans exporter de secrets.
- [ ] Les [précontrôles d'installation et mise à jour](INSTALLATION_ETABLISSEMENT.md#mises-à-jour-et-retour-arrière)
  passent sur la cible autorisée. Une vérification de syntaxe ou un `/health/`
  vert ne prouve ni migrations terminées, ni workers, ni OAuth, ni livraison SMTP.
- [ ] Le snapshot préalable chiffré a été relu et restauré sur une cible
  indépendante, avec comptes/MFA/droits/dossiers/fichiers comparés. La sauvegarde
  du seul SIS ne couvre pas Open edX ; prévoir les deux si le périmètre les utilise.

### Parcours à faire exécuter avec les guides par rôle

Pour chaque case retenue, consigner **date, version/images, variante/tenant,
acteur, attendu/observé, refus et référence de preuve expurgée** dans le dossier
de réception privé existant. Une capture de menu ne suffit pas. Ne pas additionner
les campagnes recouvrantes en un nombre de tests uniques. Un parcours non exercé
reste « non exécuté », même si son test est présent dans le dépôt.

- [ ] **Administrateur et compte sans droit** : connexions nominatives et MFA,
  attribution/retrait minimal, refus dans la session déjà ouverte et par URL
  directe ; second tenant et autre variante sans accès indu. Tester aussi
  fichier/export/API, pas seulement la disparition d'un menu.
- [ ] **Scolarité secondaire** : année/classe → dossier élève sans affectation
  directe → inscription en attente → validation. Avant validation aucune classe
  n'est attribuée ; après validation la classe persiste après reconnexion.
  L'année close, le doublon et l'élève hors périmètre sont refusés.
- [ ] **Scolarité supérieure, si annoncée** : dossier étudiant → inscription
  administrative → inscription pédagogique/semestre ; conservation des acquis
  et refus des transitions non prises en charge. La recette secondaire ne
  couvre pas automatiquement ce parcours.
- [ ] **Enseignant et élève secondaire** : évaluation → note présente **16,5/20**
  dans un jeu fictif → consultation personnelle. Note hors barème refusée ;
  absence/non rendu/manquant non remplacé par zéro. Préserver les notes d'autrui.
- [ ] **Gestionnaire de bulletins et élève** : préparer le bulletin, contrôler
  sources/coefficients, valider, publier puis télécharger le PDF. Avant
  publication, élève et compte voisin ne lisent ni brouillon ni PDF.
  Publication sans validation et sources périmées refusées ; le PDF publié
  contient la note et les appréciations attendues. Recalculer un brouillon
  invalide sa validation ; aucune mutation silencieuse d'un bulletin publié.
  Ce scénario possède déjà une preuve dans la démonstration du 9 novembre :
  il doit être revérifié pour la version et la cible d'une nouvelle livraison.
- [ ] **Famille, comptabilité, LMS et modules facultatifs, si annoncés** :
  appliquer les limites du [guide utilisateurs](GUIDE_UTILISATEURS.md).
  Tester enfant lié puis lien retiré ; paiement rapproché et rejeu fournisseur ;
  cours réel autorisé puis accès retiré ; module désactivé puis réactivé sans
  perte. En l'absence de fournisseur, un simulateur n'établit pas sa réception.
  Ne pas inventer une preuve commune à ces parcours différents.
- [ ] **Accessibilité et mobile sur chaque parcours ouvert** : tout réaliser
  au clavier (Tab/Maj+Tab/Entrée/Échap), focus visible et retour au déclencheur
  après fermeture des dialogues ; libellés, erreurs et statut de sauvegarde
  annoncés au lecteur d'écran ; zoom 200 %, largeurs 320 et 390 px, portrait et
  paysage. Pas d'action masquée ou hors écran, de piège clavier, de message porté
  seulement par la couleur ni de défilement horizontal de la page ; un tableau
  peut défiler dans son conteneur. Répéter connexion/MFA, inscription, note,
  validation du bulletin et téléchargement, pas seulement l'accueil.
- [ ] **Perte de connexion, reprise et persistance** : conserver les erreurs,
  distinguer résultat inconnu et échec avant de rejouer une écriture. Fermer le
  navigateur, recréer les services autorisés, se reconnecter avec des comptes
  frais et rapprocher les données par lecture indépendante, sans rejouer les
  mutations métier. La restauration applicative complète est une preuve
  distincte de la restauration de la seule base.

Les recettes existantes `verify_installation.py --verify-backup` et
`frontend-app-sis/e2e/{institution,workspace,design}.e2e.js` couvrent un socle,
pas l'intégralité des cas ci-dessus ni une certification d'accessibilité.
Suivre leur préparation dans le [guide opérateur](INSTALLATION_ETABLISSEMENT.md#diagnostic-et-qualification) ;
**ne pas les lancer pour un simple contrôle documentaire**.

### Artefacts, retrait et décision

- [ ] Conserver ensemble : commit complet/version approuvée, archive de sources
  et SHA-256, digests des images, changements de schéma/configuration, modules
  actifs, limites connues, références des preuves, snapshot et procédure de
  retour arrière. Les secrets, sauvegardes et comptes privés restent hors dépôt
  et hors archive publique. Un hash identifie un artefact ; il ne certifie pas
  son fonctionnement. Aucun tag, push ou registre public n'est automatique.
- [ ] Reprendre la procédure de
  [retour arrière](INSTALLATION_ETABLISSEMENT.md#mises-à-jour-et-retour-arrière) :
  suspendre les écritures, identifier celles postérieures au snapshot, restaurer
  données **et** images compatibles dans un projet isolé, vérifier droits/MFA,
  documents et intégrations avant bascule autorisée. Ne pas remettre l'ancien
  code sur une base migrée incompatible, ni annuler une révocation récente.
- [ ] Le référent métier réalise la tâche de son rôle avec le
  [guide](GUIDE_UTILISATEURS.md), sans console technique. Identifier les contacts
  de support et d'astreinte, les règles d'escalade et la formation. L'absence de
  ces personnes bloque la réception ; un agent automatisé ne signe pas à leur place.
- [ ] Le responsable consigne « ouvert dans le périmètre décrit » ou « refusé »,
  avec exclusions et anomalies. **Aucune ouverture institutionnelle n'est
  attestée ici.** F30/F31 complets et F32 nécessitent leurs critères du
  [plan directeur](PLAN_DIRECTEUR_LMS_SIS.md#f-qualifier-et-livrer-une-installation-exploitable)
  et pas seulement cette checklist intermédiaire.

**Critères de blocage immédiat :** fuite entre personnes/tenants, droits
révoqués encore utilisables, données/MFA perdus, calcul incorrect, brouillon
exposé, double inscription/paiement, état fournisseur inconnu masqué en succès,
restauration échouée, version exécutée non identifiée, tâche essentielle
inaccessible au clavier/mobile, absence d'autorisation de cible ou de référent.
Conserver le refus et sa preuve, suspendre le parcours concerné et solliciter
l'opérateur ; ne pas corriger les données directement pour faire passer la recette.
La charge historique 500 rouge interdit d'annoncer cette capacité ou la clôture
globale. Un plafond différent ne peut pas être inventé à partir de cette campagne.

### Contrôle documentaire léger, sans service

Depuis la racine du dépôt, ces commandes ne déploient rien et ne valident pas
les parcours. Le bilan attendu est celui de cette livraison ; une promotion
future nécessite d'abord une preuve revue, pas une modification du seul compteur.

```sh
git diff --check
git rev-parse HEAD
python3 - <<'PY'
import json
from collections import Counter
from pathlib import Path

matrix = json.loads(Path("sis_apps/docs/functional-acceptance-matrix.json").read_text())
requirements = matrix["requirements"]
assert len(requirements) == len({row["id"] for row in requirements}) == 94
counts = Counter(row["status"] for row in requirements)
assert counts == {"verified": 7, "partial": 66, "absent": 19, "unverified": 2}, counts
print(dict(counts))
PY
```

## Matrice de référence

La [matrice JSON](functional-acceptance-matrix.json) conserve les exigences du
cahier fonctionnel, leurs lignes sources, comportements/champs attendus,
références de code et de tests, lacunes, critères de recette et correspondances
`f_lots`. Les identifiants `9.x`, `10.x` et `11.x` sont des repères ajoutés aux
lignes de tableaux et étapes du cahier, pas de nouvelles exigences.

**94 entrées** : 60 sous-sections des chapitres 1–8, 10 portails,
14 fonctions avancées, 9 étapes du cycle et 1 critère de cycle complet.
Le critère agrégé `11` recoupe ses étapes : ce total n'est pas un nombre de
scénarios indépendants ni un pourcentage de couverture du code.

| Statut | Nombre | Lecture |
|---|---:|---|
| `partial` | 70 | Briques identifiées, comportements ou preuves encore manquants |
| `absent` | 21 | Fonction principale non identifiée dans le périmètre inspecté |
| `unverified` | 2 | Exigences `10.10` et `11`, sans nouvelle preuve complète |
| `verified` | 1 | `1.2` : organisations internes qualifiées sur les deux SIS |
| `external_credentials_blocked` | 0 | Aucun domaine établi comme bloqué uniquement par des identifiants |

**La qualification de `1.2` ne clôt pas les autres exigences ou leurs lots.**
Les acquis et limites des incréments antérieurs restent décrits dans le plan
directeur. F01 demeure le seul lot globalement coché dans
l'état documentaire repris ; cette matrice ne rouvre ni ne clôt un lot par
simple présence de sources. Les fichiers de tests référencés ne sont pas des
comptes rendus d'exécution.

## Priorités et écarts structurants

L'ordre exact des prérequis reste celui du plan, repris dans
`f_lot_mapping`. Les liens ci-dessous désignent les entrées de la matrice.

| Exigences | Lots | Prochaine preuve attendue |
|---|---|---|
| `1.4`, `7.1`, `8.1` | F02, F03, F06, F07 | Identité, périmètres et accès au vrai LMS, avec retrait et reprise |
| `3.2`, `3.5`, `3.8`, `11.4`–`11.7` | F08, F09, F12, F13 | Publication enseignante → remise → correction → validation humaine officielle |
| `2.1`, `2.2`, `4.1`, `4.2` | F11, F12, F15, F16 | Candidat neuf → inscription → facture → règlement rapproché |
| `6.1`, `6.4`–`6.6`, `11.8`, `11.9` | F22, F24 | Diplôme conditionné aux acquis, vérification réelle, portefeuille et alumni |
| `4.4`, `4.8`, `4.9`, `8.6` | F16, F20, F28 | Comptabilité/budgets, inventaire général/achats et souscriptions SaaS |
| `5.1`–`5.8`, `6.3`, `10.1`, `10.2`, `10.7` | F22–F27 | IA/OCR supervisés, badges, mobile/hors ligne et recherche métier |
| `11` | F29–F32, après leurs prérequis | Recette transverse, exploitation, livraison persistante et acceptation |

Les sources d'accès/publication LMS étaient **inachevées et non déployées**
lors de l'inventaire. La référence communiquée était le backend
`local-20261104-courses` et le frontend `local-20261104-erp-tables`, sans sondage
de l'installation par cette mission. Une évolution concurrente ne change pas
automatiquement les statuts. Le design ERP, les comptes, le MFA et les dossiers
existants doivent être conservés.

Les prestataires paiement, vidéo, messagerie, IA et les validations
institutionnelles restent des dépendances explicites. Une fonctionnalité
absente ou simulée ne devient pas « bloquée seulement par les identifiants » :
ce statut exige la preuve du fonctionnement de l'intégration et que l'accès
externe constitue réellement le seul obstacle restant.

## Comment clôturer une exigence

1. Référencer son `id` et ses lots. Couvrir **tous** ses `required_behaviors`
   et champs, pas seulement la lacune traitée par le dernier incrément.
2. Exécuter les tests ciblés, refus importants et parcours réels sur données
   synthétiques isolées, avec rôles distincts et les variantes/packs concernés :
   droits inter-tenant, validations, erreurs, doublons, clôtures et reprise.
3. Ajouter à `execution_evidence` les scénarios, comportements couverts,
   date, révision/images, commande ou procédure reproductible, rôles/périmètre,
   résultats attendus/observés et liens vers artefacts expurgés. Distinguer
   preuve de composant, de parcours intégré et de livraison.
4. Résoudre les écarts et revues ; vérifier données persistées, notifications,
   documents et maintien du résultat après livraison/redémarrage selon le
   protocole. Conserver les preuves d'incréments antérieurs sans les extrapoler.
5. Passer à `verified` uniquement lorsque toutes les obligations sont prouvées
   pour la version et le périmètre annoncés. Sinon conserver `partial` ou
   `unverified`, décrire le reste et actualiser les compteurs. Une exigence
   vérifiée ne clôt pas automatiquement son lot ; `11` exige la chaîne complète.

La sortie globale exige aussi les **500 sessions authentifiées concurrentes
distinctes réellement exercées**, la mesure d'intégrité et la recette navigateur
prévues au protocole, puis le déploiement local persistant. Les campagnes 500
documentées ci-dessous restent rouges ; aucune acceptation institutionnelle
n'est annoncée.

## Validation de l'inventaire initial

Copie de la matrice validée conservant son schéma : **94 identifiants uniques,
32 lots et 532 références fichier:ligne**. Contrôles de JSON, compteurs,
références, correspondance des lots et identité de la copie avec l'artefact
source ; aucune donnée métier personnelle ni secret ajouté.

L'inventaire initial n'a relancé aucun test applicatif ni changé de service.
Les compléments ci-dessous actualisent ensuite les preuves et statuts, sans
extrapoler une qualification globale.

## Incrément accès et publication : preuves supplémentaires

Après l'inventaire, les contrats d'accès, de publication et de JWT locaux ont
été qualifiés sur les deux SIS isolés : **85 tests secondaire et 83 supérieur**.
Ils couvrent notamment les mêmes identifiants utilisateurs dans deux schémas,
les refus d'accès/refresh/logout interétablissements, le parcours MFA, six
pannes transitoires suivies d'un retrait confirmé avec la même version, les
conflits permanents et une réactivation concurrente au balayage de révocation.

Open edX : **8 tests d'accès natifs et 6 de publication** réussis. Deux
parcours supplémentaires utilisent réellement OAuth, le LMS et Studio depuis
les deux SIS : inscription, réponse perdue après écriture distante, reprise,
retrait, refus d'un ancien octroi, affectation/retrait enseignant, publication
de la révision examinée, rejeu identique et conflit de révision. Les contenus
de ces recettes sont synthétiques ; aucune décision académique réelle n'est
prise automatiquement.

La revue indépendante a identifié puis revérifié les trois corrections :

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | 🟠 HIGH | `sis_common/local_authentication.py` | 18–62 | Réutilisation interétablissements des JWT locaux : corrigée dans le code et les régressions | 9/10 |
| 2 | 🟡 MEDIUM | `deploy/openedx/sis-provisioning/sis_provisioning/access_views.py` | 147–161 | Retrait enseignant incomplet sur compte inactif : corrigé, réactivation sans restauration du droit | 10/10 |
| 3 | 🟡 MEDIUM | `sis_common/lms_access_sync.py`, deux `integration/tasks.py` | 54–80 ; 159–165 / 173–179 | Abandon du retrait après cinq pannes : corrigé par reprise temporisée, sans écrasement des conflits | 9/10 |

Ces conclusions concernent ce périmètre, pas une certification de sécurité
globale. L'image native `lms-sis-openedx:local-20261104-access` est installée
sur **Tutor de qualification**, après sauvegarde chiffrée vérifiée. Le paramètre
Tutor est `DOCKER_IMAGE_OPENEDX` ; les quatre conteneurs applicatifs doivent
effectivement utiliser la nouvelle image, un heartbeat seul ne le prouve pas.
La migration native additive `0006_managedpublication` est appliquée.

**Le backend utilisateur des deux SIS a été remplacé par `access3`**, après
sauvegarde chiffrée et lecture intégrale vérifiée. Les API, workers et
planificateurs utilisent l'image d'empreinte
`sha256:0aeb6aa8bf07353a0f07968c033f04aba0ea0ab7246289ee6af810917fd9e328`.
Les empreintes avant/après des comptes, mots de passe, MFA, groupes, permissions,
dossiers, notes et données financières contrôlés sont identiques.
Les anciens JWT locaux sans identité de tenant ne sont plus acceptés :
une nouvelle connexion est nécessaire, sans réinitialisation des comptes.
Le frontend utilisateur `local-20261104-access3` est également livré, sans
modification de la charte ERP. Aucun statut global de la matrice n'est coché
par ces seules preuves.

### Reprise après interruption et parcours de publication

La régression élargie a réussi sur **373 tests secondaire et 366 supérieur**.
Le delta de récupération des accès interrompus a ensuite réussi sur **46 tests
secondaire et 44 supérieur** : contention réelle de deux connexions PostgreSQL,
absence de reprise pendant un appel encore verrouillé, conservation de la
décision/version et protection contre la clôture tardive d'un ancien worker.
Chaque événement est réservé juste avant son appel réseau. Seuls les événements
`access.set`, versionnés et idempotents, sont automatiquement repris après
expiration ; cela ne prétend pas résoudre les interruptions des anciens types
d'événements. La revue indépendante de ce delta n'a pas relevé d'anomalie majeure.

La vue existante propose désormais un examen et une confirmation explicites
de publication, sans modification de la charte ERP. **15 tests composants**,
lint et build ont réussi. Deux parcours Chromium sur les SIS isolés ont ensuite
effectué une vraie publication OAuth vers Studio, perdu volontairement sa réponse,
fermé/réouvert le dialogue puis repris le même UUID et la même révision.
Les confirmations SQL natives, le contenu publié MongoDB et le score historique
1/1 ont été contrôlés séparément. Le dialogue a également été vérifié à 390 px,
sans débordement ni exception JavaScript.

Cette recette a découvert un champ `is_staff` absent du profil supérieur :
le bouton était caché à tort. La parité avec le secondaire est corrigée **en
lecture seule**, avec **22 tests API/authentification/MFA** réussis, notamment
l'impossibilité de modifier ce privilège par la mise à jour du profil.
Le backend de qualification est `lms-sis:local-20261104-access2` ; les autres
boutons encore désactivés de la page ne sont pas déclarés opérationnels.

Ces nombres désignent des campagnes qui se recoupent, pas un total de tests
distincts ni un pourcentage de couverture. Les preuves sont conservées dans
les artefacts `functional-outbox-recovery-final.log`,
`functional-superior-profile-contract.log`,
`functional-publication-browser-final.log` et
`functional-browser-native-state.log`. La charge de 500 sessions reste une
campagne distincte, encore en cours à ce stade.

### URL natives normales et raccordement de l'installation utilisateur

Les URL LMS, Studio et MFE utilisent désormais le port local **59080**, sans
règle spéciale de résolution Chromium. L'adaptateur Tutor local, désactivé par
défaut et limité à HTTP/localhost, corrige les domaines de cookies, les alias
Docker, l'écoute Caddy et le callback Studio. Le nouvel issuer est
`http://lms.sis.localhost:59080/oauth2`. Cinq tests de l'adaptateur et trois de
SSO ont réussi ; la régénération Tutor conserve la configuration. La sauvegarde
froide `05aed62e` a été relue intégralement avant modification.

Le pilote secondaire vérifie désormais dans un navigateur normal :
connexion LMS, dossier SIS, cours et réponse historique 1/1 sans nouvelle
soumission, retour SIS, déconnexion avec retour au catalogue puis reconnexion
obligatoire. Aucun ancien `404 /xblock/`, échec 5xx ou exception JavaScript
n'a été observé. L'ancienne erreur de lecteur reste **non reproduite** :
aucune correction de sa cause n'est revendiquée.

Les deux SIS utilisateur, toujours en authentification locale avec leur MFA
conservé, utilisent maintenant un **service OAuth technique distinct** de celui
des recettes. Il n'a ni mot de passe utilisable ni privilège staff/superuser ;
ses cinq permissions natives concernent uniquement les objets qu'il détient.
La santé LMS/Studio et l'accès OAuth sont vérifiés depuis chaque backend ;
une publication sur un cours non détenu est refusée. Les paramètres du réseau
externe sont persistés dans le `.env`, sans dépendre d'une commande manuelle
de raccordement Docker.

Deux nouveaux parcours sur l'installation utilisateur contrôlent connexion
avec MFA existant, rubriques, tables, thèmes et largeurs 1440/1024/390/320 px,
ainsi que la supervision LMS réelle. Les empreintes de sécurité et des données
métier restent inchangées. Les webhooks et automatismes ne sont plus présentés
comme actifs sans preuve : le delta API a réussi sur **18 tests secondaire et
16 supérieur**. Cela ne les implémente pas ni ne clôt leurs obligations.

Preuves : `functional-local-lms-connect.log`,
`functional-live-release-browser.log`, `functional-normal-sso-browser.log`
et `tutor/plugins-artifacts/native-local-urls-proof.json`. Les deux logos natifs
manquants ont été rétablis par des réécritures Caddy exactes vers leurs PNG
Indigo existants, sans changement d'image ou de charte. MIME, contenu et
décodage navigateur sont vérifiés ; l'adaptateur compte désormais six tests.
Le 404 de vérification proctoring d'un apprenant sans examen surveillé ne
qualifie pas cette fonction.

Après les sauvegardes post-livraison (SIS et Tutor) relues intégralement, les
services ont redémarré : empreintes métier, OAuth, santé LMS/Studio et parcours
SSO complet avec logos et score 1/1 restent valides. Les deux comptes de recette
publication ont été désactivés, leurs mots de passe rendus inutilisables et
leurs fichiers d'accès temporaires supprimés ; leur fixture est arrêtée.
Une revue indépendante du nouvel adaptateur, du réseau facultatif et du
service technique n'a identifié aucune régression exploitable de haute
confiance. Elle reste limitée à ce périmètre local HTTP.

### Première campagne de 500 sessions : non validée

La rampe a effectivement amené **500 sessions authentifiées distinctes** au
plateau prévu de 120 secondes, mais la cohorte complète n'a été maintenue
que **5,923 secondes**. Le rapport final indique
`passed=false` et `validated=false` : cette campagne **n'est pas acceptée**.

Le diagnostic relève 995 erreurs de transport, aucun 429/5xx serveur observé,
33,77 requêtes/s et un p95 de **5 796 ms**, au-delà des 2 000 ms exigées.
La fixture terminait TLS dans deux workers Gunicorn synchrones ; les temps
applicatifs internes (p95 99 ms) étayent un problème d'admission, sans permettre
de reconstituer chaque rupture TCP/TLS. Les 1 164 cycles confirmés restent
cohérents. Les comparaisons après écriture non confirmée sont indéterminées,
pas une preuve de corruption ni une réussite d'intégrité. Seules 252
déconnexions sont vérifiées ; 218 sessions synthétiques restent à révoquer.

Le harnais distingue maintenant charge, nettoyage et intégrité indéterminée,
toujours bloquante : 23 tests hors ligne et lint ont réussi. Le rapport rouge
original `sessions-500.json` est conservé, avec son diagnostic séparé
`load-postmortem.json`. La préparation suivante
doit qualifier une entrée TLS asynchrone et des workers adaptés, avec ses
ressources matérielles explicitement consignées, avant toute nouvelle
campagne complète. Aucun seuil, contrôle de sécurité ou objectif n'est
abaissé pour rendre le résultat artificiellement vert. Ce résultat ne clôt
ni la capacité de 500 connexions ni la recette universelle.

### Commandes outbox : qualification de composant

Les deux API disposent d'une demande de traitement limitée à l'établissement
courant. Le worker reprend le publisher existant, ses réservations, versions,
retraits, reprises et backoff. HTTP 202 confirme uniquement la mise en file ;
une publication au broker non confirmée produit une erreur 503 journalisée.
Les paramètres de périmètre et corps inattendus sont refusés. L'interface
remplace la purge par un filtre paginé `failed`/`dead` et des détails en lecture
seule, sans effacer les décisions ni les preuves.

Les campagnes ciblées ont réussi : 53 tests secondaire et 51 supérieur ;
la reprise API finale contient 8 tests par variante et recoupe ces campagnes.
Le frontend compte 83 tests réussis, incluant la publication existante ;
Ruff et ESLint sont sans erreur sur le périmètre. Les journaux sont
`.outbox-integration-tests.log`, `.outbox-api-final-tests.log` et
`.outbox-frontend-tests.log`, dans le dossier de travail parent du dépôt.

La revue indépendante des sources et régressions de cet incrément ne relève
aucune vulnérabilité exploitable de haute confiance. Elle ne constitue ni une
revue globale ni une preuve de livraison. Les preuves suivantes complètent la
qualification de composant ; elles ne changent pas les statuts universels.

### Outbox : recette réelle et livraison persistante

La recette navigateur a révélé un défaut réel que les mocks de publication
au broker ne détectaient pas : les deux processus HTTP utilisaient l'application
Celery par défaut et tentaient AMQP malgré Redis disponible. L'import standard
de l'application Celery dans les deux `config/__init__.py` corrige ce démarrage.
Une régression en processus neufs WSGI **et** ASGI vérifie maintenant le broker,
le backend de résultats et la file de la tâche. Les campagnes ciblées ont réussi :
21 tests par variante, puis 6 tests de routage par variante après lint final ;
ces campagnes se recoupent et ne s'additionnent pas.

Deux parcours navigateur sur de nouveaux établissements synthétiques, avec
sessions locales et CSRF réels, ont ensuite vérifié :

- HTTP 202 avant le démarrage du worker, sans modification prématurée des événements ;
- consommation effective via Redis/Celery ; retrait transitoire passant de six
  à sept tentatives, toujours en attente, avec la même décision/version ;
- 52 preuves d'échec par variante conservées exactement, pagination, filtre,
  actualisation explicite et détails sans action destructive ;
- refus anonyme/enseignant et corps interdits ; arrêt réel du broker donnant
  HTTP 503 et un message honnête, puis reprise du broker ;
- empreintes outbox inchangées pour l'établissement d'origine et un établissement
  étranger ; affichage vérifié à 1440 et 390 px, sans exception JavaScript.

Le backend `lms-sis:local-20261104-outbox3`
(`sha256:e4d0f6965a9f81efa3c314e08d63f026b3124e75dfcb2fd27fa12a7352edfdb5`)
et le frontend `lms-sis-frontend:local-20261104-outbox3` sont livrés sur les deux
SIS utilisateur. Les images réellement exécutées, workers abonnés à `outbox`,
nouvelle tâche enregistrée, empreintes de sécurité et données métier couvertes
ont été vérifiés. Les sauvegardes chiffrées avant/après ont été relues entièrement :
la dernière contient 31 snapshots et 62 packs contrôlés. Après redémarrage des
services par la sauvegarde, les comptes et MFA existants, navigation ERP,
thèmes, tables, supervision native et commandes de lecture outbox fonctionnent
toujours. Aucun événement utilisateur n'a été déclenché pour cette recette de
livraison ; les mutations ont été qualifiées dans la fixture isolée.

Preuves : `outbox-browser-proof.json`, `functional-outbox-final-fixture.log`,
`functional-http-celery-bootstrap.log`, `functional-http-bootstrap-final.log`,
`functional-outbox-release-proof.json` et `functional-outbox-persistent.log`
dans le dossier de session. Les anciens essais en erreur restent conservés.
Les acteurs synthétiques ont été désactivés, leurs sessions supprimées dans
leurs seuls schémas, les domaines d'origine rétablis et la fixture arrêtée,
sans effacer les événements de preuve. **Le design reste inchangé.**

### Charge : entrée TLS corrigée, nouvelle qualification autorisée

La fixture de charge utilise maintenant Nginx pour TLS et Gunicorn HTTP
(quatre workers, huit threads chacun), avec API 4 CPU/2 Gio, PostgreSQL
2 CPU/1 Gio, proxy 0,5 CPU/128 Mio, Redis 0,25 CPU/128 Mio et générateur
1 CPU/1 Gio. Ce sont des ressources explicites différentes de la première
campagne, pas une amélioration obtenue à matériel inchangé.

Le diagnostic a retenu 500 sockets TLS vérifiées simultanément, p95 1 723 ms,
sans requête HTTP ni authentification : **ce n'est pas une preuve de capacité
applicative**. Un essai de résolution IPv6 erroné est conservé séparément.
Le petit smoke suivant ne porte que sur deux utilisateurs, 28 requêtes et
quatre cycles : p95 687 ms, intégrité déterminée et aucune session restante.
Les 218 sessions synthétiques résiduelles de la première campagne ont été
supprimées après conservation des preuves. Le harnais compte alors 26 tests
hors ligne réussis, avec Ruff et validation Nginx.

Après la livraison outbox, une nouvelle campagne complète est autorisée :
nouveau candidat/empreintes incluant la correction du démarrage Celery,
smoke préalable obligatoire, rampe de 3 600 secondes, 500 utilisateurs,
cohorte complète pendant 120 secondes et p95 de 2 secondes inchangé.
**Son résultat reste à établir.** Le premier rapport rouge demeure intact.

À 22:47 UTC, le journal de cette nouvelle campagne confirme 325 utilisateurs
authentifiés pendant la rampe. L'API exécute l'image immuable `outbox3` ci-dessus :
seuls les répertoires de recette `/fixture`, `/runtime` et `/app/load_tests` sont
montés, pas les sources applicatives entières. Ce point d'avancement ne prouve
ni 500 sessions maintenues ni le respect des seuils ; le verdict reste ouvert.

## Synchronisation individuelle des identités associées

L'action individuelle des correspondances utilisateur est raccordée, avec
confirmation explicite, requête vide `{}`, validation stricte du reçu natif
et reprise de la même identité après une réponse incertaine. L'invalidation
concerne toutes les pages du seul SIS sélectionné. Les 127 tests de trois suites
frontend et le lint ciblé réussissent ; la revue de sécurité indépendante ne
relève aucun défaut exploitable de haute confiance dans les sources et tests
de cet incrément. Elle ne constitue pas une requalification du backend natif.

Deux parcours navigateur isolés ont effectivement créé une identité native,
modifié sa source SIS, perdu la réponse **après l'écriture serveur**, puis
repris le même identifiant LMS après fermeture et réouverture du dialogue.
Confirmation, annulation sans POST, pagination précédemment mise en cache,
mapping inactif, refus enseignant, formats 1440/390 px et absence d'exception
JavaScript sont contrôlés. Une attente erronée du harnais sur un indicateur
permanent a été corrigée avant toute mutation ; son premier journal est conservé.

Le contrôle SQL natif confirme unicité, propriétaire de service, nom/email et
ID stables, sans transfert de privilèges SIS, rôle de cours, inscription ou
accès LMS. Les comptes antérieurs et le résultat historique 1/1 sont conservés.
Les seuls nouveaux acteurs de recette — 106 comptes SIS et deux comptes natifs —
ont ensuite été désactivés, leurs mots de passe rendus inutilisables et leurs
sessions SIS supprimées. Les correspondances et preuves sont conservées,
la fixture est arrêtée et ses identifiants temporaires supprimés.

Le frontend utilisateur `lms-sis-frontend:local-20261104-identity1`
(`sha256:82e312f2bcf1c767e7edb0083396969db4f2e65669e2df05eef466cf57642058`)
est livré ; le backend reste `outbox3`. Les sept images applicatives exécutées
sont contrôlées après reprise. Sauvegardes chiffrées avant/après relues
intégralement : 33 snapshots et 66 packs lors du dernier contrôle.
Comptes, mots de passe, MFA, permissions et empreintes métier couvertes sont
inchangés. Les parcours ERP, thèmes, tableaux, lecture outbox et liste des
identités fonctionnent après redémarrage, sans changement de design.

**Limite explicite :** l'installation utilisateur ne contient encore aucune
correspondance. Sa recette reste en lecture seule ; les mutations et dialogues
sont qualifiés dans la fixture, pas sur de vrais dossiers. Cet incrément
concerne uniquement les correspondances existantes, y compris sans ID natif :
il ne raccorde pas « Synchroniser tous » ni la première association d'un
utilisateur absent de cette liste. Aucun statut global n'est coché par assimilation.

Preuves dans le dossier de session : `identity-browser-proof.json`,
`functional-identity-browser-final.log`, `identity-native-verify.json`,
`identity-native-retire.json`, `functional-identity-retirement.log`,
`functional-identity-live.log`, `functional-identity-persistent.log` et
`functional-identity-persistence-proof.json`. Les journaux des composants
restent dans `validation-user-sync`.

## Première association : limite levée et livraison persistante

Depuis l'onglet Utilisateurs, « Associer un utilisateur » ouvre une seule table
paginée, avec retour aux associations. Le GET ne crée rien : seuls les comptes
actifs du périmètre courant sans aucune correspondance sont proposés ; une
correspondance révoquée reste exclue. Le compte technique anonyme de Guardian,
actif en base, avait été proposé par le premier candidat backend : ce défaut
réel a été corrigé avec une exclusion fondée sur sa configuration et une
régression dédiée. La garde de tenant outbox est extraite sans changement
de comportement et partagée avec ce nouvel endpoint.

La campagne ciblée finale compte **22 tests par SIS**, avec identités et outbox,
et **144 tests frontend dans trois suites**, plus les linters ciblés.
Ces campagnes recoupent les précédentes. La revue indépendante n'identifie
aucune vulnérabilité exploitable de haute confiance dans ce delta ; ses limites
restent celles d'une inspection statique.

Sur les deux SIS isolés, la cible n'avait **aucun mapping** avant l'action.
La première requête a réellement créé le compte natif et sa correspondance ;
sa réponse a ensuite été perdue volontairement après commit. La dernière page
des candidats, devenue inexistante, affiche explicitement le 404 et revient
à la première page. Après fermeture, actualisation et passage aux associations,
l'incertitude reste visible ; une nouvelle confirmation reprend le même
identifiant natif. Annulation sans POST, verrou pendant l'envoi, refus enseignant,
pagination, mise à jour du nom et affichages 1440/390 px sont vérifiés.

Les contrôles natifs confirment propriété de service, unicité, absence de
privilèges/inscriptions supplémentaires et conservation des comptes antérieurs
et du résultat 1/1. Les seuls acteurs synthétiques créés pour cette recette
sont ensuite désactivés ; leurs correspondances sont conservées, leurs sessions
SIS et identifiants temporaires sont retirés. Le contrôle après sauvegarde froide
native confirme que les deux nouveaux comptes restent désactivés et inutilisables.

Images utilisateur livrées :

| Composant | Image | Empreinte exécutée |
|---|---|---|
| Backend, workers et beat des deux SIS | `lms-sis:local-20261104-first-association1` | `sha256:66d0d69223e72906a06b9d7464810caafcd984a38d5d082c598e5ad2b10f4eb3` |
| Frontend | `lms-sis-frontend:local-20261104-first-association1` | `sha256:ebe5db8d135d8e67f33eca284e644cd92a5455d85b8d26c56e13fe4a47062e80` |

Le contenu backend empaqueté diffère d'outbox3 uniquement sur les six fichiers
de cet incrément, tests compris. Les sept services, leurs images effectives
et les workers outbox sont contrôlés après reprise. La sauvegarde SIS finale
contient **35 snapshots et 70 packs**, entièrement relus. Après les reprises
SIS et LMS, comptes/MFA, empreintes métier couvertes, charte ERP, supervision
et connexion OAuth fonctionnent toujours. Sur l'installation utilisateur,
64 candidats sont affichés par SIS ; ouverture puis annulation du dialogue
sans aucun POST de provisioning, avec toujours zéro correspondance créée
sur les véritables dossiers par cette recette.

« Synchroniser tous » reste désactivé. L'incertitude UI est conservée dans la
page montée, pas dans un stockage intersessions ou après rechargement complet.
Ce lot ne qualifie ni une synchronisation massive ni l'ensemble des exigences.

Preuves : journaux `validation-first-association`, puis, dans le sous-dossier
de session `first-association`, `backend-final-tests.log`,
`backend-image-delta.json`, `identity-browser-proof.json`,
`identity-native-verify.json`, `identity-native-after-retire.json`,
`main-persistent-proof.json`, `main-backup-after.log` et
`main-persistent-browser.log`.

## Nouvelle campagne 500 : échec conservé, diagnostic API en cours

La campagne `outbox3` a réellement authentifié 500 utilisateurs distincts,
avec un pic de 500 sessions et requêtes simultanées. **Elle échoue néanmoins** :
la cohorte métier complète ne tient que 9,816 secondes sur les 120 attendues ;
seuls quatre utilisateurs terminent des cycles, soit 131 cycles vérifiés.
Le p95 métier atteint 6 179 ms pour un budget de 2 000 ms, avec 496 timeouts.
Les 500 déconnexions sont confirmées et aucune session ne reste en base.
Aucun 429, 5xx ou OOM n'est observé ; cela ne rend pas la campagne acceptable.

Les 626 écritures tentées ont persisté selon le contrôle SQL ciblé :
131 appartiennent aux cycles vérifiés, 168 ont un reçu mais une relecture
échouée et 327 restent sans reçu HTTP. Aucune violation n'est trouvée dans
les champs contrôlés, **mais ces 327 issues indéterminées restent bloquantes**.
Le contrôle SQL n'annule ni l'échec de cohorte ni les résultats HTTP incertains.
L'image immuable et ses 71 fichiers gelés sont vérifiés ; les deux fichiers
de bootstrap absents du manifeste initial de 69 chemins sont explicités.
Cette mesure concerne `outbox3`, pas une qualification de la livraison suivante.

Le diagnostic borné suivant ne démontre pas de recréation TLS par requête :
les contextes et cookies sont déjà séparés et réutilisés par client.
Sur 128 lectures CSRF avec 32 clients, 1/2 CPU donne respectivement p95
265/183 ms et environ 204/199 requêtes/s ; cela ne justifie pas une hausse
durable des ressources du générateur. Le smoke applicatif reste limité à
deux utilisateurs, p95 148 ms, avec déconnexion complète. Le harnais et ses
outils comptent alors 29 tests réussis. Une erreur propre au premier outil
de diagnostic a été corrigée, pas un défaut prouvé de la campagne.

Sur 168 écritures réussies appariées, l'écart entre temps upstream et traitement
Gunicorn atteint p95 4,474 s : il comprend l'attente d'admission/file et des
écarts réseau, pas seulement l'exécution Python. Un diagnostic API ciblé est
engagé avant toute nouvelle campagne complète. Les tests Jest
terminés à 23:09 UTC ont recoupé le début du plateau ; leur contribution ne
peut pas être quantifiée avec les traces disponibles. Aucun seuil, timeout,
parcours, contrôle TLS ou protection n'a été assoupli. Rapports et traces
rouges sont conservés ; **aucune nouvelle qualification 500 n'est annoncée**.

Preuves stables dans `sis-load-d0c25c75/output` du dossier de session :
`outbox3-500-final-result.json`, `outbox3-500-database-integrity.json` et
`transport-diagnostic-final-result.json`. La validation globale reste ouverte.

## Organisations internes : qualification partielle réconciliée

Pour `1.2`, le journal `functional-broad-regressions-final.log` confirme sept
tests hiérarchiques réussis par variante, aux lignes 24 et 102. Son SHA-256 est
`0415beb7727075821dfd7c95611d96cf0d1cb0a34abf60b53d457e4dee60a29e`.
La mention documentaire `not_run` est corrigée sans additionner les campagnes
373/366 ni promouvoir le statut `partial`.

Ce socle couvre les unités campus/département/programme, les rattachements
classes/formations, l'héritage, les verrous, révisions et refus testés.
Il ne couvre pas encore les organisations université/entreprise du cahier,
leurs articulations avec tous les objets académiques existants, ni les
rattachements généraux d'utilisateurs, ressources et activités. Une extension
compatible est engagée ; aucun organigramme universel ni scénario navigateur
complet n'est encore annoncé livré par ce nouvel incrément.

## Verrous des calendriers : correctif livré, charge 500 toujours ouverte

Le diagnostic HTTP de 20 utilisateurs a identifié une contention sur le verrou
`FOR UPDATE` de l'année scolaire, partagé par des écritures métier pourtant
indépendantes. Ses 80 cycles et son p95 de 471 ms ne qualifient pas 500
utilisateurs et n'expliquent pas à eux seuls tous les délais des campagnes rouges.

Le garde `ensure_academic_open` utilise désormais `FOR SHARE` sur PostgreSQL
dans une transaction, puis relit le calendrier. Les mutations du calendrier
conservent leurs verrous exclusifs. Trois tests de concurrence réels par SIS
vérifient les lecteurs simultanés, le blocage d'une clôture pendant une écriture
autorisée et le refus d'un garde en attente après une clôture concurrente.
Le premier test échouait avec le code livré précédent. Les régressions ciblées
finales passent : **33 tests secondaire et 33 supérieur**, Ruff et formatage.

La première exécution élargie a aussi révélé une fixture d'examen dépendante de
l'heure : à 01 h, une épreuve du jour à 09 h n'ouvrait pas encore la soumission.
Le même échec est reproduit sur l'image précédente. La fixture fournit maintenant
explicitement une fenêtre ouverte via les champs API existants ; aucune garde
applicative ni horloge système n'a été désactivée ou modifiée.

Le candidat `lms-sis:local-20261105-calendar-lock1`,
`sha256:d4bcac920a2ccd2fa093294f8ae44fdbad46eef08f2e05023ec5a5089e78bc99`,
reprend exactement les couches et la configuration de `first-association1`,
avec deux fichiers seulement ajoutés par remplacement : le garde et ses tests.
Les sources empaquetées correspondent aux sources testées. L'extension
organisationnelle en cours n'est pas incluse.

La revue de sécurité statique ciblée ne signale aucun défaut ; elle ne constitue
pas une recette runtime. Deux contrôles HTTP non instrumentés passent ensuite,
sur `first-association1` puis le candidat : 20 utilisateurs, 400 requêtes et
80 cycles chacun, zéro erreur, écriture indéterminée ou session restante.
Le p95 est de 459 puis 451 ms, mais la moyenne de 144 puis 168 ms :
**aucun gain global n'est démontré** par cette paire de petits contrôles.

Le backend `calendar-lock1` est livré sur les deux SIS utilisateur, API,
workers et beat. Le frontend `first-association1` est conservé. Les sept images
effectives, comptes réels avec MFA, empreintes de sécurité et métier, files
outbox et vues ERP sont vérifiés avant et après sauvegarde/reprise. Les vues
d'association restent à 64 candidats par SIS ; aucune identité réelle n'est
provisionnée par ces parcours. La sauvegarde préparatoire compte 36 snapshots
et 72 packs ; celle après livraison est relue intégralement :
**37 snapshots, 74 packs**.

Une nouvelle campagne 500 sur cette image précise est autorisée après contrôle
des ressources, avec les mêmes seuils et une fenêtre de charge réservée.
Son résultat n'est pas encore disponible. Elle n'inclut pas l'extension
organisationnelle et aucune campagne 500 n'est annoncée réussie.

Preuves conservées dans les artefacts de session :
`calendar-lock-baseline-tests.log`, `calendar-lock-baseline-clock.log`,
`calendar-lock-final-tests.log`, `calendar-lock-candidate.json` et
`calendar-lock-main/backup-before.log`, `calendar-lock-main/backup-after.log`,
`calendar-lock-main/persistent-proof.json` et
`calendar-lock-main/persistent-browser.log`. Le diagnostic détaillé est
`sis-load-d0c25c75/output/api-bottleneck-diagnostic-final.json` ;
la comparaison est `sis-load-d0c25c75/output/calendar-comparison-verdict.json`.

## Organisations libres : composants et fixture réelle qualifiés

L'extension de `1.2` conserve explicitement le mode historique v1 et ajoute
un mode libre v2 : arbres université/entreprise, catégories personnalisées et
extension d'un périmètre historique sans conversion implicite. Codes, type,
parent et version restent figés ; nom et précision peuvent être modifiés.
Les trois vues exclusives reprennent le design ERP existant.

Les rattachements utilisent les vrais utilisateurs, classes/formations,
livres et créneaux, ainsi que les objets académiques présents dans chaque SIS.
Le registre des cibles est fermé et les opérations sensibles réservées à
l'administrateur du tenant. Aucun droit ou accès LMS n'est octroyé.
La FK historique de Classe/Formation reste la source unique ; snapshots,
provenance et relations antérieures ne sont pas recalculés.

**18 tests backend par variante et 14 tests UI** ont réussi, avec les linters
et contrôles de migrations. La revue statique ciblée des 19 fichiers ne signale
aucune vulnérabilité ; elle ne constitue pas une homologation globale.
L'image `lms-sis:local-20261105-organization1`,
`sha256:6a166511a8a98f86f40acd8580a83c6c340f37dfc6caf0051598e6ba4ab6e64b`,
ajoute exactement 14 fichiers backend à `calendar-lock1`. Sans montage des
sources hôte, **51 tests par variante** passent : organisation, hiérarchie,
calendriers et notes. Ces campagnes se recoupent.

Sur une fixture multitenant isolée, sauvegardée et relue intégralement,
les migrations explicites préservent les comptes, dossiers et anciens
organigrammes. Le navigateur construit ou retrouve **19 unités par variante**,
rattache et consulte **7 types d'objets secondaire et 10 supérieur**.
Les reprises réutilisent les unités/liens réellement créés, sans les compter
comme de nouvelles créations. Les premiers échecs de sélecteurs et un 429
du harnais sont conservés ; le passage final respecte la cadence API existante,
sans modifier les protections.

Les parcours complémentaires vérifient renommage/précision, champs figés,
pagination des 26 références de livres avec réinitialisation du consentement,
annulation sans lien et navigation vers une unité liée. Doublons, acteur
enseignant, type interdit et confirmation absente sont refusés. Les vues sont
contrôlées à 1440, 390 et 320 px. Le test historique du dépôt passe dans les
deux SIS : simulation, publication verrouillée, retour futur à l'héritage,
consultation datée et audit ; les catalogues temporaires sont restaurés
exactement, y compris en cas d'échec du test.

Après redémarrage intégral de la fixture, unités, rattachements, renommage et
consultation navigateur persistent. Les empreintes comptes/MFA/groupes/droits,
dossiers, snapshots et relations sont conservées. Les six acteurs synthétiques
sont ensuite désactivés, leurs mots de passe rendus inutilisables et leurs
sessions retirées ; ces états sont relus et vérifiés. Les données de recette
sont conservées et la fixture arrêtée, sans suppression d'autres tenants.

La première fixture n'exerçait pas la pagination des relations au navigateur
(moins de 25 relations). Le complément ci-dessous traite cette limite.
L'image organisation n'est pas celle de la campagne 500.

Preuves : `validation-organization`, puis artefacts de session
`organization/packaged-tests.log`, `migration-proof.json`, `browser-proof.json`,
`browser-additional-proof.json`, `historical-proof.json`,
`browser-persistent-proof.json`, `persistent-proof.json`,
`retired-integrity-proof.json` et `retire-proof.json`.

### Complément : pagination des relations réelles

Dans une nouvelle recette secondaire isolée, un groupe comporte 26 classes
réelles. La consultation affiche exactement **25 puis 1 relation** ; boutons
suivant/précédent, états désactivés et retour aux mêmes identifiants sont
vérifiés. Le scénario réussit de nouveau après redémarrage, sans mutation
causée par la consultation. Le supérieur n'expose aucune relation to-many
dans ce catalogue : ce bouton n'y est pas artificiellement rendu applicable.

Les anciennes données et les six acteurs précédemment retirés, dont leur MFA,
restent inchangés. Seul le nouvel acteur est retiré, avec ses deux sessions ;
fixture arrêtée et nouveaux secrets effacés. Aucune modification applicative,
du SIS principal ou du LMS. Preuves :
`organization-relations/proof-summary.json`, `handoff.log` et `SHA256SUMS`.

### Livraison principale des organigrammes

Après la fenêtre calme, le backend `organization1` ci-dessus et le frontend
`lms-sis-frontend:local-20261105-organization1`,
`sha256:8d77377bff18ceeb29d59104356296ffa9ee2b1a050b45426abc0f6a9919e1ba`,
sont livrés sur `http://sis.validation.localhost:58623`.
Le frontend est reconstruit pour les URL principales, pas repris de la fixture.
Seules les deux références d'images changent dans la configuration locale.

Les API, workers et beat sont arrêtés avant les migrations explicites
`migrate_schemas`. Les anciens organigrammes, comptes/MFA/droits et empreintes
métier contrôlées sont conservés. Les sept images effectives et workers outbox
sont vérifiés, ainsi que les connexions réelles avec MFA, vues ERP, intégration
et trois vues organisationnelles. L'ouverture/annulation du formulaire et la
consultation des règles n'écrivent aucune donnée d'établissement. Ces contrôles
réussissent aussi après redémarrage complet. Sauvegarde préalable **38 snapshots /
76 packs** ; sauvegarde finale **39 snapshots / 78 packs**, intégralement relue.

Une observation distincte empêche d'affirmer « zéro provisioning global » :
**61 mappings secondaire**, avec identifiants LMS, ont été créés entre
02:00:00 et 02:00:50 UTC, avant cette migration vers 02:21 UTC.
Cet horaire correspond au traitement nocturne existant des élèves sans mapping ;
le correctif des déclenchements implicites est décrit plus bas.
Les 122 anciens événements `user.sync` restent `dead` et antérieurs à cette
création. Les recettes principales observent désormais **3 candidats et
61 mappings secondaire**, contre **64 candidats et zéro mapping supérieur**.
Elles n'émettent aucun POST de provisioning. Aucun mapping n'est supprimé pour
ramener artificiellement les compteurs à zéro.

Preuves dans `organization-main` : `frontend-image.json`, `migration-proof.json`,
`initial-proof.json`, `persistent-proof.json`, `initial-browser.log`,
`persistent-browser.log`, `backup-before.log` et `backup-after.log`.

### Clôture de l'exigence 1.2

Les deux dernières réserves sont levées. Une lecture PostgreSQL en transaction
lecture seule confirme les rôles réels `eleve` et `etudiant` des membres déjà
rattachés, sans réactivation ; MFA et liens restent conservés, puis les bases
de fixture sont arrêtées.

La comparaison des frontends fixture/livré vérifie **15 assets identiques et
5 identiques après les seules substitutions des URL publiques SIS/LMS/Studio
et des noms d'assets générés**. Tout le JavaScript exécutable est comparé.
Les contenus, noms et métadonnées des sourcemaps sont identiques ; leurs
positions générées diffèrent avec la longueur des URL. Le rapport statistique
`report.html`, non référencé par le HTML/JS/CSS applicatif, est explicitement
exclu. Il s'agit d'une équivalence applicative, pas d'images binaires identiques.
Les deux comparaisons rouges précédentes sont conservées.

Toutes les obligations recensées pour `1.2` sont ainsi prouvées et son statut
passe à `verified` : **70 partial / 21 absent / 2 unverified / 1 verified**.
Les 93 autres exigences, les lots globaux et le résultat 500 restent inchangés.
Preuves : `organization-main/learner-roles-proof.json`,
`frontend-equivalence-final.json` et leurs harnais.

## Campagne 500 calendrier : résultat rouge confirmé

Sur l'image `calendar-lock1`, 500 utilisateurs sont authentifiés, mais la cohorte
complète ne tient que **9,361 secondes sur 120** et **aucun cycle métier ne se
termine**. Le p95 atteint **5 889 ms** pour un seuil de 2 000 ms, avec
**500 timeouts**. Les 500 écritures retrouvées en SQL se répartissent en
199 reçus HTTP et **301 écritures sans reçu**, toujours indéterminées.
La persistance SQL ne transforme pas ces échecs HTTP en succès.

Les **500 déconnexions** sont prouvées, sans session restante ; les invariants
contrôlés sont préservés et le broker est vide. Les budgets CPU/mémoire, limites
de connexions, parcours et protections n'ont pas été assouplis. La fenêtre
02:01:21–02:18:21 UTC est réservée sans charge parent ; le build principal
organisationnel ne commence qu'après sa fin.

Le changement de verrou reste correct selon les tests de concurrence,
mais **n'a pas qualifié la capacité de 500 utilisateurs**. Le prochain diagnostic
doit départager les files d'admission, coûts CPU et autres attentes restantes.
Aucune nouvelle campagne complète n'est autorisée ou déclarée réussie.
Preuve stable : `sis-load-d0c25c75/output/calendar-lock1-500-verdict.json`.

## Provisioning nocturne implicite : correctif livré

Les anciennes planifications déclenchaient automatiquement
`sync_all_pending_eleves` / `sync_all_pending_etudiants` à 03:00 Europe/Paris,
sans activation vérifiée par établissement. Les indicateurs « non vérifiée »
de l'interface ne contrôlaient pas Beat. Ces deux entrées sont retirées des
planifications par défaut, sans inventer une activation implicite.
L'outbox, la réconciliation/progression, les rappels et les appels opérateur
manuels sont conservés. Les tâches déjà en file ne sont pas annulées par ce
changement et aucun mapping existant n'est supprimé.

**21 tests secondaire / 20 supérieur** passent dans la campagne ciblée source ;
la régression des trois suites complètes, dans l'image sans montage source,
passe sur **33 / 31 tests**. Linters propres. Ces campagnes se recoupent.

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| — | — | Deux configurations Beat et leurs tests | — | Aucune signalée dans ce delta | Revue statique, trois empreintes concordantes |

Le stockage réel de `PersistentScheduler` est lu avec Beat arrêté : l'ancienne
entrée existe avant livraison, disparaît après mise à jour et reste absente
après redémarrage complet. Les quatre autres planifications sont strictement
identiques. Cette vérification runtime complète la revue statique ; elle ne
constitue pas une certification de sécurité générale.

Image livrée aux API/workers/beat des deux SIS :
`lms-sis:local-20261105-no-nightly1`,
`sha256:bba6656f139351b8220bb7426c30339e5ced2b7b03a6422cbb242e00ec136499`.
Elle ajoute seulement les deux configurations et leur fichier de tests à
`organization1`. Le frontend `organization1` reste inchangé. Les sept images,
workers outbox, comptes/MFA/droits, dossiers et organigrammes sont vérifiés.
La recette navigateur finale passe après reprise : ERP, intégration, identités,
organigrammes et responsive. Le premier passage du harnais cadencé attendait
trop tôt le libellé de connexion ; il attend désormais la vraie réponse HTTP
de santé avant l'assertion, sans modifier le service ou le protocole de charge.

Les 61 nouveaux comptes sont aussi vérifiés dans Open edX : propriété du
service principal, aucun privilège global, groupe, permission supplémentaire,
inscription ou accès de cours. Les comptes natifs antérieurs et le score 1/1
restent inchangés. Leur contrat conserve un mot de passe initial aléatoire
compatible avec la récupération native par email ; aucun mot de passe partagé
avec le SIS n'est ajouté. La sauvegarde froide native `474a60c3` est relue
intégralement (**11 snapshots / 25 packs**) et les empreintes sont identiques
après reprise. Sauvegarde SIS finale : **41 snapshots / 82 packs**, entièrement
relue, avec contrôle final des services et données.

Preuves : `validation-nightly-provisioning`, puis `nightly-main/backend-candidate.json`,
`packaged-tests.log`, `beat-before.json`, `beat-after.json`,
`beat-persistent.json`, `persistent-proof.json`, `final-proof.json`,
`browser-final.log` et `backup-after.log`. Conservation native :
`organization-main/native-before.json`, `native-after.json`, `native-backup.log`.
La réussite de cet incrément ne requalifie pas la charge 500 ni toute la plateforme.

## Réclamations : lectures répétées corrigées et livraison persistante

Le diagnostic HTTP à 20 acteurs sur `calendar-lock1` termine 80 cycles,
400 requêtes et les 20 déconnexions, sans écriture indéterminée ni session
restante. Son p95 de 507 ms ne qualifie pas 500 utilisateurs. Un GET fermé par
l'amont puis repris par Nginx arrive en 200 au client ; la cause de fermeture
reste inconnue. Aucun rejeu d'écriture n'est observé. Aucun bloqueur SQL n'est
vu à l'échantillonnage de 250 ms, qui peut manquer des attentes brèves.

Sur 48 POST de message, le diagnostic identifie **992 SELECT d'auteurs et
992 SET de schéma associés**. Après la mutation, `updated()` invalidait les
relations puis sérialisait chaque auteur séparément. La correction recharge
en lot l'historique avec ses auteurs et les pièces, après l'invalidation.
Périmètre, droits, verrou, version, événements et fraîcheur restent inchangés.

Une régression exécutée contre l'image déployée inchangée reproduit la
croissance de **60 à 100 requêtes SQL** pour des historiques de 10 puis
30 entrées. L'image corrigée conserve un nombre constant et restitue le
nouveau message et les libellés des auteurs. Les **9 tests réclamations par
variante**, sans montage source, couvrent aussi les refus inter-tenant,
révocations/réaffectations, versions périmées, pièces privées et rollback si
la notification échoue. Le premier harnais postulait à tort un auteur nul :
l'échec est conservé et le modèle `NOT NULL` / `PROTECT` n'est pas assoupli.

Formatage conforme ; aucune nouvelle alerte Ruff. La comparaison avec les
fichiers extraits de l'image initiale retrouve exactement les trois alertes
préexistantes : une `B904` et deux `PT027`. Elles ne sont ni masquées comme
résolues ni corrigées hors de ce delta.
Le premier contrôle par stdin avait résolu une autre configuration et signalé
huit diagnostics différents, également inchangés ; son résumé console de
trois alertes était donc incorrect. Cet artefact est conservé. La preuve
`lint-baseline-configured.json` impose le `pyproject.toml` du dépôt et les
chemins absolus, comme la commande sur les fichiers réels.

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| — | — | `sis_common/complaints.py` | 232–238 | Aucune nouvelle vulnérabilité signalée | Revue statique du delta |

Le backend **`lms-sis:local-20261105-complaint-prefetch1`**,
`sha256:163dbb742a6c6b03fdbfc68713ebd1b829b1ab24115bcaf02babd137939a26b7`,
ajoute seulement l'implémentation et son fichier de tests à `no-nightly1`.
Il est livré aux API/workers/beat du principal ; frontend `organization1`
inchangé, sans nouvelle migration. Images effectives, workers outbox,
comptes/MFA/droits, dossiers et organigrammes sont vérifiés avant et après
redémarrage complet. Des empreintes complémentaires en lecture seule
préservent les réclamations, historiques, pièces et tous les mappings LMS,
dont les 61 mappings secondaire déjà présents.

Les connexions réelles avec MFA, ERP, intégration, organigrammes, liste/filtre
des réclamations et largeurs 1440/390/320 px passent avant et après reprise.
Aucune écriture institutionnelle ou de réclamation n'est faite sur le
principal pendant ces parcours ; les sessions navigateur sont déconnectées.
Sauvegarde préalable **42 snapshots / 84 packs**, finale **43 / 86**,
relues intégralement, puis services et données revérifiés.

Preuves : `sis-load-d0c25c75/output/calendar-lock1-timed20-verdict.json`,
puis `complaint-prefetch/baseline-valid-history.log`, `packaged-tests.log`,
`lint-baseline-configured.json`, `backend-candidate.json`, `data-before.json`,
`data-final.json`, `final-proof.json`, `browser-initial.log`,
`browser-persistent.log` et `backup-after.log`.

### Comparatif HTTP20 apparié terminé

Une seule phase baseline `bba665` et une seule phase candidat `163dbb`
authentifient chacune 20 acteurs (12 apprenants, 6 enseignants, 2 directions),
terminent **80 cycles / 400 requêtes**, puis 20 déconnexions avec refus protégé
confirmé. Aucune erreur HTTP/transport, reprise, écriture indéterminée ou
session restante n'est observée. Les 48 POST sont appariés par acteur,
historique initial de 10/30 entrées et itération : **3 792 → 1 728 requêtes
SQL, soit −54,43 %**. Les deux groupes passent respectivement de 59/99
requêtes moyennes à **36 / 36** ; le N+1 des auteurs est éliminé.

Les anciennes données des 500 acteurs, notes, inscriptions, réclamations
et audits sont préservées. Les objets homologues sont ajoutés sans effacer
l'historique ; les 24 pièces privées de 600 octets conservent leur empreinte.
Toutes les nouvelles versions, 96 messages et 64 modifications de notes sont
vérifiés. Les données créées en A restent intactes pendant B.

Les p95 **482 / 420 ms sont descriptifs** : un seul A/B séquentiel avec caches
et état global différents ne prouve pas un gain de latence causal. Les pièces
sont contrôlées dans les réponses et le stockage, pas par upload/download HTTP.
Aucune contrainte ABAC non vide n'est exercée sur ces acteurs. L'ancien EOF
du diagnostic précédent ne se reproduit pas ici, sans cause ni réparation
démontrée.

Budgets et protections restent identiques ; instrumentation retirée,
fixture candidate saine, broker vide et anciens résultats rouges conservés.
Fenêtre calme libérée à **04:35:34 UTC**. Rapport
`sis-load-d0c25c75/output/complaint-prefetch-ab-final-report.txt`, données
`complaint-prefetch-ab-final-result.json` et scellé
`complaint-prefetch-ab-final-seal-v2.json` : 133 artefacts actuels vérifiés.
**La capacité 500 reste rouge** et les 93 exigences encore non qualifiées
restent ouvertes.

## Notes : relecture verrouillée évitée sans retirer le contrôle d'accès

Les deux API de modification récupéraient et verrouillaient deux fois la
même note. La régression sur l'image initiale confirme ces deux lectures pour
un enseignant comme pour un administrateur. Le premier verrou, pris dans la
transaction de `update`, demeure détenu jusqu'à sa fin.

La proposition de remplacer simplement la seconde récupération par
`serializer.instance` a été **rejetée avant application** : le verrou Note
ne fige pas l'enseignant de l'évaluation. Elle aurait omis une réévaluation
des droits après réaffectation concurrente. Il ne s'agit pas d'une
vulnérabilité introduite dans le déploiement.

La variante retenue réexécute le queryset filtré et les permissions objet
DRF, sans reprendre le verrou déjà détenu. Elle recharge ensuite
l'évaluation pour garder le contrôle de fenêtre frais. Les gardes de
calendrier, la validation métier et la sauvegarde restent inchangées.

Deux régressions avec transactions PostgreSQL indépendantes passent sur
l'ancienne puis sur la nouvelle implémentation : réaffectation commitée après
le premier verrou et avant la sauvegarde → **404 sans changement de note** ;
fermeture de fenêtre après le deuxième contrôle objet → **400 `soumission`
sans changement de note**. Le candidat réussit également le contrôle d'une
seule lecture verrouillée par PATCH et restitue/persiste la note corrigée.

**36 tests par variante** passent dans l'image sans montage source :
calendriers concurrents, cycles académiques, saisie de notes et offres.
Ruff et formatage conformes sur les trois fichiers modifiés.

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| — | — | API notes secondaire / supérieur | 691–698 / 598–603 | Aucune nouvelle vulnérabilité dans la variante finale | Revue statique, trois empreintes concordantes |

Image livrée : **`lms-sis:local-20261105-grade-update1`**,
`sha256:1131bfa0b4fe8e644ed3f8afad35104078b9fc137b7235d36ce667e7c0df93b0`.
Seulement les deux API et leur fichier de régressions sont ajoutés à
`complaint-prefetch1`. Frontend `organization1` inchangé, aucune nouvelle
migration. Les sept services applicatifs, comptes/MFA/droits, dossiers
(dont notes), organigrammes, réclamations et mappings sont vérifiés après
livraison, redémarrage complet et sauvegarde finale.

Les parcours réels avec MFA puis déconnexion couvrent ERP, intégration,
organigrammes, évaluations, liste des notes supérieur et réclamations avant
et après reprise, avec contrôles responsive. Les écritures de notes sont
testées sur fixtures, pas sur les dossiers du principal.
Sauvegarde préalable **44 snapshots / 88 packs**, finale **45 / 90**,
entièrement relues. Aucun gain de p95 ni résultat 500 n'est déduit de cet
incrément ; le palier 100 est seulement en préparation.

Preuves dans `grade-update` : `backend-candidate.json`, `baseline.log`,
`baseline-concurrent-guards.log`, `packaged-tests.log`, `security-review.json`,
`data-before.json`, `data-final.json`, `final-proof.json`,
`browser-initial.log`, `browser-persistent.log` et `backup-after.log`.

## Diagnostic 100 sur `grade-update1` : p95 encore rouge

Une seule campagne a été exécutée sur la fixture isolée avec l'image
`1131bfa…`, les 100 comptes originaux (60 apprenants, 30 enseignants,
10 direction), une rampe d'authentification de 750 secondes puis un plateau
de 12 secondes. Les 60 réclamations choisies couvrent 47 historiques courts,
12 moyens et un long. Chaque cycle réalise lecture, écriture, relecture,
puis trois secondes de réflexion. Les quotas, Argon2, TLS, cookies,
limitations de requêtes, timeout de cinq secondes et seuil p95 de deux
secondes n'ont pas été assouplis.

**Verdict rouge : p95 métier 2 437 ms > 2 000 ms.** Les 235 cycles terminés
représentent 145 messages et 90 modifications d'appréciation confirmés
indépendamment en base, sans erreur, relance cachée ni écriture indéterminée.
Chaque acteur a terminé deux ou trois cycles. Les 712 requêtes métier
incluent sept lectures sans cycle et la vidange des requêtes en vol :
696 arrivées et 664 réponses pendant les 12 secondes exactes ; 16 relectures
arrivées et 48 réponses terminées ensuite sont conservées dans les mesures.
Le débit de 53,36 requêtes/s porte sur 13,344 secondes avec cette vidange,
pas sur toute la rampe. Les 100 DELETE de déconnexion et 100 réponses 401
sur une ressource protégée sont prouvés, sans nettoyage forcé de sessions.

Le worker 10 reçoit 313 des 712 requêtes et concentre **83,46 % de l'attente
mesurée dans les files Gunicorn**, ainsi que les 81 requêtes serveur de plus
de deux secondes. L'API utilise en moyenne 2,577 des quatre CPU alloués ;
ce résultat ne démontre ni une saturation globale continue, ni une marge
pour 500 utilisateurs. PostgreSQL ne montre pas de blocage échantillonné.
La sonde PG commence à T0+690,855 s : les premières 691,291 secondes n'ont
pas d'observations d'attentes PG. Les correctifs précédents sont observés :
un seul SELECT Note verrouillé par PATCH, aucun SELECT individuel d'auteur
sur les 145 messages.

La répartition à l'acceptation, la réutilisation des connexions upstream et
le coût de journalisation restent des hypothèses à départager, pas des causes
prouvées. Nginx conserve jusqu'à 32 connexions upstream **inactives** :
ce n'est pas une limite de 32 requêtes en vol. L'identité des sockets backend
et les valeurs résolues `worker_connections`/keepalive n'ont pas été capturées.
Un diagnostic corrélé connexion/PID/file/CPU est proposé seulement ;
aucune nouvelle campagne n'est autorisée par ce constat.

Les 132 tables et 24 empreintes de pièces protégées sont vérifiées ; les
anciens historiques, audits, valeurs numériques, affectations, 500 comptes
et objets A/B sont conservés. Deux exports PostgreSQL sont archivés et
hachés, sans essai de restauration pour cette campagne. API113 et proxy
ordinaires sont restaurés, HTTPS 200 réel, broker et sessions vides ;
la fenêtre est explicitement libérée le **5 novembre à 06:16:47 UTC**.
Les 1 532 artefacts ont été revalidés.

Preuves : `sis-load-d0c25c75/output/grade-update1-100-final-report.txt`,
`grade-update1-100-final-result.json`, `grade-update1-100-analysis.json`,
`grade-update1-100-workers-and-cycles.json`, `grade-update1-100-checksums.json`
et `grade-update1-100-final-seal.json`. **500/120 secondes, navigateurs,
ABAC non vide et couverture fonctionnelle globale ne sont pas qualifiés par
ce test.** Les anciens résultats rouges restent conservés.

## Séparation des habilitations : correction livrée, périmètre borné

Deux autorisations implicites ont été reproduites sur l'image113 en montant
uniquement les nouvelles régressions : le drapeau Django `is_staff` ouvrait
des accès métier et permettait des attributions d'accès LMS sans permission
correspondante. Le correctif retire cette admission des helpers et des
branches directement couplées comptes/groupes, notes et paiements. Il
conserve l'accès Django, le superutilisateur, les permissions explicites et
les compatibilités métier existantes, sans changer les comptes.

Les créations de paiements d'autrui et les réattributions via comptes/groupes
sont également contrôlées. Les deux routes d'attribution LMS exigent
`integration.change_edxaccessintent` et respectent les contraintes `courses`
et `kinds` avant lecture des cibles, création de décision/outbox ou appel
du LMS ; voir le [guide des responsabilités](INSTALLATION_ETABLISSEMENT.md#comptes-et-responsabilités).

La revue a ensuite bloqué **r2 avant son déploiement** : les retours personnels
enseignants ignoraient les scopes de lecture. Une régression PostgreSQL
reproduit deux évaluations propres renvoyées au lieu d'une, avec et sans
`staff`. En r3, les filtres existants sont appliqués avant les branches
personnelles des évaluations, notes, bulletins et moyennes. L'accès personnel
est donc intersecté avec les restrictions configurées ; l'exception
superutilisateur et les tableaux de scopes sont conservés.

| Réserve historique | Traitement vérifié |
|---|---|
| HIGH, confiance 9/10 : `staff` assimilé à une habilitation métier | Suppression de l'admission implicite et des voies couplées ; refus des opérations croisées et maintien des opérations autorisées |
| HIGH, confiance 9/10 : attributions LMS par `staff` seul | Permission explicite et contexte contrôlés avant effet local ou distant |
| MEDIUM, confiance 9/10 : scopes ignorés dans le candidat r2 | Candidat non déployé ; r3 intersection propriété/scopes, listes/détails et PATCH exclu en 404 sans modification |

**126 tests secondaire et 127 supérieur passent dans l'image empaquetée,
sans montage source.** Ils couvrent notamment droits croisés staff/non-staff,
propriété enseignante, ABAC non vide, permissions explicites, révocation
d'attribution LMS, paiements personnels, calendriers concurrents, délégations,
documents et réclamations. Le premier essai r1 conserve son échec : un ancien
test attendait l'accès au journal global grâce à `staff` seul. Il attend
désormais 403, puis vérifie qu'une permission explicite permet la lecture
sans exposer les réclamations privées. Aucune garde applicative n'a été
assouplie pour ce test.

La revue indépendante vérifie 19 empreintes en r2 puis les trois changements
r3, les seize autres étant identiques. La réserve ABAC est levée statiquement,
sans nouveau finding dans ce dernier delta. Ruff reste à **95 diagnostics
préexistants contre 95**, zéro nouveau : ce n'est pas un lint global propre.
Le formatage des onze fichiers contrôlés et les espaces du diff sont conformes ;
les anciens écarts de formatage du fichier de tests d'autorisation ne sont
pas présentés comme corrigés.

Image livrée : **`lms-sis:local-20261105-business-roles3`**,
`sha256:a4cfa8702af41d517f847d9f1221a735fb09cb5cf6f7c4b9625fc37b8acd9332`.
Les 19 fichiers sont ajoutés au-dessus d'image113 ; configuration runtime,
frontend `organization1`, design ERP et schéma de données restent inchangés.
Les 13 sources applicatives sont vérifiées dans chacun des deux conteneurs API.
Livraison, redémarrage complet, parcours réels avec MFA et déconnexion, puis
sauvegarde finale sont contrôlés. Les vues ERP, intégration, identités,
organigrammes, notes/évaluations et réclamations restent utilisables aux
largeurs 1440, 1024, 390 et 320, sans écriture des dossiers du principal.

Les comptes/MFA, dossiers, organigrammes, réclamations et mappings sont
préservés. Une empreinte complémentaire contrôle identifiants stables,
attributs d'accès, groupes et leurs permissions, appartenances, droits directs,
décisions LMS et états d'inscription ; progression et date de rafraîchissement
ne font pas partie de cette dernière empreinte d'autorisation.
Sauvegarde préalable **46 snapshots / 92 packs**, finale **47 / 94**,
avec lecture intégrale réussie.

Preuves dans `business-roles` : `backend-candidate.json`, `changes.diff`,
`baseline-superieur.log`, `scope-baseline-r2.log`, `packaged-tests.log`,
`packaged-tests-r2.log`, `packaged-tests-r3.log`, `security-review.json`,
`lint-baseline.json`, `data-final.json`, `authorization-final.json`,
`final-proof.json`, les deux journaux navigateur et `backup-after.log`.

**Limites :** les tests des nouvelles gardes LMS utilisent un transport natif
simulé, pas une nouvelle campagne d'attributions sur Open edX. Les parcours
navigateur du principal utilisent son administrateur existant, pas tous les
rôles. Les autres opérations techniques d'intégration gardées par `IsAdminUser`
et le circuit de validation humaine des notes restent ouverts. La chaîne
jusqu'à une modification des notes officielles par synchronisation n'est pas
établie. Ni l'exigence `1.4`, ni les lots F02/F07, ni la sécurité globale,
ni la capacité500 ne sont clôturés par cet incrément.

### Diagnostic admission100-v1 : arrêt avant T0

Le passage préparé après la séparation des habilitations n'a pas démarré :
le contrôle proc/cgroup utilisait le terminal au lieu du scope plafonné du
générateur. Aucun utilisateur n'a été authentifié et aucune écriture métier
n'a été effectuée par cet essai. Les quatre configurations Gunicorn résolues
avaient été lues : 4 workers × 8 threads, 1 000 connexions par worker,
keepalive 2 s, backlog 1 024 et `reuse_port=false`.

Le retour à l'API113/proxy ordinaires, HTTPS200, zéro session/broker,
132 tables et 24 fichiers protégés a été vérifié. La fenêtre calme a été
libérée le **5 novembre 2026 à 08:21:17 UTC**. Les 54 artefacts de cet arrêt
sont scellés ; il ne s'agit ni d'un résultat de charge ni de 100 déconnexions.

Un second contrôle a trouvé `memory.swap.max=max` pour PostgreSQL et Redis
malgré `MemorySwap=Memory` déclaré par Docker, avec du swap réellement occupé.
**Les campagnes précédentes n'établissaient donc pas l'effectivité du
zéro-swap.** L'ancienneté de cet écart et son influence sur leurs latences
ne sont pas démontrées. Leurs résultats rouges restent rouges.
La réapplication unique des deux limites a mis `swap.max` à zéro, sans vider
les pages déjà échangées : une reprise contrôlée est un travail distinct,
pas une autorisation de charge.

Cette reprise a ensuite rétabli **`memory.swap.max=0` et
`memory.swap.current=0` à 09:14:08 UTC**, sans changer les conteneurs,
volumes, images ni budgets. Les arrêts gracieux PostgreSQL/Redis, leur reprise,
HTTPS200, zéro session/broker et la conservation de 132 tables, 24 pièces,
500 comptes et 537 entrées d'historique ont été vérifiés après une sauvegarde
fraîche intégralement relue. Les 46 artefacts de `output/swap-restore-v1/`
sont scellés et revérifiés ; aucune mesure de capacité n'en découle.

Le kit v2 corrige l'identité du scope entre préflight et superviseur ;
ses **22 tests hors serveur**, Ruff et formatage passent. Le vrai scope
1 CPU / 1 Gio / swap0 / 600 tâches a été qualifié puis retiré, sans client
HTTP ni série de charge. `sched_schedstats=0` interdit d'interpréter les
compteurs comme une mesure fiable d'attente ordonnanceur. Aucun sysctl,
quota CPU, seuil de latence ou scénario n'est assoupli.

Preuves : `sis-load-d0c25c75/output/admission100-v1-blocked-final-report.txt`,
`admission100-v2/protocol.txt` et `output/swap-remediation-v1/report.txt`
dans le même dossier de travail. Une nouvelle campagne exige un contrôle
frais des limites effectives, une autorisation et une fenêtre calme distinctes.

### Types de périodes configurables : incrément livré

Les deux variantes utilisent désormais `configuration_academique.catalogs.period_types`
dans le formulaire des périodes/semestres et leurs libellés API. Le catalogue
historique reste le défaut lorsqu'aucun catalogue propre n'est défini.
Le code stocké est conservé lorsqu'il disparaît du catalogue ; il reste
sélectionnable en modification. Les permissions d'écriture, dates, clôtures,
contraintes d'unicité et rattachements à l'établissement ne sont pas modifiés.
Les endpoints de choix ne publient que `code` et `label`, pas les attributs
administratifs supplémentaires du catalogue.

Les régressions ont d'abord échoué sur l'application antérieure : **3 cas
backend secondaire** et **5 cas UI**. Un premier candidat a ensuite révélé
l'exposition d'attributs supplémentaires ; un test l'a reproduite et la
projection explicite l'a corrigée avant toute livraison au principal.
Le candidat final passe **70 tests empaquetés par variante**, sans montage
de sources, incluant calendriers, notes, configuration et organigrammes.
Les **18 tests UI** du formulaire et du gestionnaire partagé passent ;
Ruff, formatage Python, ESLint ciblé et espaces du diff sont conformes.
La revue du petit delta est une revue directe du parent, **pas un audit
indépendant ni une qualification globale de sécurité**.

Une nouvelle fixture indépendante a exercé dans le navigateur les deux
variantes : création d'année/période, choix configuré, retrait de code,
modification conservatrice, refus des dates hors année et des modifications
après clôture, rendu responsive et vraie déconnexion. La mise à niveau vers
le candidat final puis sa reprise ont conservé comptes, calendriers et données.
Les services de cette fixture sont arrêtés ; l'ancienne fixture organisation
n'a pas été réactivée.

Backend livré : **`lms-sis:local-20261105-calendar-catalogs2`**,
`sha256:8bf604164094446e676cff798f449a46353b5ff724599f6d3e6d5c454085d09a`.
Frontend : **`lms-sis-frontend:local-20261105-calendar-catalogs1`**,
`sha256:d035c78b95fbd7e71690b2044d71f8ab531ea942f481efe9f99a96e50d8148f6`.
Les cinq fichiers backend sont ajoutés au-dessus de `business-roles3` ;
aucune migration, règle CSS ou refonte du design ERP n'est introduite.

Sur le principal `http://sis.validation.localhost:58623`, livraison,
redémarrage complet, sept images de services et workers outbox sont vérifiés.
Les parcours avec l'administrateur/MFA existants chargent les choix réels,
ouvrent puis annulent le formulaire sans écriture métier, et parcourent ERP,
intégration, identités, organigrammes, évaluations/notes et réclamations avant
déconnexion, aux largeurs 1440, 1024, 390 et 320.
Les 17 sources applicatives suivies, comptes/MFA, permissions/scopes,
identités, dossiers, calendriers, réclamations, mappings et états d'accès LMS
sont contrôlés après reprise. Sauvegarde avant **48 snapshots / 96 packs**,
finale **49 / 98**, lecture intégrale réussie.

Preuves dans `calendar-catalogs` : `backend-candidate.json`,
`backend-candidate-r1.json`, `metadata-baseline-r1.log`, `changes-r2.diff`,
`packaged-tests-r2.log`, `frontend-tests.log`, `qualification.json`,
les preuves navigateur et de persistance fixture, `final-proof.json`,
`data-final.json`, `authorization-final.json`, les journaux navigateur du
principal et `backup-after.log`.

**Portée :** ce raccordement ne suffit pas à valider toute l'exigence `1.3`.
Les règles propres aux vacances, stages, inscriptions ou publications ne sont
pas créées par le seul nom d'un type. Les scénarios de tous les rôles,
l'ensemble F04/F14 et la capacité500 restent ouverts.

### Diagnostic admission100-v2 : passage vert, capacité500 non qualifiée

Le passage unique a démarré le **5 novembre 2026 à 09:41:17.634751 UTC**,
après reprise directe du parent : l'agent interrompu par une panne réseau
n'avait lancé aucun essai. Les 103 artefacts du kit sont inchangés.
Les préconditions ont été renouvelées : sauvegarde intégralement relue,
cohorte et fenêtres, sources, migrations, TLS, quatre configurations Gunicorn,
zéro session/broker et limites effectives. Les quatre services avaient bien
`memory.swap.max=0` **et** `memory.swap.current=0`.
Le préflight et le client ont partagé le même scope vérifié, plafonné à
1 CPU / 1 Gio / swap0 / 600 tâches.

Sur la fixture `https://load-secondaire.localhost:60031`, toujours en
**image113**, les 100 comptes d'origine (60 élèves, 30 enseignants,
10 direction) ont atteint la barrière après 750 secondes de rampe.
Le plateau de 12 secondes est complet : **253 cycles**, **159 messages**
et **94 appréciations**, sans écriture indéterminée. Les 1 566 requêtes
comptent zéro échec : 1 466 réponses200 et 100 refus401 attendus après
déconnexion. Le **p95 de charge est de 1 751 ms**, sous le seuil de 2 000 ms ;
p99 2 859 ms et maximum 3 329,61 ms. Les 100 DELETE200 et 100 GET401
de déconnexion sont confirmés par le proxy, sans nettoyage forcé.

Les 257 captures à 100 ms ne présentent ni lacune, ni intervalle perdu,
ni erreur d'observateur. La première vague se répartit entre les workers
7/8/9/10 à hauteur de 28/28/24/20 requêtes : l'ancienne concentration
sur le worker10 n'est pas reproduite. L'API présente toutefois 67 périodes
de bridage CPU sur les intervalles métier observés, et aucun blocage
PostgreSQL n'est observé dans les échantillons.
La capture et l'émission de l'observateur consomment respectivement
1,886 et 0,077 seconde CPU sur une série d'environ 25,7 secondes.
Les attentes des journaux synchrones sont également mesurées et ne sont
pas négligeables ; leurs durées agrégées entre threads ne sont pas une
durée réelle d'exécution et leurs étapes imbriquées ne doivent pas être
additionnées. `sched_schedstats=0` interdit toujours l'interprétation
de l'attente ordonnanceur ; aucun diagnostic de GIL n'est établi.

La sauvegarde après passage a été intégralement relue. Les 132 tables
et 24 pièces protégées, zéro session et zéro clé broker authentifié sont
vérifiés après restauration de l'API/proxy ordinaires. Les sondes et leurs
bytecodes sont archivés puis retirés, le scope est absent et les limites
effectives restent conformes. La fenêtre calme a été explicitement libérée
après au moins 1 200 secondes depuis T0.
Deux erreurs du contrôleur de clôture (casse du message Docker et contrôle
Redis sans authentification) ont été conservées, corrigées puis revérifiées ;
elles n'ont modifié ni les données, ni le kit, ni le résultat du passage.

Preuves : `sis-load-d0c25c75/output/admission100-v2-` suivi de
`sessions.json`, `independent-verdict.json`, `analysis.json`,
`process-result.json`, `restored.json`, `window-release.json`,
`checksums.json` et du dossier `final-traces`.
Le principal **8bf604/d035c78**, ses comptes/MFA, son design et sa
sauvegarde **49 snapshots / 98 packs** restent inchangés.

**Portée :** ce diagnostic instrumenté de 100 utilisateurs pendant
12 secondes ne qualifie ni **500 utilisateurs pendant 120 secondes**,
ni l'image du principal, ni l'ensemble des fonctions. L'évolution des
historiques, la nouvelle instrumentation et le rétablissement du swap
interdisent d'attribuer causalement l'amélioration à un seul changement.
Les anciens résultats rouges ne sont pas remplacés.

### Mise à jour des notes : audit conservé, lectures superflues supprimées

Le diagnostic précédent a identifié environ 86 requêtes SQL par PATCH de
note. `django-auditlog` 2.3 relisait notamment les relations d'auteur
inchangées pour comparer tous les champs. Le correctif fait enregistrer
aux deux `NoteSerializer` les seuls champs validés, avec `save(update_fields=...)`.
Il conserve `Model.save`, les signaux et la validation des offres.
Les métadonnées de modification ajoutées par le serveur restent enregistrées ;
la création, les permissions, verrous, clôtures et formulaires sont inchangés.
Aucun réglage `search_path`, mécanisme d'audit ou contrôle d'accès n'est désactivé.

La régression échoue sur l'image précédente dans **les deux variantes** :
trois relectures du même auteur, contre au plus une après correction.
Le journal conserve les valeurs avant/après, la représentation de la note et
l'horodatage ; un PUT avec changement d'apprenant reste persisté et audité.
Un résultat refusé ne laisse ni modification de note ni entrée d'audit.
Un premier compteur de test du supérieur comptait aussi un apprenant ;
il a été corrigé pour cibler la clé de l'auteur, puis son échec sur l'image
précédente a été reconfirmé.

Le candidat passe **50 tests empaquetés par variante**, sans montage de
sources, couvrant notes, audit, calendrier/verrous concurrents et habilitations.
Ruff, formatage et espaces du diff sont conformes. La revue porte sur le
petit delta exact extrait de l'image précédente, pas sur toute la sécurité
de l'application.

Backend livré et redémarré :
**`lms-sis:local-20261105-grade-audit1`**,
`sha256:13b5c47c1b0b0ab6a8adfccd8c4435b6216f63e0200cf4322b65e3227b1aa2cc`.
Frontend **d035c78** et design inchangés. Les sept services, workers outbox,
18 sources applicatives, comptes/MFA, autorisations, calendriers, dossiers,
réclamations et mappings sont vérifiés après reprise.
Les parcours navigateur réels avec le compte/MFA existants couvrent ERP,
calendriers, intégration/outbox, identités, organigrammes, notes et réclamations,
aux largeurs 1440/1024/390/320, avec déconnexion. Ils restent en lecture seule
sur le principal : les écritures de régression sont exercées dans les bases
isolées des tests, pas sur les dossiers de l'établissement.
Sauvegarde avant **50 snapshots / 100 packs**, finale **51 / 102**,
snapshot `63256d1a`, intégralement relue.

Preuves dans `grade-audit/` : `changes.diff`, les deux journaux `baseline`,
`packaged-tests.log`, `qualification.json`, `backend-candidate.json`,
`final-proof.json`, `data-final.json`, `authorization-final.json`,
les parcours `browser-initial` / `browser-persistent` et `backup-after.log`.
**Portée :** réduction ciblée de requêtes, sans nouvelle mesure de latence
ni qualification500 du nouveau backend. Le diagnostic100 précédent portait
sur l'image113, pas sur ce candidat.

### Backend courant : passage100/120s rouge, clôture vérifiée

Le passage non instrumenté du 5 novembre 2026 utilise l'image **13b5c47c**
sur la fixture HTTPS60031, pas le principal. Les quotas restent inchangés :
API4CPU/2GiB, quatre workers de huit threads, rampe750s, délai HTTP5s,
pause3s et seuil p95 de2s. Les 100 utilisateurs s'authentifient ; les
10522 requêtes comprennent 10421 réponses200, une502 et 100 réponses401
attendues après déconnexion. Les 3239 cycles confirmés comprennent
1942 messages et 1297 mises à jour d'appréciation. Le p95 est **819ms**,
le p99 **1392ms**, le maximum **2455,82ms**, sans timeout client.

**Le résultat reste rouge.** Une502 sur l'ajout d'un message interrompt
l'acteur35 après deux cycles : la cohorte complète ne tient que
**10,342 secondes**, et non les120 secondes demandées. Le client conserve
une écriture sans confirmation et un résultat de relecture indéterminé.
La réconciliation indépendante retrouve les cycles confirmés, sans
écriture partielle supplémentaire ni violation détectée ; elle ne transforme
pas l'absence de reçu en réussite. Les100 DELETE200 et100 GET401 de clôture
sont réels, sans nettoyage forcé ; aucune session ni tâche broker ne reste.
Les132 tables,24 pièces,1447 sources, quotas et swap effectif max/current0
sont préservés. Aucun OOM n'est observé dans les échantillons.

La fenêtre est explicitement libérée le **2026-11-05 à13:04:04,148037UTC**,
5890,093 secondes après T0. Le scope a disparu et l'API ordinaire13b reste
en place. Les48 prérequis sont inchangés ;58 artefacts de résultat sont
scellés dans `output/current-release100-checksums.json`,
SHA256 `3bdd0a5d72f66f1bcd28cea22df9f96fc2a99521763cf2f44e675c041b520ebc`.
Le journal API vivant n'est pas scellé : seule sa copie figée l'est.
Le principal13b/d035 et sa sauvegarde51/102 ne sont pas modifiés.

### Ruptures amont : reproduction isolée et candidat proxy

À11:38:28UTC, Nginx enregistre deux resets amont. Le POST échoue en une
tentative ; le GET distinct réussit après une seconde tentative amont.
Le journal de cycle de vie API ne contient que les quatre démarrages initiaux,
sans timeout, arrêt, redémarrage ou exception enregistré. Les anciens journaux
ne permettent pas d'identifier le socket amont ni le worker concerné :
**la cause exacte de cet incident n'est pas démontrée**.

Un montage isolé reprend les mêmes images Gunicorn22/Nginx, sans SIS,
base de données, identifiants ni port hôte. Un worker réservé au test suspend
brièvement la fenêtre entre la sélection des sockets et leur fermeture
pour expiration, puis appelle le traitement Gunicorn non modifié.
Des octets POST/GET sont observés sur le socket expiré avant sa fermeture :
le POST obtient502 sans écriture ; le GET est retenté et obtient200.
Cette reproduction établit un mécanisme possible, pas une preuve rétrospective
de l'ordonnancement de la campagne.

Le candidat `load_tests/fixture-nginx.conf` retire le cache de connexions
amont et transmet `Connection: close`. Les connexions TLS côté client restent
inchangées. Aucun retry d'écriture n'est activé, aucun délai ni quota augmenté.
Dans le même montage, dix requêtes réussissent sans retry, dont six écritures
uniques avec corps vérifié, y compris quatre envoyées par deux clients
concurrents. Chaque requête atteint l'application via un nouveau port amont.
Le coût des nouvelles connexions TCP devra être mesuré sous charge.
Les journaux candidats ajoutent l'heure, les millisecondes, l'adresse et le
statut amont pour éviter les limites de corrélation constatées.

Preuves : `upstream-reset-lab/{baseline,candidate}/`, notamment les journaux
de planification, reçus application/proxy, `verdict.json` et `cleanup.json`.
Les conteneurs du montage sont supprimés après chaque phase.
Les29 tests hors serveur du générateur restent verts.
**Ce contrôle de transport ne qualifie ni100/120s, ni500 connexions,
ni la couverture fonctionnelle globale.**

Le proxy de fixture est rechargé le5 novembre à13:20UTC après `nginx -t` :
le worker176 est sorti, le203 est actif, et une réponse HTTPS200 comporte
les nouveaux champs amont. Les quatre conteneurs, l'API13b,1447 sources,
quotas et protections sont inchangés ; zéro session/broker.
La configuration persistée correspond au candidat testé,
SHA256 `a56712e5234975120a9e84e8fafcbb1fc269c32d4d913f814e9b22e0850ce2a7`.
Preuves : `output/proxy-close-{before,after}.json`.
L'ancien manifest48 n'est pas réécrit : son entrée de configuration vivante
se vérifie désormais sur la copie figée
`output/current-release100-live-prerequisites/profile-nginx.conf`.
Cette filiation est explicite dans les nouveaux contrôles, sans ignorer
l'ancienne empreinte ni masquer le changement de configuration.

### Proxy corrigé : qualification100/120s verte

Un protocole distinct `transport-readiness/` conserve les100 acteurs,
100 objets, quotas, délais et seuils précédents. Les historiques évolués
comptent2638 entrées avant passage :59 réclamations longues et une moyenne.
Les droits, calendriers, migrations,500 identités d'origine et132 tables/
24 pièces sont revérifiés sans remise à zéro ni extension de permissions.
Le kit de80 artefacts est scellé ;11 tests hors serveur et les contrôles
de formatage passent. Aucun redémarrage ni changement de l'API13b.

T0 : **2026-11-05 à13:24:49,128481UTC**, puis rampe750s.
La cohorte complète tient cette fois **120 secondes** :
**10762 requêtes, zéro échec, zéro timeout**, avec10662 réponses200 et
100 réponses401 attendues. Les3319 cycles confirmés comprennent2002 messages
et1317 appréciations de notes. Le **p95 de charge est637ms**, le p99
1481ms, le maximum2647,22ms ; le p95 toutes phases est696ms.
Les200 contrôles d'intégrité client passent, sans écriture non confirmée
ni résultat indéterminé. La vérification indépendante retrouve les écritures
persistées sans violation détectée.

Nginx ne signale **aucune erreur ni nouvelle tentative amont**.
Les100 déconnexions DELETE200 et100 refus GET401 sont réels ;
aucun nettoyage forcé, aucune session ni tâche broker restante.
Les132 tables,24 pièces,1447 sources, quotas et swap max/current0 restent
conformes, sans OOM échantillonné. La sauvegarde après passage est
intégralement décodée. Le scope a disparu et la clôture libère explicitement
la fenêtre à **13:44:56,231256UTC**, après1200,349 secondes.
Le proxy corrigé et l'API ordinaire restent en place.

Preuves : `output/transport100-{analysis,independent-verdict,independent-integrity,
sessions,closure}.json` et journaux associés. Les42 artefacts de résultat
sont scellés dans `output/transport100-checksums.json`,
SHA256 `45849ca5e8800b3fbd212bd3eddb0e9cb8a16a02bee774ab28f81daac90458cf`.
Le kit80 porte l'empreinte
`ae636673dce83a95cb1c605d0d46c7b749726e0210d0817ab9ca43a614b437c7`.

**Limite importante :500 connexions ne sont toujours pas qualifiées.**
Sur120,082 secondes de plateau échantillonné, l'API consomme en moyenne
3,761 CPU sur4, avec819 périodes bridées sur1188 ; PostgreSQL utilise
1,160 CPU sur2. La marge CPU est donc faible dès100 acteurs.
Ce passage vert ne démontre ni une capacité multipliée par cinq, ni une
causalité A/B des latences, ni la couverture de toutes les fonctions LMS/SIS.
Les précédents résultats rouges sont conservés et aucune nouvelle campagne
n'est autorisée par cette clôture.

### Palier500 courant : saturation et résultat rouge conservé

Le passage suivant utilise les500 acteurs et objets du manifeste d'origine,
sans réallocation :300 élèves,150 enseignants,50 membres de direction,
6262 entrées d'historique avant passage. Les132 tables et24 pièces sont
comparées à la clôture100 avec son ancienne sélection **avant** de calculer,
dans le même instantané en lecture seule, la protection adaptée aux500 acteurs.
Le kit distinct de112 artefacts passe15 tests hors serveur, formatage et
validation du manifeste. Les quotas restent inchangés, dont API4CPU/2GiB,
proxy0,5CPU et générateur1CPU ; aucun ajustement des seuils ni protections.

T0 : **2026-11-05 à14:06:52,245652UTC**, rampe3600s, plateau visé120s,
pause3s, délai HTTP5s et p95 maximal2s. Les500 utilisateurs s'authentifient,
mais la cohorte complète ne tient que **9,768 secondes** :
**zéro cycle métier complet,500 timeouts**, p95 **5888ms**, p99 **6005ms**,
maximum **6169,72ms**. Les5238 requêtes client comprennent4238 réponses200,
500 erreurs de transport et500 réponses401 attendues. Les762 échecs comptables
comprennent les500 timeouts et262 relectures indéterminées ;262 écritures
restent sans confirmation côté client.

La réconciliation retrouve **500 mutations persistées** :300 messages et
200 appréciations de notes, sans violation détectée des données protégées.
Cela ne valide pas les cycles interrompus et ne transforme pas les écritures
sans reçu en succès client. Les500 DELETE200 et500 GET401 de déconnexion sont
réels, sans nettoyage forcé ; aucune session ni tâche broker restante.
Les132 tables,24 pièces,1447 sources, quotas et swap effectif max/current0
sont conservés ; aucun OOM échantillonné. La sauvegarde après passage est
intégralement décodée.

Le proxy ne présente aucune erreur amont ni retry : ses journaux comptent
4239 réponses200,499 réponses499 et500 réponses401. Ces observations serveur
ne valent pas confirmation de réception par le client. Sur10,005 secondes
d'activité échantillonnée, l'API consomme **3,990 CPU sur4**, avec
**98 périodes bridées sur100**. Le proxy et le générateur sont aussi bridés
par rafales, respectivement48 et34 périodes sur100. La saturation est
observée ; ces mesures ne désignent pas encore une fonction Python précise
ni la répartition des requêtes entre workers.

**Correction d'un faux positif du contrôleur :** le contrôle additionnel
d'auteur comparait par erreur la clé `User` à `Note.modifie_par`, qui référence
`enseignants.Personnel`. La vérification en lecture seule via `Personnel.user`
confirme les200 attributions. Les valeurs brutes avant/après/finales/en base
sont identiques : la normalisation erronée n'a été appliquée à aucune ligne
observée. Une régression avec des clés User/Personnel différentes vérifie
le correctif du contrôle. Le premier essai d'addendum, arrêté sur un nom
d'application présumé incorrect, et sa sortie vide sont également conservés.
Le kit112 et le verdict initial ne sont pas réécrits ;
`output/current500-author-correction-v2.json` apporte cette correction limitée.
**Les500 timeouts et262 résultats indéterminés restent rouges.**

Clôture explicite à **15:17:00,053470UTC**, après4200,349 secondes :
scope supprimé, API13b et proxy corrigé ordinaires conservés,
aucune nouvelle campagne autorisée. Les48 artefacts de résultat et d'addendum
sont scellés dans `output/current500-checksums.json`,
SHA256 `ce4886db66b7c43105f77543aaac61f79f20b1352b290f8497114b541872658a`.
Contrôleurs : `current500-readiness/checksums.json`,
SHA256 `801b0906d67fd947c7a86cf66a1b928cdc5fd872c26e52a8f121bb6e5282106e`.
Le principal, sa sauvegarde51/102 et le design ne sont pas modifiés.
La qualification100 demeure verte dans son périmètre ; **500 et la recette
fonctionnelle globale ne sont pas validés**.

### Réclamations : suppression du rendu redondant avant mutation

Un diagnostic de composant en lecture seule sur l'image13b exécute15 GET
avec les acteurs synthétiques : réclamations courtes/médianes/longues
(jusqu'à105 entrées), notes enseignant et direction. Il conserve permissions
et scopes mais exclut l'authentification de session, les middleware et le
transport HTTP. Les temps CPU incluent le coût du profileur ; le premier
appel contient également des imports à froid. Il ne s'agit ni d'un benchmark
de latence ni d'une nouvelle qualification de charge. Le wrapper SQL observe
7 SELECT et7 SET par GET réclamation,3+3 pour une note enseignant et5+5
pour une note direction, sans garantir une capture exhaustive côté PostgreSQL.

L'inspection identifie un travail redondant distinct du N+1 déjà corrigé :
les actions affectation/message/transition/pièce chargeaient et sérialisaient
tout l'historique pour consulter uniquement le champ `actions`, puis
rechargeaient et sérialisaient l'historique après modification.
Elles utilisent désormais **la même méthode `ComplaintSerializer.get_actions`**
directement. La lecture verrouillée préalable ne précharge plus historique
et pièces ; le rechargement final est conservé. Droits, version, verrou de ligne,
transactions, audit, notifications et règles de pièces jointes restent inchangés.

La régression existante est renforcée sur des historiques de10 et30 entrées :
**une seule lecture de l'historique final**, contre deux sur l'ancien backend,
avec noms d'auteurs et dernier message à jour. L'ancien13b échoue explicitement
sur cette assertion. L'image candidate passe **18 tests secondaire et18 supérieur**,
incluant workflow, refus d'accès, révocation, isolation, annulation transactionnelle
et nettoyage des pièces. Aucun nouveau diagnostic Ruff : un B904 et deux PT027
préexistants restent identiques à l'image de référence ; ne pas confondre
cette comparaison du delta avec un lint global sans défaut.

Backend livré : `lms-sis:local-20261105-complaint-actions1`,
image `sha256:b8d813e01bfc4c9141e47703345e1f340d23dd0403ae4c9fd46ae624c6be5aba`.
Le frontendd035 et le design ne changent pas. Les sept services contrôlés,
les workers outbox et19 sources applicatives par variante sont vérifiés après
livraison, redémarrage et contrôle final ; comptes, MFA, droits, données,
mappings et hiérarchie sont préservés.
Les parcours navigateur réels ERP/réclamations/notes/calendriers/organigrammes/
identités/outbox/intégration passent après redémarrage, sans écriture métier,
en clair/sombre et aux largeurs1440/1024/390/320 ; les sessions sont déconnectées.
Sauvegarde finale : **53 snapshots,106 packs intégralement relus**.

Preuve de livraison :2026-11-05 à15:54:59,977508UTC.
Les105 artefacts sont scellés dans `complaint-actions/checksums.json`,
SHA256 `23fd7f7de21009cbc18b73e91d1bb9c6dbfdcd431920da4343da641a30470c8a`.
Le diagnostic de composant et l'ancien scellé500 y sont référencés séparément ;
les48 preuves historiques restent inchangées.
**La fixture de charge reste sur13b. Aucun nouveau100/500 n'a été exécuté :
le100 vert historique n'est pas transférable au nouveau backendb8,
et500 reste non qualifié.**

### Backendb8 : nouvelle qualification100/120s verte

Une préparation distincte, puis une autorisation de mise à jour et une
autorisation de passage séparées, remplacent uniquement l'API de fixture13b
par le backendb8 livré. PostgreSQL, Redis, proxy, quotas et protections sont
conservés. Les152 prérequis sont scellés dans
`actions100-readiness/checksums.json`,
SHA256 `f17cd1a324e5fde4523d5a0e5d874a1e619dbd814361481174b8d387955bb113`.
Les14 tests hors serveur, le formatage et Ruff passent.
L'ancienne projection500 est vérifiée avant de protéger plus strictement les
seuls100 acteurs du nouveau passage, dans le même instantané en lecture seule.
Les40 auteurs de notes correspondent aux profilsPersonnel ; leur clé étrangère
reste intégralement protégée, **sans aucune normalisation vers une cléUser**.

La cohorte originale60/30/10 conserve ses100 objets, avec4700 entrées
d'historique et60 réclamations longues au départ.
Le premier aperçu échoue avant le démarrage Django sur les droits du répertoire
de logs ; le second utilise l'UID de fixture et des logs temporaires, sans
écriture en base. Le premier scellé rencontre un cache Ruff temporaire :
il est retiré de façon ciblée, la preuve intermédiaire est conservée.
Aucun de ces essais ne lance de charge.

T0 : **2026-11-05 à16:16:03,851654UTC**. Rampe750s, plateau120s,
pause3s, délai HTTP5s, p95 maximal2s et budgets inchangés.
Résultat : **100 authentifiés, cohorte complète120,0s,3286 cycles métier**,
dont1974 messages et1312 mises à jour de notes.
Les10660 requêtes donnent10560 réponses200 et100 réponses401 attendues,
**zéro échec, timeout ou écriture non confirmée**.
Les200 contrôles d'intégrité client passent, sans résultat indéterminé.
**p95 charge819ms**, p991449ms, maximum2149,22ms ; p95 toutes phases877ms.

Les100 DELETE200 et100 GET401 de déconnexion sont constatés au proxy,
sans nettoyage forcé ; aucune session ni tâche broker restante.
Les132 tables,24 pièces et1447 sources sont préservées ; sauvegarde après
passage intégralement décodée, aucune erreur proxy ni retry amont,
aucun OOM observé, quotas et swap max/current0 conservés.
Sur115,079 secondes échantillonnées, l'API consomme encore3,666 CPU sur4
avec680 périodes bridées sur1138 ; PostgreSQL1,127 CPU sur2.
**Ce résultat ne prouve pas une marge suffisante pour500 utilisateurs.**

Clôture à **16:36:12,451953UTC**, après1200,388 secondes :
scope supprimé, fenêtre libérée, APIb8 ordinaire conservée.
Les44 résultats sont scellés dans `output/actions100-checksums.json`,
SHA256 `5bdc06329e89009a7318830bd7098f8f73d1def76bf39cbe4ee6d2ad59fa95c5`.
Il s'agit d'une nouvelle preuve100 surb8, et non du transfert du succès13b.
Les historiques ont évolué : aucune comparaison causale A/B n'est revendiquée.
**Aucun nouveau500 n'est autorisé par cette clôture ; son dernier résultat
reste rouge et la recette globale demeure ouverte.**

## F07 : protection des inscriptions Open edX préexistantes

Une inscription native `audit` déjà présente, active ou désactivée, n'avait pas
la même protection contre l'adoption implicite qu'un droit enseignant existant :
une première décision SIS pouvait la prendre en charge puis la retirer.
L'API native `/api/sis/v1/courses/.../enrollments/.../` renvoie désormais
**409 avant toute mutation** si cette inscription existe et qu'aucune décision
`ManagedAccess` initialisée ne la possède. Les inscriptions créées par le
service et leurs retraits/rejeux restent possibles ; aucun rôle global ni
inscription historique n'est modifié par ce correctif.

Le défaut est reproduit sur l'ancienne image : une inscription active répondait
200 au lieu de409. Deux tests distincts couvrent les inscriptions préexistantes
active et inactive ; les **10 tests natifs Open edX passent dans l'image finale
sans montage des sources**. Ruff sur E4/E7/E9/F et contrôle de format passent ;
le lint complet conserve les37 diagnostics de l'image précédente, sans nouveau
diagnostic après ajustement des assertions de test.

Image finale `lms-sis-openedx:local-20261105-access-ownership2`,
`sha256:d59d36c491c484abdde7812040bf003de34756215be509f6f432b91b9c3aa418`.
Tutor la conserve dans sa configuration ; LMS, Studio et leurs deux workers
utilisent cette même image. La sauvegarde froide antérieure `f8d3aba8`, puis
la sauvegarde finale `6f5e098d`, ont été prises avant redémarrage ; les
**14 snapshots et31 packs** du dépôt chiffré ont été entièrement relus.
Le contexte de construction final est archivé dans la racine sauvegardée
(`sis-openedx-20261105-access-ownership2-source.tar.gz`).

La première relance du proxy sans la surcouche
`docker-compose.prod.override.yml` a interrompu le port local59080 ;
la relance avec les **quatre** fichiers Compose Tutor l'a rétabli.
Après le redémarrage final, LMS, Studio et apps répondent301/302/302.
Le navigateur ouvre le cours existant dans Studio puis le cours apprenant
avec réponse et score1/1 conservés, sans nouvelle soumission ; les deux
comptes de test se déconnectent. Les empreintes des comptes, mots de passe,
permissions/MFA, autorisations, OAuth, inscription et résultat historique
restent identiques à l'avant, y compris après ce parcours.

Cet incrément améliore seulement l'appartenance des inscriptions ; il ne valide
ni l'affectation universelle d'un candidat neuf, ni tous les cours, ni F07 entier.
La matrice reste à70 partielles,21 absentes,2 non vérifiées et1 vérifiée.
La capacité500 reste rouge et aucune recette globale à100 % n'est annoncée.

## F07 : limites d'établissement sur la synchronisation manuelle SIS

Les routes historiques `sync/user/<id>/` et `sync/course/` acceptaient
`is_staff` sans vérifier l'établissement de l'administrateur ni celui des
objets à synchroniser. Une recette sur l'ancienne image a confirmé deux
provisionnements utilisateur inter-établissements en HTTP200 au lieu des
refus attendus. Les deux SIS exigent maintenant un établissement courant
cohérent pour l'appelant, puis refusent sans appel distant les comptes et
cours rattachés à un autre établissement, y compris via année ou niveau
en secondaire et via semestre ou maquette en supérieur. Le compte sans
établissement et les matières/classes sans établissement restent admis
dans leur schéma courant, comme pour les candidats et données historiques.
Les droits `is_staff` existants ne sont pas élargis.

Tests isolés : **29 secondaire et43 supérieur** verts, dont deux refus
utilisateur et les sources de cours étrangères, avec succès des objets
locaux et compatibilité des anciens tests API. Ces **29+43 tests** sont
également verts dans l'image finale sans montage source. Ruff E/F
passe ; six avertissements PT018 et les différences de formatage hors
lignes nouvelles préexistaient dans les fichiers concernés. L'agent de
diagnostic500 n'a pas établi un coût SQL/CPU significatif des permissions
par réclamation : aucune optimisation spéculative n'a été appliquée.

Image SIS persistante `lms-sis:local-20261105-manual-sync-tenant2`,
`sha256:988ec9f81632ecd0ed5c086fe706002032fbd48d51a9fa6ad3bf88f8210b7e72`.
Les six services applicatifs utilisent cette image après redémarrage,
avec frontend et bases inchangés. Snapshots froids antérieurs
`6a644f12` et `8aad9f9d`, final après redémarrage `de0bd3eb` ;
**56 snapshots et112 packs** relus
intégralement sans erreur. Les deux routes publiques refusent les
requêtes non authentifiées en HTTP401 après sauvegarde. Ces tests
isolés n'exercent aucun compte ou cours réel en écriture ; la recette
institutionnelle complète, les autres routes historiques, F07 et la
capacité500 restent ouverts. Le dernier500 reste rouge, sans nouveau
passage autorisé ni revendication de100 %.

## F02/F07 : administrateurs d'intégration limités à leur établissement

Après la protection des routes `sync/user` et `sync/course`, les autres
routes administratives pouvaient encore être appelées par un `is_staff`
d'un établissement étranger. Sur l'image précédente, les deux SIS
renvoyaient notamment HTTP200 pour l'état, les listes de mappings et
la santé LMS ; publication, activation de visio, notes et certificats
atteignaient aussi leur logique métier avant le contrôle d'établissement.
Une permission commune vérifie désormais le rôle administratif **et**
la cohérence entre établissement de l'appelant, tenant HTTP et schéma
actif avant toute lecture, validation ou opération distante. Les
webhooks signés et les décisions d'accès LMS gardent leurs propres
contrôles ; les administrateurs locaux et les comptes historiques sans
établissement conservent leurs accès.

Le défaut a été reproduit sur les deux variantes. Dans l'image finale,
**52 tests secondaire et50 supérieur** passent sans montage source,
dont les refus sur toutes les routes administratives, les schémas
incohérents, les droits locaux et les contrats de publication et d'accès
existants. Ruff complet sur les quatre fichiers touchés et le format
des lignes nouvelles passent.
Image persistante `lms-sis:local-20261105-integration-admin-tenant1`,
`sha256:934fcba6c1b139bde15d393b0286f753dd2596e4cd4dbc038f440e79a426b321`
sur les six services SIS, sains après redémarrage. Avant livraison,
snapshot `dc4da52d` ; après redémarrage, `1b26df04`.
Le dépôt chiffré final est intégralement vérifié :
**58 snapshots et116 packs, sans erreur**. Le frontend reste accessible
en HTTP200 et les mappings des deux SIS refusent les appels
non authentifiés en HTTP401.

Ce contrôle ne démontre ni les permissions métier de tous les profils
ni l'isolation de toutes les autres API ; les94 exigences et F02/F07
restent ouverts. Aucun nouveau test à500 connexions n'a été exécuté :
le dernier reste rouge.
