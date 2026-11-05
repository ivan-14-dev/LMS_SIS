# Validation des paiements par carte

`POST /api/v1/paiements/transactions/{id}/valider/` consulte **Stripe** avant de
créditer une facture pour le mode `carte`. Renseigner `SIS_STRIPE_SECRET_KEY`
avec une clé secrète Stripe côté serveur, jamais dans le client ou dans le
dépôt. Sans clé ou en cas d'indisponibilité Stripe, la validation échoue sans
modifier la facture. Les espèces, chèques et autres modes conservent le circuit
de validation manuel existant.

La référence externe doit être l'identifiant `pi_…` d'un PaymentIntent créé
côté serveur sur ce compte Stripe. Son paiement confirmé doit être en euros,
non remboursé, et correspondre exactement au montant du paiement SIS. À sa
création, l'intégration Stripe doit enregistrer des métadonnées **côté serveur** :
`sis_variant=superieur`, `sis_tenant_id=<PK de l'établissement>`,
`sis_tenant_schema=<schema_name>` et `sis_invoice=<numéro de facture>`.
Ne pas accepter de métadonnées arbitraires du payeur. Seuls les paiements
Stripe en mode réel (`livemode`) sont créditables. Ce module ne crée pas de
PaymentIntent et n'effectue pas de remboursement auprès de Stripe : l'action
`rembourser` reste comptable, à rapprocher séparément d'un remboursement réel.

Avant la migration `0004_card_reference_unique` dans chaque schéma tenant,
rechercher et rapprocher manuellement les références de carte déjà validées
ou remboursées en double :
la création de l'index unique échoue volontairement si des doublons existent.
