# Utiliser le SIS selon sa responsabilité

Édition du **9 novembre 2026**, fondée sur les parcours existants à `fa8ac06`.
Ce guide est destiné à la formation et à la réception d'une **livraison
intermédiaire**. Il ne présente pas tous les menus comme des métiers terminés.
Les [preuves et limites datées](RESTE_A_FAIRE_ET_VALIDATION.md) font foi :
bulletin secondaire réellement déployé/testé dans la démonstration isolée,
mais aucune production homologuée ni réception institutionnelle globale.

## Avant la première connexion

Demandez à votre établissement l'URL, le SIS concerné (**Secondaire** ou
**Supérieur**), votre compte nominatif et le contact de support. Ne partagez
ni mot de passe ni code MFA. La démonstration contient des personnes fictives :
ne la remplissez pas de dossiers réels sans autorisation.

1. Connectez-vous sur l'URL reçue et vérifiez le nom de l'établissement.
   Une identité Open edX ne remplace un compte local que si le SSO a été
   explicitement raccordé. Ne créez pas un second dossier pour contourner un refus.
2. Ouvrez **Mon compte** pour configurer le MFA local. Gardez les moyens de
   secours selon la procédure de votre établissement. La récupération du mot
   de passe ne désactive pas le MFA ; sa perte nécessite une assistance contrôlée.
3. Les espaces **Scolarité**, **Pédagogie**, **Vie de l'établissement**,
   **Documents**, **Suivi et accès**, **Administration** et leurs onglets dépendent
   de vos droits. Un intitulé de rôle ou `is_staff` n'accorde pas tous les droits.
   La palette **Ctrl+K / ⌘K** cherche les modules autorisés, pas les dossiers.
4. Sur téléphone, ouvrez le menu puis l'onglet métier ; faites défiler le
   tableau dans son propre cadre si nécessaire. Au clavier : Tab parcourt
   les commandes, les flèches/Entrée choisissent dans la palette, Échap la ferme.
   Les préférences clair/sombre et favoris restent locales à ce navigateur.
5. Déconnectez-vous sur un appareil partagé. Un téléchargement reste un fichier
   privé sur cet appareil : ne l'envoyez pas dans une conversation publique.

Les parcours ci-dessous décrivent des **responsabilités**, pas des droits
attribués automatiquement. Si un bouton manque ou une action est refusée,
demandez la vérification de l'habilitation et du périmètre ; ne passez pas par
le compte d'un administrateur.

## Administrateur de l'établissement

Dans **Administration**, vérifier l'établissement, l'année et ses périodes,
la structure puis les comptes. Utiliser des comptes distincts pour administrer,
enseigner, publier et consulter ; ne pas utiliser le superutilisateur initial
comme compte de travail collectif.

Dans **Utilisateurs**, attribuer les groupes/permissions nécessaires uniquement
aux personnes concernées. Après une modification, faire revérifier avec leur
propre compte l'action autorisée **et** le refus sur un dossier voisin.
Les groupes de permissions ne constituent pas une preuve d'achèvement du
modèle complet de rôles métier. Retirer un droit ne supprime pas le dossier.

### Choisir le périmètre activable

Dans **Établissement → Modules**, relever l'état **effectif** du catalogue
installé, puis, pour une modification autorisée : indiquer le motif,
**Simuler les modules**, examiner les impacts, **Appliquer les modules**.
Un conflit de révision exige de recharger avant de recommencer.

