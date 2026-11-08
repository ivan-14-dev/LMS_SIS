"""Append-only research subledger; mutations are financial commands, not CRUD."""

import re
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import F, Q

from sis_common.exam_files import PrivateFinancialStorage, validate_payment_proof


def research_financial_upload_to(instance, filename):
    schema = getattr(connection, "schema_name", "")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", schema) or schema == "public":
        raise ValidationError("Un schéma établissement est requis.")
    return f"recherche-finance/{schema}/{uuid4().hex}/preuve{Path(filename).suffix.lower()}"


class ImmutableFinancialQuerySet(models.QuerySet):
    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False, **kwargs):
        if ignore_conflicts or update_conflicts:
            raise ValidationError("Les écritures financières ne peuvent pas être remplacées ou ignorées.")
        return super().bulk_create(objs, batch_size=batch_size, **kwargs)

    def update(self, **kwargs):
        raise ValidationError("Les écritures financières sont immuables.")

    def delete(self):
        raise ValidationError("Les écritures financières sont immuables.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Les écritures financières sont immuables.")


class ImmutableFinancialRecord(models.Model):
    objects = ImmutableFinancialQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Les écritures financières sont immuables.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Les écritures financières sont immuables.")


class ResearchFinanceOperation(ImmutableFinancialRecord):
    class Type(models.TextChoices):
        FINANCEMENT = "financement", "Encaissement confirmé"
        ENGAGEMENT = "engagement", "Engagement budgétaire"
        DEPENSE = "depense", "Paiement confirmé"
        ANNULATION = "annulation_engagement", "Annulation du solde engagé"
        CONTREPASSATION = "contrepassation", "Contrepassation"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    projet = models.ForeignKey(
        "recherche.ProjetRecherche", on_delete=models.PROTECT, related_name="operations_financieres"
    )
    sequence = models.PositiveBigIntegerField(editable=False)
    type = models.CharField(max_length=24, choices=Type.choices)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    date_operation = models.DateField()
    libelle = models.CharField(max_length=1000)
    engagement = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="utilisations"
    )
    contrepassation_de = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="contrepassation"
    )
    idempotency_key = models.UUIDField(unique=True)
    request_hash = models.CharField(max_length=64)
    justificatif = models.FileField(
        upload_to=research_financial_upload_to,
        storage=PrivateFinancialStorage(),
        validators=[validate_payment_proof],
        max_length=300,
    )
    justificatif_nom = models.CharField(max_length=255)
    justificatif_taille = models.PositiveBigIntegerField()
    justificatif_sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="research_finance_operations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ["projet_id", "sequence"]
        constraints = [
            models.CheckConstraint(condition=Q(sequence__gt=0), name="research_finance_seq_positive"),
            models.UniqueConstraint(fields=["projet", "sequence"], name="research_finance_project_seq"),
            models.CheckConstraint(condition=Q(montant__gt=0), name="research_finance_positive"),
            models.CheckConstraint(
                condition=(
                    Q(type__in=["financement", "engagement"], engagement__isnull=True, contrepassation_de__isnull=True)
                    | Q(
                        type__in=["depense", "annulation_engagement"],
                        engagement__isnull=False,
                        contrepassation_de__isnull=True,
                    )
                    | Q(type="contrepassation", engagement__isnull=True, contrepassation_de__isnull=False)
                ),
                name="research_finance_link_shape",
            ),
            models.CheckConstraint(condition=~Q(id=F("engagement_id")), name="research_finance_not_self_eng"),
            models.CheckConstraint(
                condition=~Q(id=F("contrepassation_de_id")), name="research_finance_not_self_rev"
            ),
            models.CheckConstraint(condition=~Q(reference=""), name="research_finance_reference"),
            models.CheckConstraint(condition=Q(justificatif_taille__gt=0), name="research_finance_proof_size"),
            models.UniqueConstraint(
                fields=["engagement"],
                condition=Q(type="annulation_engagement"),
                name="research_finance_cancel_once",
            ),
        ]
        indexes = [models.Index(fields=["projet", "created_at"], name="research_finance_project_idx")]

    def __str__(self):
        return f"{self.reference} ({self.type}, {self.montant} EUR)"


class ResearchAccountingLine(ImmutableFinancialRecord):
    class Account(models.TextChoices):
        BANQUE = "banque", "Banque"
        FINANCEMENT = "financement", "Financement"
        CHARGE = "charge", "Charge"

    operation = models.ForeignKey(ResearchFinanceOperation, on_delete=models.PROTECT, related_name="lignes")
    compte = models.CharField(max_length=16, choices=Account.choices)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        default_permissions = ()
        ordering = ["compte"]
        constraints = [
            models.UniqueConstraint(fields=["operation", "compte"], name="research_line_account_once"),
            models.CheckConstraint(
                condition=Q(compte__in=["banque", "financement", "charge"]), name="research_line_account"
            ),
            models.CheckConstraint(
                condition=Q(debit__gt=0, credit=0) | Q(credit__gt=0, debit=0),
                name="research_line_one_positive_side",
            ),
        ]

    def __str__(self):
        return f"{self.operation_id} / {self.compte} : {self.debit} / {self.credit}"
