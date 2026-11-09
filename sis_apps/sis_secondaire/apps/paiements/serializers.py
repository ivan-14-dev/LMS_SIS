"""Serializers for paiements (SIS Secondaire)."""

from apps.etablissement.models import AnneeScolaire
from rest_framework import serializers

from sis_common.authorization import has_business_permission_or_role

from .models import BudgetPrevisionnel, Facture, Paiement, TypeFrais
from .services import CURRENCY_EXPONENTS, MANUAL_MODES, provider_status


class BudgetPrevisionnelSerializer(serializers.ModelSerializer):
    annee_scolaire = serializers.PrimaryKeyRelatedField(queryset=AnneeScolaire.objects.none())

    class Meta:
        model = BudgetPrevisionnel
        fields = [
            "id",
            "annee_scolaire",
            "code",
            "libelle",
            "montant_prevu",
            "statut",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "statut", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant and tenant.pk:
            self.fields["annee_scolaire"].queryset = AnneeScolaire.objects.filter(etablissement_id=tenant.pk)

    def validate_montant_prevu(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant prévu doit être positif.")
        return value

    def validate(self, attrs):
        if self.instance:
            if self.instance.statut == "cloture":
                raise serializers.ValidationError("Un budget clôturé ne peut plus être modifié.")
            if any(field in self.initial_data for field in ("annee_scolaire", "code", "statut")):
                raise serializers.ValidationError("L'année, le code et le statut ne sont pas modifiables.")
            annee = self.instance.annee_scolaire
        else:
            annee = attrs["annee_scolaire"]
        if annee.cloturee:
            raise serializers.ValidationError({"annee_scolaire": "L'année scolaire est clôturée."})
        return attrs


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
            "devise",
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
    devise = serializers.ChoiceField(choices=list(CURRENCY_EXPONENTS))

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
            "devise",
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

    def validate(self, data):
        request = self.context["request"]
        tenant_id = getattr(getattr(request, "tenant", None), "pk", None)
        student = data.get("eleve", getattr(self.instance, "eleve", None))
        fee = data.get("type_frais", getattr(self.instance, "type_frais", None))
        if (
            not tenant_id
            or request.user.etablissement_id != tenant_id
            or (student.etablissement_id != tenant_id or fee.annee_scolaire.etablissement_id != tenant_id)
        ):
            raise serializers.ValidationError("Facture hors établissement.")
        if self.instance and self.instance.paiements.exists():
            for name in ("eleve", "type_frais", "montant", "devise", "date_emission", "date_echeance"):
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


class PaiementSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements."""

    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    enregistre_par_nom = serializers.CharField(source="enregistre_par.get_full_name", read_only=True)
    preuve_disponible = serializers.SerializerMethodField()
    devise = serializers.CharField(source="facture.devise", read_only=True)

    class Meta:
        model = Paiement
        fields = [
            "id",
            "facture",
            "numero",
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
        from .api import visible_invoices

        facture = data["facture"]
        request = self.context.get("request")
        if not visible_invoices(request).filter(pk=facture.pk).exists():
            raise serializers.ValidationError({"facture": "Facture hors périmètre."})
        if facture.devise not in CURRENCY_EXPONENTS:
            raise serializers.ValidationError({"facture": "Devise de la facture non configurée."})
        if CURRENCY_EXPONENTS[facture.devise] == 0 and data["montant"] != data["montant"].to_integral_value():
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
            "direction",
            "responsable_pedagogique",
            "comptable",
            "personnel_administratif",
        }
        is_manager = user and has_business_permission_or_role(user, "paiements.add_paiement", manager_roles)
        owns_invoice = user and (
            facture.eleve.user_id == user.id
            or facture.eleve.tuteurs_lies.filter(tuteur__user=user, autorise_acces_portail=True).exists()
        )
        if not is_manager and not owns_invoice:
            raise serializers.ValidationError({"facture": "Vous ne pouvez pas payer cette facture."})
        tenant = getattr(request, "tenant", None)
        if (
            not getattr(tenant, "pk", None)
            or getattr(user, "etablissement_id", None) != tenant.pk
            or facture.eleve.etablissement_id != tenant.pk
            or facture.type_frais.annee_scolaire.etablissement_id != tenant.pk
        ):
            raise serializers.ValidationError({"facture": "Cette facture n'appartient pas à votre établissement."})
        if facture.statut not in ("emise", "partielle", "en_retard"):
            raise serializers.ValidationError({"facture": "Cette facture n'accepte plus de paiement."})
        if data["montant"] <= 0:
            raise serializers.ValidationError({"montant": "Le montant doit être positif."})
        if data["montant"] > facture.montant_restant:
            raise serializers.ValidationError({"montant": "Le montant dépasse le solde de la facture."})
        return data
