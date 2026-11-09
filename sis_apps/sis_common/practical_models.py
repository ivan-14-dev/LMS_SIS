"""Shared practical aggregates; evidence and decisions are append-only."""

import re
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import F, Q

from sis_common.exam_files import PrivateExamStorage, validate_exam_copy

_writing = ContextVar("practical_command", default=False)


@contextmanager
def practical_command():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


def evidence_path(instance, filename):
    schema = getattr(connection, "schema_name", "")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", schema) or schema == "public":
        raise ValidationError("Un schéma établissement est requis.")
    kind = "heures" if instance._meta.model_name == "heurepratique" else "evaluations"
    return (
        f"pratique/{schema}/{instance.dossier.etablissement_id}/{instance.dossier_id}/"
        f"{kind}/{uuid4().hex}.pdf"
    )


class PracticalQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Utilisez une commande pratique versionnée.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Les mises à jour pratiques en masse sont interdites.")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Les créations pratiques en masse sont interdites.")

    def delete(self):
        raise ValidationError("Les dossiers et preuves pratiques ne sont pas supprimables.")


class PracticalModel(models.Model):
    objects = PracticalQuerySet.as_manager()
    mutable_fields = frozenset()

    class Meta:
        abstract = True
        default_permissions = ()

    def __str__(self):
        return f"{self._meta.model_name}-{self.pk}"

    def save(self, *args, **kwargs):
        if self._state.adding:
            kwargs["force_insert"] = True
        else:
            previous = type(self).objects.get(pk=self.pk)
            changed = {
                field.attname for field in self._meta.concrete_fields
                if getattr(previous, field.attname) != getattr(self, field.attname)
            }
            if not _writing.get() or changed - self.allowed_changes(previous):
                raise ValidationError("Les faits pratiques sont immuables hors commande autorisée.")
        return super().save(*args, **kwargs)

    def allowed_changes(self, previous):
        return self.mutable_fields

    def delete(self, *args, **kwargs):
        raise ValidationError("Les dossiers et preuves pratiques ne sont pas supprimables.")

class ProgrammePratiqueBase(PracticalModel):
    code = models.CharField(max_length=64)
    version = models.PositiveIntegerField(default=1)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    mutable_fields = frozenset({"version", "updated_at"})

    class Meta(PracticalModel.Meta):
        abstract = True
        permissions = [
            ("gerer_suivi_pratique", "Gérer les programmes et dossiers pratiques"),
            ("consulter_suivi_pratique", "Consulter un dossier pratique attribué"),
            ("saisir_heures_pratiques", "Saisir les heures pratiques"),
            ("valider_heures_pratiques", "Valider les heures pratiques attribuées"),
            ("evaluer_competences_pratiques", "Évaluer les compétences pratiques attribuées"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["etablissement", "curriculum", "code"], name="practical_programme_code"),
            models.CheckConstraint(condition=Q(version__gte=1), name="practical_programme_version"),
        ]


class RevisionProgrammePratiqueBase(PracticalModel):
    programme = models.ForeignKey("stages.ProgrammePratique", on_delete=models.PROTECT, related_name="revisions")
    numero = models.PositiveIntegerField()
    statut = models.CharField(max_length=12, default="brouillon")
    titre = models.CharField(max_length=200)
    minutes_requises = models.PositiveIntegerField()
    competences = models.JSONField(default=list)
    snapshot = models.JSONField(default=dict)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    publie_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    published_at = models.DateTimeField(null=True)
    archive_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    archived_at = models.DateTimeField(null=True)

    class Meta(PracticalModel.Meta):
        abstract = True
        ordering = ["-numero"]
        constraints = [
            models.UniqueConstraint(fields=["programme", "numero"], name="practical_revision_number"),
            models.UniqueConstraint(
                fields=["programme"], condition=Q(statut="brouillon"), name="practical_one_draft"
            ),
            models.UniqueConstraint(fields=["programme"], condition=Q(statut="publie"), name="practical_one_published"),
            models.CheckConstraint(condition=Q(numero__gte=1), name="practical_revision_positive"),
            models.CheckConstraint(condition=Q(statut__in=["brouillon", "publie", "archive"]), name="practical_revision_state"),
        ]

    def allowed_changes(self, previous):
        if previous.statut == "archive":
            return frozenset()
        archive = {"statut", "archived_at", "archive_par_id"}
        if previous.statut == "publie":
            if self.statut != "archive":
                return frozenset()
            return archive
        return archive | {"titre", "minutes_requises", "competences", "snapshot", "published_at", "publie_par_id"}


