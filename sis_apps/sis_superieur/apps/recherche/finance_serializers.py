"""Strict financial command input and private, read-only representations."""

import re
from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from sis_common.exam_files import validate_payment_proof

from .finance_models import ResearchAccountingLine, ResearchFinanceOperation


class StrictText(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str) or any(ord(char) < 32 or ord(char) == 127 for char in data):
            self.fail("invalid")
        return super().to_internal_value(data)


class StrictVersion(serializers.IntegerField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (str, int)) or not re.fullmatch(r"[1-9][0-9]*", str(data)):
            self.fail("invalid")
        return super().to_internal_value(data)


class StrictUUID(serializers.UUIDField):
    def to_internal_value(self, data):
        if not isinstance(data, (str, UUID)):
            self.fail("invalid")
        return super().to_internal_value(data)


class ExactMoney(serializers.DecimalField):
    def to_internal_value(self, data):
        if not isinstance(data, (str, Decimal)) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?", str(data)):
            self.fail("invalid")
        return super().to_internal_value(data)


class StrictDate(serializers.DateField):
    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
            self.fail("invalid", format="YYYY-MM-DD")
        return super().to_internal_value(data)


class FinancialCommandSerializer(serializers.Serializer):
    version = StrictVersion(min_value=1, max_value=2147483647)
    idempotency_key = StrictUUID()
    type = serializers.ChoiceField(choices=ResearchFinanceOperation.Type.choices)
    montant = ExactMoney(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    reference = StrictText(max_length=100)
    date_operation = StrictDate()
    libelle = StrictText(max_length=1000)
    engagement = StrictUUID(required=False, allow_null=True, default=None)
    contrepassation_de = StrictUUID(required=False, allow_null=True, default=None)
    justificatif = serializers.FileField(max_length=255, allow_empty_file=False)

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": "Un objet de commande est requis."})
        if set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": "Champs inconnus dans la commande financière."})
        if hasattr(data, "getlist") and any(len(data.getlist(key)) != 1 for key in data):
            raise serializers.ValidationError({"non_field_errors": "Un champ ne peut pas être répété."})
        return super().to_internal_value(data)

    def validate_justificatif(self, value):
        if any(ord(char) < 32 or ord(char) == 127 for char in value.name):
            raise serializers.ValidationError("Nom de justificatif invalide.")
        try:
            validate_payment_proof(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    def validate(self, attrs):
        project = self.context["project"]
        if not project.date_debut <= attrs["date_operation"] <= timezone.localdate():
            raise serializers.ValidationError({"date_operation": "Date hors de la période autorisée."})
        kind = attrs["type"]
        needs_commitment = kind in ("depense", "annulation_engagement")
        needs_reversal = kind == "contrepassation"
        if bool(attrs["engagement"]) != needs_commitment:
            raise serializers.ValidationError({"engagement": "Lien d'engagement incompatible avec cette opération."})
        if bool(attrs["contrepassation_de"]) != needs_reversal:
            raise serializers.ValidationError({"contrepassation_de": "Lien de contrepassation incompatible."})
        return attrs


class AccountingLineSerializer(serializers.ModelSerializer):
    debit = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True, read_only=True)
    credit = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True, read_only=True)

    class Meta:
        model = ResearchAccountingLine
        fields = ["compte", "debit", "credit"]
        read_only_fields = fields


class FinancialOperationSerializer(serializers.ModelSerializer):
    montant = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True, read_only=True)
    url_justificatif = serializers.SerializerMethodField()
    lignes = AccountingLineSerializer(many=True, read_only=True)

    class Meta:
        model = ResearchFinanceOperation
        fields = [
            "id", "sequence", "type", "montant", "reference", "date_operation", "libelle", "engagement",
            "contrepassation_de", "created_at", "justificatif_nom", "justificatif_sha256",
            "url_justificatif", "lignes",
        ]
        read_only_fields = fields

    def get_url_justificatif(self, operation):
        return (
            f"/api/v1/recherche/projets-recherche/{operation.projet_id}/"
            f"justificatifs/{operation.pk}/"
        )
