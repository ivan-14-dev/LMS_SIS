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
`sis_variant=secondaire`, `sis_tenant_id=<PK de l'établissement>`,
`sis_tenant_schema=<schema_name>` et `sis_invoice=<numéro de facture>`.
Ne pas accepter de métadonnées arbitraires du payeur. Seuls les paiements
Stripe en mode réel (`livemode`) sont créditables. Ce module ne crée pas de
PaymentIntent et n'effectue pas de remboursement auprès de Stripe. L'action
`rembourser` refuse les cartes : sans preuve d'un remboursement Stripe achevé,
décréditer la facture libérerait son solde alors que les fonds restent encaissés.
Les remboursements réels de carte requièrent un circuit de remboursement et de
rapprochement Stripe qualifié avant toute écriture comptable SIS ; les autres
modes conservent leur circuit manuel.

Avant la migration `0004_card_reference_unique` dans chaque schéma tenant,
rechercher et rapprocher manuellement les références de carte déjà validées
ou remboursées en double :
la création de l'index unique échoue volontairement si des doublons existent.
Exécuter cette requête **en lecture seule dans chaque schéma tenant** (pour le
secondaire), puis rapprocher les références signalées sans modification
automatique :

```sql
SELECT current_schema(), reference_externe, COUNT(*) AS occurrences,
       ARRAY_AGG(numero ORDER BY numero) AS paiements
FROM paiements_paiement
WHERE mode = 'carte' AND statut IN ('valide', 'rembourse')
  AND reference_externe <> ''
GROUP BY reference_externe
HAVING COUNT(*) > 1;
```