class DossierPratiqueBase(PracticalModel):
    convention = models.OneToOneField("stages.ConventionStage", on_delete=models.PROTECT, related_name="dossier_pratique")
    programme_revision = models.ForeignKey("stages.RevisionProgrammePratique", on_delete=models.PROTECT, related_name="dossiers")
    apprenant_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    tuteur_interne_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    partenaire_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True)
    snapshot = models.JSONField(default=dict)
    programme_snapshot = models.JSONField(default=dict)
    identite = models.JSONField(default=dict)
    date_debut = models.DateField()
    date_fin = models.DateField()
    fuseau_horaire = models.CharField(max_length=64)
    statut = models.CharField(max_length=10, default="ouvert")
    version = models.PositiveIntegerField(default=1)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    clos_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True)
    closed_at = models.DateTimeField(null=True)
    annule_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True)
    cancelled_at = models.DateTimeField(null=True)
    motif_annulation = models.TextField(null=True)  # noqa: DJ001 -- null until administrative cancellation
    partenaire_revoque_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True)
    partenaire_revoque_le = models.DateTimeField(null=True)
    motif_revocation = models.TextField(null=True)  # noqa: DJ001 -- null until partner revocation

    class Meta(PracticalModel.Meta):
        abstract = True
        constraints = [
            models.CheckConstraint(condition=Q(date_fin__gte=F("date_debut")), name="practical_dossier_dates"),
            models.CheckConstraint(condition=~Q(apprenant_user=F("tuteur_interne_user")), name="practical_tutor_not_learner"),
            models.CheckConstraint(
                condition=Q(partenaire_user__isnull=True) | (
                    ~Q(partenaire_user=F("apprenant_user")) & ~Q(partenaire_user=F("tuteur_interne_user"))
                ), name="practical_partner_distinct",
            ),
            models.CheckConstraint(condition=Q(version__gte=1), name="practical_dossier_version"),
            models.CheckConstraint(condition=Q(statut__in=["ouvert", "clos", "annule"]), name="practical_dossier_state"),
            models.CheckConstraint(
                condition=(
                    Q(statut="ouvert", closed_at__isnull=True, clos_par__isnull=True,
                      cancelled_at__isnull=True, annule_par__isnull=True)
                    | Q(statut="clos", closed_at__isnull=False, clos_par__isnull=False,
                        cancelled_at__isnull=True, annule_par__isnull=True)
                    | Q(statut="annule", closed_at__isnull=True, clos_par__isnull=True,
                        cancelled_at__isnull=False, annule_par__isnull=False)
                ), name="practical_terminal_actor",
            ),
            models.CheckConstraint(
                condition=Q(partenaire_revoque_le__isnull=True, partenaire_revoque_par__isnull=True)
                | Q(partenaire_revoque_le__isnull=False, partenaire_revoque_par__isnull=False, partenaire_user__isnull=False),
                name="practical_revocation_actor",
            ),
        ]

    def allowed_changes(self, previous):
        acl = {"version"}
        if previous.partenaire_revoque_le is None and self.partenaire_user_id:
            acl |= {"partenaire_revoque_le", "partenaire_revoque_par_id", "motif_revocation"}
        if previous.statut != "ouvert":
            return acl if self.partenaire_revoque_le is not None else frozenset()
        return acl | {"statut", "closed_at", "clos_par_id", "cancelled_at", "annule_par_id", "motif_annulation"}


class PracticalEvidenceBase(PracticalModel):
    fichier = models.FileField(
        storage=PrivateExamStorage(), upload_to=evidence_path, validators=[validate_exam_copy],
        max_length=350, blank=True,
    )
    fichier_nom = models.CharField(max_length=200, blank=True)
    fichier_taille = models.PositiveIntegerField(default=0)
    fichier_sha256 = models.CharField(max_length=64, blank=True)
    version_creation = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(PracticalModel.Meta):
        abstract = True


