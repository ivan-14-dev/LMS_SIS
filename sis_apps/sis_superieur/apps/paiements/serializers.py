"""Serializers for paiements (SIS Supérieur)."""

from rest_framework import serializers

from sis_common.authorization import has_business_permission_or_role

from .models import FactureFrais, PaiementFrais, TypeFraisInscription
from .services import CURRENCY_EXPONENTS, MANUAL_MODES, provider_status


class TypeFraisInscriptionSerializer(serializers.ModelSerializer):
    """Serializer pour les types de frais."""

    periodicite_display = serializers.CharField(source="get_periodicite_display", read_only=True)
    annee_libelle = serializers.CharField(source="annee_universitaire.libelle", read_only=True)

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

    etudiant_matricule = serializers.CharField(source="etudiant.matricule", read_only=True)
    etudiant_nom = serializers.CharField(source="etudiant.user.get_full_name", read_only=True)
    type_frais_libelle = serializers.CharField(source="type_frais.libelle", read_only=True)
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
            "devise",
            "montant_paye",
            "reste_a_payer",
            "statut",
            "statut_display",
        ]

    def get_reste_a_payer(self, obj):
        return obj.montant - obj.montant_paye


class FactureFraisDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une facture."""

    etudiant_matricule = serializers.CharField(source="etudiant.matricule", read_only=True)
    etudiant_nom = serializers.CharField(source="etudiant.user.get_full_name", read_only=True)
    type_frais_libelle = serializers.CharField(source="type_frais.libelle", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    reste_a_payer = serializers.SerializerMethodField()
    nb_paiements = serializers.SerializerMethodField()
    devise = serializers.ChoiceField(choices=list(CURRENCY_EXPONENTS))

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
            "devise",
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
        read_only_fields = [
            "id",
            "numero",
            "montant_paye",
            "statut",
            "pdf_path",
            "qr_paiement",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        request = self.context["request"]
        tenant_id = getattr(getattr(request, "tenant", None), "pk", None)
        student = data.get("etudiant", getattr(self.instance, "etudiant", None))
        fee = data.get("type_frais", getattr(self.instance, "type_frais", None))
        if (
            not tenant_id
            or request.user.etablissement_id != tenant_id
            or (student.universite_id != tenant_id or fee.annee_universitaire.universite_id != tenant_id)
        ):
            raise serializers.ValidationError("Facture hors établissement.")
        if self.instance and self.instance.paiements.exists():
            for name in ("etudiant", "type_frais", "montant", "devise", "date_emission", "date_echeance"):
                if name in data and data[name] != getattr(self.instance, name):
                    raise serializers.ValidationError("Facture liée à un paiement : données financières figées.")
        amount = data.get("montant", getattr(self.instance, "montant", 0))
        currency = data.get("devise", getattr(self.instance, "devise", ""))
        if amount <= 0 or currency not in CURRENCY_EXPONENTS:
            raise serializers.ValidationError("Montant positif et devise explicite obligatoires.")
        if CURRENCY_EXPONENTS[currency] == 0 and amount != amount.to_integral_value():
            raise serializers.ValidationError("Cette devise n'accepte pas de fraction.")
        start = data.get("date_emission", getattr(self.instance, "date_emission", None))
        end = data.get("date_echeance", getattr(self.instance, "date_echeance", None))
        if end < start:
            raise serializers.ValidationError("Échéance antérieure à l'émission.")
        return data

    def get_reste_a_payer(self, obj):
        return obj.montant - obj.montant_paye

    def get_nb_paiements(self, obj):
        return obj.paiements.filter(statut="valide").count()

    def validate_montant(self, value):
        if self.instance and self.instance.montant_paye > 0 and value != self.instance.montant:
            raise serializers.ValidationError("Le montant d'une facture avec paiement validé ne peut pas être modifié.")
        return value


class PaiementFraisSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements."""

    facture_numero = serializers.CharField(source="facture.numero", read_only=True)
    etudiant_nom = serializers.CharField(source="facture.etudiant.user.get_full_name", read_only=True)
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    enregistre_par_nom = serializers.CharField(source="enregistre_par.get_full_name", read_only=True)
    preuve_disponible = serializers.SerializerMethodField()
    devise = serializers.CharField(source="facture.devise", read_only=True)

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
            "devise",
            "remboursement",
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
        from .api import visible_invoices

        facture = data["facture"]
        montant = data["montant"]
        reste = facture.montant - facture.montant_paye
        request = self.context.get("request")
        if not visible_invoices(request).filter(pk=facture.pk).exists():
            raise serializers.ValidationError({"facture": "Facture hors périmètre."})
        if facture.devise not in CURRENCY_EXPONENTS:
            raise serializers.ValidationError({"facture": "Devise de la facture non configurée."})
        if CURRENCY_EXPONENTS[facture.devise] == 0 and montant != montant.to_integral_value():
            raise serializers.ValidationError({"montant": "Cette devise n'accepte pas de fraction."})
        mode = data["mode"]
        if mode not in MANUAL_MODES and (mode != "carte" or provider_status()["carte"] != "configure"):
            raise serializers.ValidationError({"mode": "Prestataire non configuré."})
        if not data.get("reference_externe", "").strip():
            raise serializers.ValidationError({"reference_externe": "Référence de rapprochement obligatoire."})
        if mode in MANUAL_MODES and not data.get("preuve_paiement"):
            raise serializers.ValidationError({"preuve_paiement": "Justificatif obligatoire pour le contrôle."})
        user = getattr(request, "user", None)
        manager_roles = {
            "president",
            "vice_president",
            "doyen",
            "scolarite",
            "comptable",
        }
        is_manager = user and has_business_permission_or_role(user, "paiements.add_paiementfrais", manager_roles)
        if not is_manager and (not user or facture.etudiant.user_id != user.id):
            raise serializers.ValidationError({"facture": "Vous ne pouvez pas payer cette facture."})
        if facture.statut not in ("emise", "partielle", "en_retard"):
            raise serializers.ValidationError({"facture": "Cette facture n'accepte plus de paiement."})
        if montant <= 0:
            raise serializers.ValidationError({"montant": "Le montant doit être positif."})
        if montant > reste:
            raise serializers.ValidationError(
                {"montant": f"Le montant ne peut pas dépasser le reste à payer ({reste} {facture.devise})"}
            )
        return data
