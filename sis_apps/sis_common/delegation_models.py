"""Time-limited, read-only work assignments without changing the learner's role."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class AccessDelegationBase(models.Model):
    beneficiaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="missions_recues")
    accorde_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="missions_accordees"
    )
    ressource = models.CharField(max_length=30)
    dossiers_ids = models.JSONField(default=list)
    debut = models.DateTimeField()
    fin = models.DateTimeField()
    motif = models.TextField()
    revoque_le = models.DateTimeField(null=True, blank=True)
    revoque_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="missions_revoquees"
    )
    motif_revocation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at", "-pk"]
        permissions = [("manage_accessdelegation", "Accorder et révoquer des missions de consultation aux apprenants")]
        constraints = [
            models.CheckConstraint(condition=models.Q(fin__gt=models.F("debut")), name="mission_dates_ordered")
        ]

    @property
    def statut(self):
        if self.revoque_le:
            return "revoquee"
        now = timezone.now()
        if self.fin <= now:
            return "expiree"
        return "planifiee" if self.debut > now else "active"

    def __str__(self):
        return f"Mission {self.pk} — {self.ressource}"