| Module préinstallé | État par défaut à cette édition | Limite à connaître |
|---|---|---|
| Identité/autorisations et historique/notifications | Obligatoires | Le noyau notifications ne prouve pas une livraison email/SMS. |
| Réclamations privées (`sis.complaints`) | Activé | Affectation et traitement exigent des permissions distinctes ; demande parent pour enfant non couverte. |
| Missions (`sis.delegations`) | Activé | Mission datée et révocable, sans changement de rôle ni accès global aux notes/finances. |
| Projets pédagogiques (`sis.projects`) | Désactivé | Évaluation de projet distincte d'une note officielle ou d'un crédit acquis. |
| Agenda (`sis.events`) | Désactivé | Invitations et accès privés ; voir le [guide événementiel](institutional-events.md). |
| Enquêtes (`sis.surveys`) | Désactivé | Réponses nominatives, pas anonymes ; voir le [guide enquêtes](institutional-surveys.md). |
| Recherche (`sis.research`) | Désactivé, supérieur seulement | [Guide recherche](research.md) ; sous-livre financier interne, pas ERP général. |

Cette liste décrit le registre de la version, **pas tous les menus**, ni
l'état d'un établissement déjà configuré. Les droits restent indispensables
après activation. La désactivation conserve les données ; elle n'est pas une
suppression ni une révocation des opérations externes déjà engagées.
Les options pédagogiques, profils d'offres, cours Open edX, SMS, paiement,
applications mobiles et prestataires ne sont pas installés par ces interrupteurs.

Pour l'installation, les migrations, les clés, sauvegardes et restaurations,
passer à l'opérateur technique : [guide établissement](INSTALLATION_ETABLISSEMENT.md).
Une commande technique n'est pas nécessaire pour accomplir les parcours usuels
ci-dessous ; une action qui la nécessite encore reste à signaler à la réception.

## Scolarité : dossier et inscription

**Secondaire**

1. Dans **Années académiques**, préparer l'année ouverte et les périodes.
   Dans **Structure**, puis **Classes**, préparer niveau, matières et classe.
2. Dans **Élèves**, créer le dossier civil. **Ne pas affecter directement une
   classe dans ce formulaire** : celle-ci vient d'une inscription validée.
3. Dans **Classes → Inscriptions annuelles**, créer l'inscription de l'élève
   pour l'année/classe choisie. Vérifier le dossier puis utiliser **Valider**.
4. Revenir au dossier : contrôler année et classe. Un simple enregistrement
   d'inscription en attente ne doit pas affecter la classe.

**Supérieur** : préparer formation et année, créer le dossier dans
**Étudiants**, puis traiter **Inscriptions administratives** et les affectations
pédagogiques du semestre. Une inscription administrative ne remplace pas
l'inscription pédagogique requise pour la saisie des notes.

Pour les imports, télécharger le modèle de la liste, garder ses colonnes,
utiliser des dates `AAAA-MM-JJ`, **prévisualiser** puis confirmer.
CSV UTF-8 à virgules ou XLSX : 5 Mo et 1 000 lignes maximum. Une erreur bloque
le lot ; ne pas découper le fichier pour masquer un doublon divergent.

**Réinscrire / changer de cursus** crée une nouvelle demande à examiner dans
une année postérieure ; cela ne réécrit pas les anciens résultats. Un transfert
simple exige un motif et reste refusé sur les dossiers incompatibles (notes,
acquis ou règles historisées selon le circuit). Ne pas effacer ces données
pour forcer le transfert. Année close, candidature externe complète,
équivalences et transferts interétablissements ne sont pas présumés disponibles.

## Enseignant : saisir et vérifier une évaluation

1. Ouvrir **Évaluations** au secondaire ou **Notes** au supérieur. Si l'accès
   est refusé, faire vérifier l'affectation et les permissions, pas seulement
   l'intitulé « enseignant ».
2. Choisir la classe/formation, l'évaluation et la période ouvertes ; contrôler
   barème, coefficient et liste des apprenants autorisés.
3. Dans **Saisir les notes**, renseigner uniquement les résultats concernés.
   Laisser une note manquante vide ; ne pas saisir zéro pour une absence.
   Un résultat renseigné exige le statut **Présentée**.
4. Enregistrer, lire l'éventuel refus et recharger pour vérifier la persistance.
   Le lot est transactionnel : un résultat hors barème ou hors périmètre
   empêche son application. Une offre par compétences n'est pas convertie en
   moyenne chiffrée.