class HeurePratiqueBase(PracticalEvidenceBase):
    dossier = models.ForeignKey("stages.DossierPratique", on_delete=models.PROTECT, related_name="heures")
    date = models.DateField()
    minute_debut = models.PositiveSmallIntegerField()
    minute_fin = models.PositiveSmallIntegerField()
    pause_minutes = models.PositiveSmallIntegerField()
    minutes = models.PositiveSmallIntegerField()
    activite = models.TextField()
    saisi_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    statut = models.CharField(max_length=12, default="brouillon")
    remplace = models.OneToOneField("self", on_delete=models.PROTECT, null=True, related_name="remplacement")
    mutable_fields = frozenset({"statut"})

    class Meta(PracticalEvidenceBase.Meta):
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=Q(minute_debut__gte=0, minute_fin__lte=1440, minute_fin__gt=F("minute_debut")),
                name="practical_hour_interval",
            ),
            models.CheckConstraint(
                condition=Q(pause_minutes__gte=0, pause_minutes__lt=F("minute_fin") - F("minute_debut")),
                name="practical_hour_break",
            ),
            models.CheckConstraint(
                condition=Q(minutes__gt=0, minutes=F("minute_fin") - F("minute_debut") - F("pause_minutes")),
                name="practical_hour_minutes",
            ),
            models.CheckConstraint(
                condition=Q(statut__in=["brouillon", "soumise", "validee", "rejetee", "annulee"]),
                name="practical_hour_state",
            ),
        ]
        indexes = [
            models.Index(fields=["apprenant", "date", "statut"], name="practical_learner_hours"),
            models.Index(fields=["dossier", "date"], name="practical_dossier_hours"),
        ]


class DecisionHeurePratiqueBase(PracticalModel):
    heure = models.ForeignKey("stages.HeurePratique", on_delete=models.PROTECT, related_name="decisions")
    sequence = models.PositiveIntegerField()
    action = models.CharField(max_length=24)
    etat_avant = models.CharField(max_length=12, null=True)  # noqa: DJ001 -- creation has no previous state
    etat_apres = models.CharField(max_length=12)
    motif = models.TextField(null=True)  # noqa: DJ001 -- only reason-bearing decisions have a reason
    acteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    acteur_nom = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    version_dossier = models.PositiveIntegerField()
    heure_remplacement = models.ForeignKey("stages.HeurePratique", on_delete=models.PROTECT, null=True, related_name="+")

    class Meta(PracticalModel.Meta):
        abstract = True
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(fields=["heure", "sequence"], name="practical_hour_decision_sequence"),
            models.CheckConstraint(condition=Q(sequence__gte=1), name="practical_decision_positive"),
        ]


class EvaluationCompetencePratiqueBase(PracticalEvidenceBase):
    dossier = models.ForeignKey("stages.DossierPratique", on_delete=models.PROTECT, related_name="evaluations_pratiques")
    code = models.CharField(max_length=64)
    revision = models.PositiveIntegerField()
    acquise = models.BooleanField()
    contexte_professionnel = models.TextField()
    date_observation = models.DateField()
    motif_revision = models.TextField(null=True)  # noqa: DJ001 -- initial observation has no revision reason
    remplace = models.ForeignKey("self", on_delete=models.PROTECT, null=True, related_name="+")
    evalue_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    evaluateur_nom = models.CharField(max_length=300)

    class Meta(PracticalEvidenceBase.Meta):
        abstract = True
        ordering = ["code", "-revision"]
        constraints = [
            models.UniqueConstraint(fields=["dossier", "code", "revision"], name="practical_assessment_revision"),
            models.CheckConstraint(condition=Q(revision__gte=1), name="practical_assessment_positive"),
        ]


class AuditPratiqueBase(PracticalModel):
    programme = models.ForeignKey("stages.ProgrammePratique", on_delete=models.PROTECT, null=True, related_name="historique")
    dossier = models.ForeignKey("stages.DossierPratique", on_delete=models.PROTECT, null=True, related_name="historique")
    version = models.PositiveIntegerField()
    action = models.CharField(max_length=40)
    acteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    acteur_nom = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    class Meta(PracticalModel.Meta):
        abstract = True
        ordering = ["-version", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(programme__isnull=False, dossier__isnull=True)
                | Q(programme__isnull=True, dossier__isnull=False), name="practical_audit_aggregate",
            ),
            models.UniqueConstraint(fields=["programme", "version"], name="practical_programme_audit"),
            models.UniqueConstraint(fields=["dossier", "version"], name="practical_dossier_audit"),
        ]
