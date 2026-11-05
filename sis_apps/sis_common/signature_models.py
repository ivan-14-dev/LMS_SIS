"""Approval records and append-only document evidence shared by both variants."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SignatureApprovalBase(models.Model):
    STATUSES = [
        ("en_attente", "En attente"),
        ("validee", "Validée"),
        ("refusee", "Refusée"),
        ("suspendue", "Suspendue"),
        ("revoquee", "Révoquée"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulaire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="signatures_demandees"
    )
    fonction = models.CharField(max_length=150)
    types_documents = models.JSONField(default=list)
    debut = models.DateTimeField()
    fin = models.DateTimeField()
    statut = models.CharField(max_length=20, choices=STATUSES, default="en_attente")
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="signatures_validees"
    )
    valide_le = models.DateTimeField(null=True, blank=True)
    cle_publique = models.CharField(max_length=100, blank=True, editable=False)
    cle_privee_chiffree = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at", "id"]
        permissions = [
            ("request_signature", "Demander une signature institutionnelle"),
            ("approve_signature", "Valider les signatures d'autres responsables"),
            ("use_signature", "Apposer une signature institutionnelle autorisée"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(fin__gt=models.F("debut")), name="signature_dates_ordered"),
        ]

    @property
    def utilisable(self):
        return (
            self.statut == "validee"
            and self.debut <= timezone.now() < self.fin
            and self.titulaire.is_active
            and bool(self.cle_publique)
        )

    def __str__(self):
        return f"{self.fonction} — {self.titulaire.get_full_name() or self.titulaire.username}"


class SignatureMandateBase(models.Model):
    signature = models.ForeignKey("core.SignatureApproval", on_delete=models.PROTECT, related_name="mandats")
    operateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mandats_signature")
    debut = models.DateTimeField()
    fin = models.DateTimeField()
    motif = models.TextField()
    revoque_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fin__gt=models.F("debut")), name="signature_mandate_dates_ordered"
            ),
        ]

    @property
    def statut(self):
        if self.revoque_le:
            return "revoque"
        now = timezone.now()
        return "expire" if self.fin <= now else ("planifie" if self.debut > now else "actif")

    def __str__(self):
        return f"Mandat {self.pk}"


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Une archive ne peut pas être modifiée.")

    def delete(self):
        raise ValidationError("Une archive ne peut pas être supprimée.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Une archive ne peut pas être modifiée.")


class ImmutableRecord(models.Model):
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Une archive ne peut pas être modifiée.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Une archive ne peut pas être supprimée.")


class DocumentArchiveBase(ImmutableRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_type = models.CharField(max_length=80)
    source_id = models.PositiveBigIntegerField()
    beneficiaire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents_archives"
    )
    signature = models.ForeignKey("core.SignatureApproval", on_delete=models.PROTECT, related_name="usages")
    operateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents_signes")
    mandat = models.ForeignKey("core.SignatureMandate", on_delete=models.PROTECT, null=True, blank=True)
    version = models.PositiveIntegerField()
    idempotency_key = models.UUIDField()
    pdf = models.BinaryField(editable=False)
    sha256 = models.CharField(max_length=64, editable=False)
    manifeste = models.JSONField(editable=False)
    preuve = models.CharField(max_length=150, editable=False)
    cle_publique = models.CharField(max_length=100, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        abstract = True
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "version"], name="archive_source_version_unique"
            ),
            models.UniqueConstraint(fields=["operateur", "idempotency_key"], name="archive_request_unique"),
        ]

    def __str__(self):
        return f"Archive {self.pk} v{self.version}"


class ArchiveRevocationBase(ImmutableRecord):
    archive = models.OneToOneField("core.DocumentArchive", on_delete=models.PROTECT, related_name="revocation")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    motif = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        permissions = [("revoke_documentarchive", "Révoquer un document archivé sans supprimer sa preuve")]
