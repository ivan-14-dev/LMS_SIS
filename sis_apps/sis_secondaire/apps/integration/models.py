"""Models for Open edX integration (SIS Secondaire)."""

from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve
from django.db import models


class EdxUserMapping(models.Model):
    """Mapping entre utilisateur SIS et utilisateur LMS Open edX."""

    user_sis = models.OneToOneField(
        "utilisateurs.Utilisateur", on_delete=models.CASCADE, related_name="edx_mapping"
    )
    username_edx = models.CharField(max_length=200, unique=True)
    user_id_edx = models.PositiveBigIntegerField(null=True, blank=True)
    date_sync = models.DateTimeField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mapping utilisateur EdX"
        verbose_name_plural = "Mappings utilisateurs EdX"

    def __str__(self):
        return f"{self.user_sis.username} ↔ {self.username_edx}"


class EdxCourseMapping(models.Model):
    """Mapping entre matière/classe et cours LMS."""

    matiere = models.ForeignKey(
        Matiere, on_delete=models.CASCADE, related_name="edx_courses"
    )
    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE, related_name="edx_courses"
    )
    course_id = models.CharField(max_length=200, unique=True)
    course_name = models.CharField(max_length=300)
    date_creation = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = [("matiere", "classe")]
        verbose_name = "Mapping cours EdX"
        verbose_name_plural = "Mappings cours EdX"

    def __str__(self):
        return f"{self.matiere} / {self.classe} → {self.course_id}"


class EdxEnrollment(models.Model):
    """Inscription d'un élève à un cours LMS."""

    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="edx_enrollments"
    )
    course = models.ForeignKey(
        EdxCourseMapping, on_delete=models.CASCADE, related_name="enrollments"
    )
    enrollment_id = models.PositiveBigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    date_inscription = models.DateTimeField(auto_now_add=True)
    date_desinscription = models.DateTimeField(null=True, blank=True)
    progression = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    last_sync = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("eleve", "course")]
        verbose_name = "Inscription EdX"
        verbose_name_plural = "Inscriptions EdX"

    def __str__(self):
        return f"{self.eleve} → {self.course.course_id}"


class EdxGradeLog(models.Model):
    """Log des notes synchronisées depuis LMS."""

    enrollment = models.ForeignKey(
        EdxEnrollment, on_delete=models.CASCADE, related_name="grade_logs"
    )
    subsection_id = models.CharField(max_length=200)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    completion = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    timestamp_lms = models.DateTimeField()
    imported_to_sis = models.BooleanField(default=False)
    note_sis = models.ForeignKey(
        "notes.Note",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sources_lms",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log note EdX"
        verbose_name_plural = "Logs notes EdX"
        ordering = ["-timestamp_lms"]

    def __str__(self):
        return f"{self.enrollment} - {self.subsection_id} : {self.score}"


class OutboxEvent(models.Model):
    """Outbox pour événements à publier vers LMS ou autres services."""

    STATUT_CHOICES = [
        ("pending", "En attente"),
        ("processing", "En cours"),
        ("done", "Traité"),
        ("failed", "Échec"),
        ("dead", "Dead letter"),
    ]
    event_type = models.CharField(max_length=100)
    aggregate_type = models.CharField(max_length=100)
    aggregate_id = models.CharField(max_length=100)
    payload = models.JSONField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="pending")
    nb_tentatives = models.PositiveSmallIntegerField(default=0)
    derniere_tentative = models.DateTimeField(null=True, blank=True)
    erreur = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Événement outbox"
        verbose_name_plural = "Événements outbox"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["statut", "created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.aggregate_type}#{self.aggregate_id}"
