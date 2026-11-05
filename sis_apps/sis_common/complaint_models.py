"""Shared private complaint records, instantiated in each tenant's core app."""

import uuid

from django.conf import settings
from django.db import models

from sis_common.exam_files import PrivateExamStorage, validate_exam_copy


def complaint_attachment_path(instance, filename):
    return f"reclamations/{instance.reclamation.etablissement_id}/{instance.reclamation_id}/{uuid.uuid4().hex}.pdf"


class ComplaintBase(models.Model):
    CATEGORIES = [
        ("resultat", "Note ou résultat"),
        ("inscription", "Inscription"),
        ("frais", "Frais et paiement"),
        ("autre", "Autre demande"),
    ]
    STATUSES = [
        ("soumise", "Soumise"),
        ("en_cours", "En cours"),
        ("complement", "Complément demandé"),
        ("resolue", "Réponse apportée"),
        ("cloturee", "Clôturée"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reclamations")
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reclamations_assignees"
    )
    categorie = models.CharField(max_length=20, choices=CATEGORIES)
    objet = models.CharField(max_length=200)
    description = models.TextField()
    reference_dossier = models.CharField(max_length=200, blank=True)
    statut = models.CharField(max_length=20, choices=STATUSES, default="soumise")
    decision = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-updated_at", "id"]
        permissions = [
            ("affecter_reclamation", "Recevoir et affecter les réclamations de l'établissement"),
            ("traiter_reclamation", "Traiter les réclamations explicitement affectées"),
        ]

    @property
    def reference(self):
        return f"REC-{self.pk.hex.upper()}"

    def __str__(self):
        return self.reference


class ComplaintEntryBase(models.Model):
    reclamation = models.ForeignKey("core.Reclamation", on_delete=models.CASCADE, related_name="historique")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=30)
    message = models.TextField()
    statut = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["created_at", "id"]


class ComplaintAttachmentBase(models.Model):
    reclamation = models.ForeignKey("core.Reclamation", on_delete=models.CASCADE, related_name="pieces")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fichier = models.FileField(
        storage=PrivateExamStorage(), upload_to=complaint_attachment_path, validators=[validate_exam_copy]
    )
    nom = models.CharField(max_length=255)
    taille = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["created_at", "id"]
