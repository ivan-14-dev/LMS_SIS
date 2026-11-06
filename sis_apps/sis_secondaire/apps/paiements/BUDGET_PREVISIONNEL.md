# Budget prévisionnel local (secondaire)

`/api/v1/paiements/budgets-previsionnels/` permet à la direction et à la
comptabilité (ou aux détenteurs des permissions
`paiements.view_budgetprevisionnel`, `paiements.add_budgetprevisionnel` et
`paiements.change_budgetprevisionnel`, selon l'opération) de consulter et
d'enregistrer un montant prévu positif pour un poste libre (`code`, `libelle`)
et une année scolaire de leur établissement. Le code est unique par année.
Le montant et le libellé sont modifiables par `PATCH /{id}/` avant clôture ;
`POST /{id}/cloturer/` clôture définitivement le poste. Une année scolaire
clôturée interdit toute création, modification et clôture de poste.

Les données sont stockées dans le schéma du tenant, et la sélection de l'année
ainsi que la lecture des postes vérifient explicitement l'établissement du
tenant. Aucun poste ne peut être supprimé ou réaffecté à une autre année.
Cette saisie **ne représente ni une dépense effective, ni un solde, ni un
contrôle de dépassement**, et ne modifie aucun paiement ou encaissement Stripe.
Elle ne constitue pas un livre comptable ni une implémentation complète de la
gestion budgétaire ou des obligations de comptabilité publique.
