"""Explicitly nominative, tenant-local institutional surveys."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class InstitutionalSurveyBase(models.Model):
    STATUSES = [("brouillon", "Brouillon"), ("publiee", "Publiée"), ("fermee", "Fermée")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    politique = models.CharField(max_length=12, default="nominative", choices=[("nominative", "Nominative")])
    questionnaire = models.JSONField()
    statut = models.CharField(max_length=10, choices=STATUSES, default="brouillon")
    version = models.PositiveIntegerField(default=1)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at", "id"]
        default_permissions = ()
        permissions = [
            ("gerer_enquete_institutionnelle", "Gérer les enquêtes institutionnelles nominatives et leurs résultats")
        ]
        constraints = [
            models.CheckConstraint(condition=Q(politique="nominative"), name="survey_nominative"),
            models.CheckConstraint(condition=Q(statut__in=["brouillon", "publiee", "fermee"]), name="survey_status"),
        ]

    def __str__(self):
        return f"ENQ-{self.pk}"


class SurveyRecipientBase(models.Model):
    enquete = models.ForeignKey("core.InstitutionalSurvey", on_delete=models.PROTECT, related_name="destinataires")
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["id"]
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["enquete", "utilisateur"], name="survey_unique_recipient")]


class SurveyResponseBase(models.Model):
    destinataire = models.OneToOneField("core.SurveyRecipient", on_delete=models.PROTECT, related_name="reponse")
    reponses = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["created_at", "id"]
        default_permissions = ()
