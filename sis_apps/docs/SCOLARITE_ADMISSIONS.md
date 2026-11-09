# Admissions et interruptions de scolarité

## Périmètre

Ce circuit réutilise les dossiers apprenants, inscriptions annuelles, règles
historisées et notifications existants des deux SIS. Il ne crée ni règlement
national, ni campagne publique de candidature, ni preuve de paiement.

Le compte et le profil d'élève/étudiant doivent avoir été créés dans
l'établissement. Dans **Mon espace élève / étudiant → Admissions et
inscriptions**, un apprenant sans inscription peut déposer sa première demande :
année, classe ou formation, parcours facultatif dans le supérieur et message.
L'identité provient du compte connecté, jamais d'un identifiant envoyé par le
formulaire. Un refus réseau/API reste affiché ; il n'est pas présenté comme un
dépôt réussi. Après dépôt, le même panneau affiche les inscriptions, décisions
et motifs notifiés. Il ne propose pas de décision à l'apprenant.

La scolarité retrouve les demandes dans **Classes → Inscriptions annuelles**
(secondaire) ou **Inscriptions administratives** (supérieur). La validation
reste obligatoire avant affectation. Une demande n'est pas une réservation de
place ; la capacité de classe est vérifiée à la validation.

## Transitions opérées par la scolarité

| Action | État d'origine | Effet |
|---|---|---|
| Valider | En cours / Provisoire | Inscription validée ; affectation uniquement si l'année est en cours. |
| Refuser / annuler | En cours / Provisoire | Décision motivée conservée sur le dossier. |
| Suspendre | Validée | Inscription suspendue ; statut apprenant suspendu ; classe actuelle retirée dans le secondaire. |
| Enregistrer un abandon | Validée / Suspendue | Inscription abandonnée et statut apprenant abandon ; pas de reprise de cette même inscription. |
| Reprendre | Suspendue | Inscription validée ; statut inscrit/redoublant antérieur restauré ; capacité de classe contrôlée à nouveau. |
| Réinscrire / changer de cursus | Validée / Suspendue / Abandonnée | Nouveau dossier à examiner sur une année strictement postérieure, sans chevauchement. |

Chaque interruption/reprise exige un motif non vide, est atomique avec son
événement et sa notification interne, et conserve l'inscription d'origine.
Le rejeu d'une transition déjà effectuée est refusé avec HTTP 400 : ni nouvel
événement, ni seconde affectation. Le compte apprenant, même marqué personnel,
ne peut pas prendre ces décisions. Les droits et périmètres existants de
scolarité s'appliquent.

**La suspension libère la place au secondaire.** La reprise n'est donc pas
garantie si la classe a été remplie entre-temps. En cas de refus de capacité,
le dossier reste suspendu sans affectation partielle.

La suspension, l'abandon et la reprise concernent uniquement une année en cours
non clôturée. Une année terminée ne peut plus recevoir une admission ou une
validation, même si sa clôture administrative a été oubliée. La validation
anticipée d'une année future ne remplace ni la classe, ni le statut courant.
Après fin/clôture d'année, une réinscription est possible depuis le parcours
historique : l'ancien dossier, ses notes, ses choix pédagogiques et ses règles
ne sont pas réécrits.

Les notes et choix pédagogiques déjà enregistrés restent conservés pendant
l'interruption. Les listes de saisie de notes excluent les inscriptions
suspendues/abandonnées ; une reprise ne rouvre pas une période de notes close.
Les transferts existants restent motivés et refusés lorsqu'ils nécessiteraient
de convertir des règles, notes ou acquis sans traitement d'équivalence.

## Contrats API

Racine secondaire : `/api/v1/eleves/inscriptions/`.
Racine supérieur : `/api/v1/inscriptions/`.

- `GET catalogue/` : choix minimaux de première admission (`years`, `targets`,
  `paths`), réservés au compte apprenant actif avec profil dans le tenant et
  sans inscription existante. Les années closes/terminées et les formations
  inactives sont exclues. Seuls identifiants, libellés et rattachements utiles
  sont exposés, sans dossiers, effectifs ni personnel. Les listes scolaires
  ordinaires restent limitées aux classes/formations déjà attribuées.
- `POST deposer/` : première demande du compte apprenant. Corps :
  `annee_scolaire`, `classe`, `motif` facultatif au secondaire ;
  `annee_universitaire`, `formation`, `parcours` facultatif, `motif` facultatif
  au supérieur. Réponse 201 ; une nouvelle première demande est refusée dès
  qu'un dossier existe.
- `POST {id}/suspendre/`, `abandonner/`, `reprendre/` :
  `{"motif": "Justification de la décision"}` uniquement. Réponse 200 avec
  l'inscription actualisée. Champ supplémentaire, état incompatible, date,
  clôture ou capacité invalide : 400.
- `POST {id}/reinscrire/` : année/affectation de destination,
  `date_inscription`, `motif` obligatoire ; `parcours` et `regime` facultatifs
  au supérieur. Sans régime explicite, le régime d'origine est conservé.
  Réponse 201, identité apprenante conservée. Le dossier ultérieur existant
  bloque une seconde réinscription concurrente ou répétée.
- `GET {id}/historique/` : événements du dossier accessible uniquement dans
  le périmètre autorisé. L'interface rafraîchit cet historique après action.
- La modification directe du statut et la suppression d'une inscription
  sont refusées. Un dossier décidé n'est plus éditable par le formulaire
  ordinaire ; transferts et transitions doivent utiliser leurs actions.

Les modèles ajoutent les états `suspendue`, `abandonnee` et un champ technique
non éditable conservant le statut d'apprenant avant interruption.
Migrations : `eleves.0007_enrollment_interruptions` et
`etudiants.0006_enrollment_interruptions`. Elles n'altèrent aucune note ni
configuration historique.

## Recette et limites

Recette minimale : profil neuf → dépôt → validation → suspension motivée →
refus de nouveau dépôt et de saisie de note → reprise → saisie autorisée.
Vérifier ensuite capacité atteinte, année close/terminée, refus de transition
par l'apprenant ou dans un autre tenant, répétition sans doublon et abandon
puis réinscription. Les décisions figurent dans l'historique et les
notifications internes.

Tests backend ciblés, à lancer dans les environnements isolés de chaque SIS :

```text
sis_common.tests.test_admissions
sis_common.tests.test_academic_lifecycle.AcademicLifecycleTests
apps.etudiants.tests.test_api  # supérieur uniquement
```

Tests frontend : `AdmissionRequestPanel.test.jsx` et
`ResourceManager.test.jsx` (actions motivées sur les deux variantes).
Machine à états sans Django :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sis_apps python3 -m unittest sis_common.tests.test_enrollment_states
```

Restent hors de ce circuit : candidat public sans profil préalable,
campagnes/formulaires configurables, dépôt/quarantaine de pièces, concours,
compléments, contrôle financier préalable, prérequis automatiques,
équivalences et transferts inter-établissements. La capacité de formation
supérieure n'a pas de modèle existant : aucun plafond implicite n'est inventé.
Les migrations et tests d'intégration doivent être validés avant déploiement ;
ce document ne constitue pas une preuve d'exécution ou de mise à jour de la
démonstration.
