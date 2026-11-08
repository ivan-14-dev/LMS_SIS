"""Institutional agenda; rooms and accounts remain in their existing catalogues."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class InstitutionalEventBase(models.Model):
    TYPES = [
        ("conference", "Conférence"),
        ("examen", "Examen"),
        ("reunion", "Réunion"),
        ("ceremonie", "Cérémonie"),
        ("activite", "Activité institutionnelle"),
    ]
    STATUSES = [("planifie", "Planifié"), ("annule", "Annulé")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=12, choices=TYPES)
    statut = models.CharField(max_length=10, choices=STATUSES, default="planifie")
    debut = models.DateTimeField()
    fin = models.DateTimeField()
    effectif = models.PositiveIntegerField()
    version = models.PositiveIntegerField(default=1)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["debut", "id"]
        default_permissions = ()
        permissions = [
            ("gerer_evenement_institutionnel", "Organiser les événements institutionnels"),
            ("consulter_evenement_institutionnel", "Consulter les événements auxquels on est invité"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(fin__gt=F("debut")), name="institutional_event_interval"),
            models.CheckConstraint(condition=Q(effectif__gt=0), name="institutional_event_attendance"),
            models.CheckConstraint(condition=Q(statut__in=["planifie", "annule"]), name="institutional_event_status"),
            models.CheckConstraint(
                condition=Q(type__in=["conference", "examen", "reunion", "ceremonie", "activite"]),
                name="institutional_event_type",
            ),
        ]
        indexes = [models.Index(fields=["salle", "debut", "fin"], name="institutional_event_room_dates")]

    def __str__(self):
        return f"EVT-{self.pk}"


class EventInvitationBase(models.Model):
    evenement = models.ForeignKey("core.InstitutionalEvent", on_delete=models.PROTECT, related_name="invitations")
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["id"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=["evenement", "utilisateur"], name="institutional_event_invitation")
        ]