Ce formulaire couvre le contrôle continu non anonyme, pas toutes les règles
d'examen/jury. Saisir une note ne publie ni bulletin ni diplôme.
L'accès à un cours Open edX, aux remises et corrections LMS dépend d'un
raccordement réellement qualifié ; un indicateur de santé seul ne le démontre pas.

## Gestionnaire des résultats : bulletin numérique secondaire

Permissions explicites : `notes.view_bulletin`, `notes.change_bulletin` et,
pour préparer, `notes.add_bulletin`, avec le périmètre de classe autorisé.
L'établissement doit faire approuver ses règles de calcul par son référent métier.

1. Ouvrir **Pédagogie → Bulletins** et préparer un brouillon pour un élève
   inscrit dans la classe et l'année de la période.
2. Vérifier les sources, barèmes et coefficients. Le protocole
   `moyenne_ponderee_20_v1` ramène les notes sur 20, pondère les évaluations par
   coefficient × pondération / 100, puis les matières par leurs coefficients
   de programme ou, à défaut, de matière. L'arrondi final seul est à deux
   décimales, demi supérieur.
3. Une note manquante/absente/non rendue/non chiffrable bloque le calcul ; une
   dispense explicite ou une pondération nulle est exclue et signalée. Lire le
   détail plutôt que de compléter arbitrairement la source par zéro.
4. Saisir l'appréciation et, si pertinente, la décision facultative ;
   **Valider après vérification**, puis **Publier le bulletin**.
5. Faire vérifier par l'élève son document publié et son PDF. Un brouillon
   n'est pas un document destiné à l'élève, même si le gestionnaire peut le lire.

Si les sources ont changé, recharger puis recalculer le brouillon : **cela
annule la validation et les appréciations précédentes**. En cas de conflit,
ne pas répéter aveuglément la publication. Le bulletin calculé publié est
immuable dans ce circuit ; une correction après publication nécessite un
circuit de rectification distinct, pas une modification directe des sources
figées. Compétences, barèmes ne commençant pas à zéro, parcours individualisés,
rang, passage, crédits et diplômes ne sont pas décidés par ce calcul.

