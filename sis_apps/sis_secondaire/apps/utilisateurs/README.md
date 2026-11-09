# Comptes et affiliations famille

## Administration déléguée

Les deux variantes exigent désormais `utilisateurs.view_utilisateur` pour
consulter les autres comptes et les permissions `add`, `change`, `delete`
correspondantes pour administrer les comptes. Un nom de rôle, `is_staff` ou un
groupe de configuration sans permission ne les accorde pas. Les groupes Django
existants restent le mécanisme de délégation ; leur désactivation retire leurs
droits. Les contraintes ABAC ne deviennent pas des délégations globales.

Le compte personnel, les sessions, le mot de passe et le MFA gardent leurs
actions de libre-service. La modification du rôle hérité demeure réservée au
super-utilisateur selon le contrôle existant ; aucun nouveau rôle métier ni
permission de module n'est créé par cette livraison.

## Secondaire : parents et enfants

Dans **Administration → Utilisateurs → Parents et enfants** :

1. Utiliser un compte actif de rôle `parent` créé par l'autorité déjà habilitée.
2. Créer son profil parent (compte, identité, lien de parenté, coordonnées).
3. Sélectionner ce profil et un élève du même établissement.
4. Cocher explicitement **Autoriser l'accès au portail**, puis créer la liaison.
5. **Révoquer l'accès** conserve la relation avec accès désactivé.
   **Retirer la liaison**, après confirmation, supprime la relation.

| API relative à `/api/v1/` | Droits explicites |
|---|---|
| `utilisateurs/parents/` et `{id}/` | `eleves.view/add/change/delete_tuteur` selon l'opération |
| `utilisateurs/liens-parent/` et `{id}/` | `eleves.view/add/change/delete_elevetuteur` selon l'opération |
| `{id}/historique/` sur ces deux ressources | droit de lecture de la ressource et `core.view_workflowevent` |

La création d'une liaison reçoit `eleve`, `tuteur`,
`autorise_acces_portail` (obligatoire). Un PATCH change seulement l'autorisation ;
les deux extrémités ne se transfèrent pas silencieusement. Le compte d'un profil
parent ne se transfère pas non plus. Le retrait des liens précède la suppression
d'un profil. Les doublons et références étrangères/inactives sont rejetés.

Chaque mutation et son audit sont atomiques. L'historique conserve acteur,
tenant, avant/après et identifiants ; pas de mot de passe, token ni donnée médicale.
Après suppression, les événements restent dans l'historique de workflow autorisé.
Les scopes de liaison supportent `eleves`, `classes`, `tuteurs` ; les profils
supportent `tuteurs`, `comptes`. Un scope inconnu ou vide n'élargit jamais l'accès.

## Portail famille

Le parent choisit un enfant autorisé dans **Mon espace famille**. Le nouveau
GET `portail/apprenant/dossier_enfant/?enfant_id=…` expose les lectures existantes :
50 notes récentes, 30 absences/retards récents, planning actif, factures/paiements
et bulletins publiés. Les factures et bulletins réutilisent leurs querysets métier
autorisés ; les bulletins restent téléchargés via l'API privée existante
`bulletins/{id}/pdf_officiel/`, jamais par un chemin de stockage.

Une liaison désactivée ou supprimée retourne 404 pour le dossier et le PDF dès
la requête suivante. L'interface masque les données pendant la revalidation et
après refus, puis retire le dossier sélectionné si l'enfant disparaît. Le
rechargement/focus réévalue les droits ; un PDF déjà téléchargé hors navigateur
ne peut pas être effacé à distance.

**Limites explicites :** pas de relation parent-étudiant définie au supérieur,
pas de devoirs/messages/rendez-vous ajoutés au dossier famille, pas de nouveau
cycle complet de rôles métier/versionnement/approbations ni de propagation LMS.
Les comptes existants reposant uniquement sur un nom de rôle administratif
doivent recevoir leurs permissions explicites par l'autorité habilitée.
Les tests navigateur/déploiement et la recette distante restent distincts.
