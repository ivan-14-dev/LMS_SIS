"""Models for Open edX integration (SIS Supérieur)."""

from django.db import models


class EdxUserMapping(models.Model):
    user_sis = models.OneToOneField(
        "utilisateurs.Utilisateur",
        on_delete=models.CASCADE,
        related_name="edx_mapping_u",
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
    """Mapping entre ECUE et cours LMS."""

    ecue = models.OneToOneField(
        "ue_ecue.ECUE", on_delete=models.CASCADE, related_name="edx_course"
    )
    course_id = models.CharField(max_length=200, unique=True)
    course_name = models.CharField(max_length=300)
    date_creation = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Mapping cours EdX"
        verbose_name_plural = "Mappings cours EdX"

    def __str__(self):
        return f"{self.ecue} → {self.course_id}"


class EdxEnrollment(models.Model):
    etudiant = models.ForeignKey(
        "etudiants.Etudiant", on_delete=models.CASCADE, related_name="edx_enrollments"
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
        unique_together = [("etudiant", "course")]

    def __str__(self):
        return f"{self.etudiant} → {self.course.course_id}"


class EdxGradeLog(models.Model):
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
        ordering = ["-timestamp_lms"]

    def __str__(self):
        return f"{self.enrollment} - {self.subsection_id} : {self.score}"


class OutboxEvent(models.Model):
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
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["statut", "created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.aggregate_type}#{self.aggregate_id}"