Le PDF ordinaire est généré à partir des résultats figés mais son en-tête
institutionnel reste courant : ce n'est pas une archive PDF cryptographique.
Les [versions signées archivées](INSTALLATION_ETABLISSEMENT.md#signatures-approuvées-et-versions-archivées)
relèvent d'un autre circuit, sans qualification juridique automatique.

## Élève, étudiant ou doctorant

Ouvrir son espace apprenant, vérifier le dossier puis les onglets résultats,
documents et démarches autorisés. **Mes documents → Télécharger le PDF**
permet au secondaire de télécharger ses bulletins publiés ; au supérieur,
les relevés signés et transcripts/attestations administrativement validés
selon le document. L'absence d'un brouillon dans cet espace est attendue.

Comparer identité, période et résultat. En cas d'erreur, ne pas créer un
second dossier : demander une vérification à la scolarité ou utiliser
**Mes réclamations** si le module est actif. Indiquer objet, motif et référence
sans joindre les données d'une autre personne. Les pièces admises sont des
PDF privés (dix au plus, 25 Mo chacun dans la configuration standard) ; le
contrôle de format n'est pas une analyse antivirus.

**Mes missions** ne donne accès qu'aux dossiers résumés explicitement délégués,
pendant la période autorisée ; ce n'est pas un changement de rôle.
Les liens LMS, factures et autres onglets ne garantissent pas qu'un paiement
en ligne ou un cours réel soit activé dans cet établissement.

## Parent ou tuteur

Au secondaire, ouvrir l'espace famille avec son propre compte. Un lien familial
autorisé doit rattacher l'enfant ; vérifier l'enfant sélectionné avant d'ouvrir
ses résultats ou **Mes documents**. Seuls ses bulletins publiés doivent être
accessibles. L'absence de lien/révocation doit retirer l'accès, y compris au PDF.

Signaler un enfant absent ou une identité erronée à la scolarité avec une
vérification d'identité hors canal public. Ne jamais emprunter le compte de
l'enfant. Les réclamations au nom de l'enfant et le portail familial supérieur
complet ne sont pas promis par ce guide. Un champ « parents prévenus » dans un
formulaire de vie scolaire consigne une action ; il ne prouve pas l'envoi d'un SMS.

## Comptabilité, services et partenaires

**Comptabilité** : les écrans et permissions disponibles ne constituent pas
une certification comptable/pays. Rapprocher toute facture, référence, montant,
devise et statut avec la pièce/source avant validation. Un bouton, une réponse
HTTP ou une notification interne ne prouve pas l'encaissement auprès d'une banque.
Face à un statut inconnu, une coupure ou un doublon, conserver la référence et
demander une réconciliation ; ne pas recréer le paiement pour « réessayer ».

**Services habilités** : suivre le [guide bibliothèque](digital-library.md),
le [guide recherche](research.md), le [guide agenda](institutional-events.md)
ou le [guide enquêtes](institutional-surveys.md) pour le module effectivement
ouvert. Ils précisent leurs commandes, permissions et exclusions.

**Partenaire/tuteur de stage** : un rôle « partenaire » ne donne pas accès à
tous les apprenants. N'utiliser que l'affectation et le parcours de stage
explicitement ouverts pour ce compte. Le lot pratique distinct n'est pas
déclaré déployé par ce guide ; ne pas en déduire une convention signée, une
soutenance validée, des crédits ou une note officielle.

## Opérateur et assistance : quand arrêter, quoi transmettre

L'opérateur utilise [installation/mise à jour/retour arrière](INSTALLATION_ETABLISSEMENT.md),
[sauvegarde/restauration](BACKUP_RESTORE.md) et [supervision](MONITORING.md).
Avant ouverture, faire exécuter la
[checklist existante de réception](RECETTE_FONCTIONNELLE.md#checklist-de-livraison-intermédiaire-f30-f31),
avec des comptes par rôle, une restauration et des contacts de support désignés.
Une simple sauvegarde réussie ne prouve pas que le service peut être restauré.

| Situation | Conduite à tenir |
|---|---|
| Session expirée / 401 | Se reconnecter ; vérifier si la dernière opération a été enregistrée avant de la rejouer. |
| Refus / 403 ou objet indisponible / 404 | Vérifier établissement, lien, permissions et module avec le responsable ; ne pas changer d'identifiant au hasard. |
| Validation / 400 | Lire les champs signalés, corriger la saisie ; ne pas inventer de note/référence pour satisfaire la règle. |
| Conflit / 409 ou version périmée | Recharger l'état, comparer les changements ; ne pas écraser le travail d'autrui. |
| Erreur serveur, réseau, paiement inconnu | Arrêter les répétitions ; transmettre l'heure et la référence au support. |
| Données d'autrui visibles, perte de données, résultat erroné | Cesser le parcours, ne pas télécharger davantage, alerter immédiatement le responsable. |
| Action impossible au clavier/mobile | Signaler écran, largeur, navigateur et étape ; une capture seule ne qualifie pas l'accessibilité. |

Transmettre **variante, écran, heure/fuseau, référence non sensible,
étapes et erreur expurgée**, éventuellement l'identifiant de requête.
Ne pas joindre mot de passe, QR MFA, token, `.env`, sauvegarde, dossier médical,
pièce d'identité ou bulletin à une issue publique. Les contacts et engagements
de réponse doivent être fournis par l'établissement : aucun support permanent
ou délai de reprise n'est garanti par ce dépôt.

Le web responsive n'est pas une application native Android/iOS. Une page
d'indisponibilité hors réseau ne permet pas de travailler/synchroniser des
données pédagogiques hors ligne. Accessibilité complète, hors ligne et
acceptation mobile restent à qualifier sur les parcours réellement ouverts.
