"""Serializers for paiements (SIS Secondaire)."""

from rest_framework import serializers

from .models import Facture, Paiement, TypeFrais


class TypeFraisSerializer(serializers.ModelSerializer):
    """Serializer pour les types de frais."""

    periodicite_display = serializers.CharField(source="get_periodicite_display", read_only=True)
    nb_factures = serializers.SerializerMethodField()

    class Meta:
        model = TypeFrais
        fields = [
            "id",
            "annee_scolaire",
            "code",
            "libelle",
            "montant",
            "periodicite",
            "periodicite_display",
            "obligatoire",
            "classes",
            "date_limite",
            "actif",
            "nb_factures",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nb_factures(self, obj):
        return obj.factures.count()


class FactureListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de factures."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    type_frais_libelle = serializers.CharField(source="type_frais.libelle", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    montant_restant = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Facture
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "type_frais",
            "type_frais_libelle",
            "numero",
            "date_emission",
            "date_echeance",
            "montant",
            "montant_paye",
            "montant_restant",
            "statut",
            "statut_display",
        ]


class FactureDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une facture."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    type_frais_libelle = serializers.CharField(source="type_frais.libelle", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    montant_restant = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    paiements = serializers.SerializerMethodField()

    class Meta:
        model = Facture
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "type_frais",
            "type_frais_libelle",
            "numero",
            "date_emission",
            "date_echeance",
            "montant",
            "montant_paye",
            "montant_restant",
            "statut",
            "statut_display",
            "note",
            "pdf_path",
            "paiements",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "numero",
            "montant_paye",
            "statut",
            "pdf_path",
            "created_at",
            "updated_at",
        ]

    def get_paiements(self, obj):
        return PaiementSerializer(obj.paiements.all(), many=True).data


class PaiementSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements."""

    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    enregistre_par_nom = serializers.CharField(source="enregistre_par.get_full_name", read_only=True)
    preuve_disponible = serializers.SerializerMethodField()

    class Meta:
        model = Paiement
        fields = [
            "id",
            "facture",
            "numero",
            "date_paiement",
            "montant",
            "mode",
            "mode_display",
            "reference_externe",
            "statut",
            "statut_display",
            "recu_pdf",
            "preuve_disponible",
            "enregistre_par",
            "enregistre_par_nom",
            "verifie_par",
            "verifie_le",
            "motif_rejet",
            "created_at",
        ]
        read_only_fields = fields

    def get_preuve_disponible(self, obj):
        return bool(obj.preuve_paiement)


class PaiementCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un paiement."""

    class Meta:
        model = Paiement
        fields = [
            "facture",
            "date_paiement",
            "montant",
            "mode",
            "reference_externe",
            "preuve_paiement",
        ]
        extra_kwargs = {"preuve_paiement": {"write_only": True}}

    def validate(self, data):
        facture = data["facture"]
        request = self.context.get("request")
        user = getattr(request, "user", None)
        manager_roles = {
            "direction",
            "responsable_pedagogique",
            "comptable",
            "personnel_administratif",
        }
        is_manager = user and (
            user.is_staff or user.has_perm("paiements.add_paiement") or getattr(user, "role", "") in manager_roles
        )
        owns_invoice = user and (
            facture.eleve.user_id == user.id
            or facture.eleve.tuteurs_lies.filter(tuteur__user=user, autorise_acces_portail=True).exists()
        )
        if not is_manager and not owns_invoice:
            raise serializers.ValidationError({"facture": "Vous ne pouvez pas payer cette facture."})
        if facture.statut in ("payee", "annulee"):
            raise serializers.ValidationError({"facture": "Cette facture n'accepte plus de paiement."})
        if data["montant"] <= 0:
            raise serializers.ValidationError({"montant": "Le montant doit être positif."})
        if data["montant"] > facture.montant_restant:
            raise serializers.ValidationError({"montant": "Le montant dépasse le solde de la facture."})
        return data
