# Facturation et contrôle des paiements — deux SIS

Ce contrat concerne `sis_superieur/apps/paiements`,
`sis_secondaire/apps/paiements` et `sis_common/payment_review.py`.
Il ne qualifie aucun prestataire, pays ni traitement fiscal.

## Parcours utilisable

Dans `/superieur/paiements`, la comptabilité peut émettre une facture pour
un identifiant de dossier et de tarif existants de son établissement, avec
montant, échéance et **devise explicite**. Les identifiants sont ceux des
écrans dossiers/tarifs, pas des comptes utilisateurs. Les listes sont paginées.
La page utilise exclusivement l'API réelle : le mode simulé est refusé.
Le composant accepte aussi `apiType="secondaire"` ; son raccordement à une
route secondaire reste à la charge de l'intégration centrale (aucune
navigation partagée modifiée dans ce lot).

1. Déclarer un paiement : date, montant, mode, référence de rapprochement
   et justificatif privé PDF/PNG/JPEG. La carte nécessite une référence
   PaymentIntent existante ; cette interface ne crée ni débit ni checkout.
2. L'enregistrement reste `en_attente`, sans reçu ni crédit de facture.
   Un agent habilité **distinct du déclarant** télécharge la preuve puis
   valide ou rejette avec motif. Espèces/chèque/virement sont des constats
   humains documentés, pas une interrogation automatique de la banque.
3. La carte est rapprochée par lecture serveur Stripe. Une indisponibilité
   rend 503, une incohérence 409 ; aucun succès navigateur n'est accepté.
   `mobile_money`, `sepa` et `autre` restent non configurés.
4. Le solde est recalculé depuis les seuls paiements `valide`. Un reçu JSON
   consultable/imprimable, **non fiscal**, n'est disponible qu'après
   confirmation. Un remboursement est explicitement indiqué sur ce reçu.
5. Pour un remboursement intégral déjà exécuté hors SIS, un gestionnaire
   soumet motif, référence et justificatif ; un **autre gestionnaire**
   contrôle puis confirme. Pour la carte, le serveur vérifie en plus que
   Stripe a effectivement remboursé la totalité. Le SIS ne déclenche jamais
   ce remboursement. Le total est recalculé, pas simplement décrémenté.
6. La mutation, son audit et les notifications internes sont atomiques.
   Rejouer une confirmation callback ou un remboursement déjà comptabilisé
   ne crée ni crédit, ni audit, ni notification supplémentaires.

Un refus est conservé sur le paiement et son historique. Un événement
prestataire `payment_failed` marque `echec`, sans crédit ; une confirmation
ultérieure vérifiée peut reprendre ce même paiement. Une déclaration rejetée
doit être corrigée par une nouvelle déclaration et une nouvelle preuve.
Après coupure réseau, recharger avant toute nouvelle soumission : la création
de déclaration n'est pas une API idempotente et ne déclenche aucun débit.

## API (`/api/v1/paiements/`)

- `factures/` : GET/POST ; `factures/{id}/` : GET/PATCH, jamais DELETE.
  Après une première déclaration, apprenant/tarif/montant/devise/dates sont
  figés. `annuler/` refuse toute facture avec paiement confirmé.
- Solde : `factures/{id}/solde/` (supérieur),
  `factures/{id}/solde-confirme/` (secondaire).
- Listes, statistiques et bilans acceptent `?devise=EUR` (exemple de filtre,
  pas une devise par défaut). Les agrégations multidevises/non qualifiées
  sont refusées ; les factures annulées sont exclues des impayés agrégés.
- `transactions/` : GET/POST ; `transactions/{id}/` : GET seulement.
- `transactions/{id}/valider/`, `rejeter/` (`motif`) : POST.
- `transactions/{id}/demander-remboursement/` : POST multipart
  (`motif`, `reference`, `preuve`) ; `rembourser/` : POST du contrôleur.
- `transactions/{id}/recu/`, `justificatif/`,
  `justificatif-remboursement/`, `historique/` : GET, sous les mêmes
  restrictions tenant/propriétaire que le paiement.
