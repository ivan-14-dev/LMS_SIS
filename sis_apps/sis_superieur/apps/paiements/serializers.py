"""Serializers for paiements (SIS Supérieur)."""

from rest_framework import serializers

from .models import FactureFrais, PaiementFrais, TypeFraisInscription


class TypeFraisInscriptionSerializer(serializers.ModelSerializer):
    """Serializer pour les types de frais."""

    periodicite_display = serializers.CharField(
        source="get_periodicite_display", read_only=True
    )
    annee_libelle = serializers.CharField(
        source="annee_universitaire.libelle", read_only=True
    )

    class Meta:
        model = TypeFraisInscription
        fields = [
            "id",
            "annee_universitaire",
            "annee_libelle",
            "code",
            "libelle",
            "montant",
            "periodicite",
            "periodicite_display",
            "obligatoire",
            "formations",
            "date_limite",
            "actif",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class FactureFraisListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de factures."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    type_frais_libelle = serializers.CharField(
        source="type_frais.libelle", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    reste_a_payer = serializers.SerializerMethodField()

    class Meta:
        model = FactureFrais
        fields = [
            "id",
            "numero",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "type_frais",
            "type_frais_libelle",
            "date_emission",
            "date_echeance",
            "montant",
            "montant_paye",
            "reste_a_payer",
            "statut",
            "statut_display",
        ]

    def get_reste_a_payer(self, obj):
        return obj.montant - obj.montant_paye


class FactureFraisDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une facture."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    type_frais_libelle = serializers.CharField(
        source="type_frais.libelle", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    reste_a_payer = serializers.SerializerMethodField()
    nb_paiements = serializers.SerializerMethodField()

    class Meta:
        model = FactureFrais
        fields = [
            "id",
            "numero",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "type_frais",
            "type_frais_libelle",
            "date_emission",
            "date_echeance",
            "montant",
            "montant_paye",
            "reste_a_payer",
            "statut",
            "statut_display",
            "note",
            "pdf_path",
            "qr_paiement",
            "nb_paiements",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "numero", "montant_paye", "created_at", "updated_at"]

    def get_reste_a_payer(self, obj):
        return obj.montant - obj.montant_paye

    def get_nb_paiements(self, obj):
        return obj.paiements.filter(statut="valide").count()


class PaiementFraisSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements."""

    facture_numero = serializers.CharField(source="facture.numero", read_only=True)
    etudiant_nom = serializers.CharField(
        source="facture.etudiant.user.get_full_name", read_only=True
    )
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    enregistre_par_nom = serializers.CharField(
        source="enregistre_par.get_full_name", read_only=True
    )
    preuve_disponible = serializers.SerializerMethodField()

    class Meta:
        model = PaiementFrais
        fields = [
            "id",
            "numero",
            "facture",
            "facture_numero",
            "etudiant_nom",
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
        ]
        read_only_fields = fields

    def get_preuve_disponible(self, obj):
        return bool(obj.preuve_paiement)


class PaiementCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de paiement."""

    class Meta:
        model = PaiementFrais
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
        montant = data["montant"]
        reste = facture.montant - facture.montant_paye
        request = self.context.get("request")
        user = getattr(request, "user", None)
        manager_roles = {
            "president",
            "vice_president",
            "doyen",
            "scolarite",
            "comptable",
        }
        is_manager = user and (
            user.is_staff or getattr(user, "role", "") in manager_roles
        )
        if not is_manager and (not user or facture.etudiant.user_id != user.id):
            raise serializers.ValidationError(
                {"facture": "Vous ne pouvez pas payer cette facture."}
            )
        if facture.statut in ("payee", "annulee"):
            raise serializers.ValidationError(
                {"facture": "Cette facture n'accepte plus de paiement."}
            )
        if montant <= 0:
            raise serializers.ValidationError({"montant": "Le montant doit être positif."})
        if montant > reste:
            raise serializers.ValidationError(
                {
                    "montant": f"Le montant ne peut pas dépasser le reste à payer ({reste}€)"
                }
            )
        return data