- `transactions/prestataires/` : GET, état explicite sans secret.
- `transactions/callback-stripe/` : POST public authentifié par signature
  Stripe HMAC-SHA256 sur les **octets bruts**, horodatage ±300 s.
  Types acceptés : `payment_intent.succeeded`, `payment_intent.payment_failed`.
  Le succès est revérifié auprès du prestataire ; signature seule insuffisante.

Les métadonnées Stripe doivent contenir `sis_variant`, `sis_tenant_id`,
`sis_tenant_schema`, `sis_invoice`. Montant, devise, facture, tenant, statut,
mode carte, capture, absence de litige et état de remboursement sont vérifiés.
La référence `(mode, reference_externe)` ne peut être comptabilisée deux fois,
y compris sur deux factures. Le callback refuse les références ambiguës.
Les clés `SIS_STRIPE_SECRET_KEY` et `SIS_STRIPE_WEBHOOK_SECRET` sont lues côté
serveur seulement ; **ne jamais les mettre dans les factures, le frontend,
les exemples ou le dépôt**. Les intentions de test Stripe (`livemode=false`)
ne sont pas comptabilisées comme argent réel. Aucun secret n'est configuré
par cette livraison et aucun appel réel ne fait partie des tests.

## Notifications

Les destinataires financiers sont l'apprenant et l'acteur authentifié,
selon le mécanisme existant ; aucun parent non lié n'est ajouté.
La notification interne de mutation est persistée dans la transaction.
L'envoi externe n'est pas automatiquement branché sur ces événements.

Le dispatcher email existant refuse les backends console/locmem/fichier et
le SMTP par défaut localhost : état `not_configured`, sans faux « envoyé ».
Un SMTP réel explicitement configuré, un expéditeur, un destinataire actif
du tenant et son consentement sont nécessaires. La réservation persistée
`sending` empêche deux workers de renvoyer le même message ; `sent` n'est
jamais renvoyé. Un accusé négatif certain (0 envoi accepté) autorise les
reprises existantes. Une exception réseau ou un worker interrompu laisse
`uncertain` : **pas de reprise aveugle**, rapprochement avec le prestataire
obligatoire. SMTP n'offre pas l'exactly-once transactionnel.

SMS/push/webhooks commerciaux, routage automatique finance vers l'email,
administration du rapprochement des envois incertains et qualification réelle
des fournisseurs restent externes/ouvertes. Le centre existant affiche les
états et motifs ; ce lot ne promet aucun envoi à une destination réelle.

## Migrations et validation

- Supérieur : `paiements.0005_payment_review_currency`.
- Secondaire : `paiements.0006_payment_review_currency`.
- La devise historique reste vide : **aucune conversion ou supposition EUR**.
  Les anciennes factures sans devise n'acceptent pas de nouveaux paiements.
  La qualification des archives déjà mouvementées nécessite une reprise
  contrôlée hors de cette API, qui interdit de réinterpréter un encaissement.
- L'index unique ajouté refuse les doublons historiques déjà confirmés.
  Les rapprocher avant migration ; aucun effacement automatique n'est prévu.

À exécuter uniquement sur le runner de recette isolé :

```text
manage.py makemigrations --check --dry-run
manage.py test apps.paiements.tests.test_api sis_common.tests.test_payment_review sis_common.tests.test_notification_channels
npm test -- --runInBand src/superieur/paiements
```

Le superviseur central exécute les tests Django/Jest et migrations sur chaque
variante. Les seuls contrôles locaux de ce lot sont Ruff ciblé et analyse
syntaxique Babel ; ne pas les confondre avec une recette navigateur ou une
validation prestataire.

N3.1 (comptes/journaux/clôtures), aides/avoirs récurrents, rapprochement bancaire
automatique, fiscalité, remboursements partiels et N4.1 admission→LMS ne sont
pas clôturés par ce parcours. Les contrôles d'accès aux cours doivent rester
indépendants tant que leur condition financière n'est pas raccordée/validée.
