"""Serializers for integration (SIS Supérieur)."""

from rest_framework import serializers

from .models import EdxCourseMapping, EdxEnrollment, EdxGradeLog, EdxUserMapping, OutboxEvent


class EdxUserMappingSerializer(serializers.ModelSerializer):
    """Serializer pour les mappings utilisateur EdX."""

    user_sis_username = serializers.CharField(
        source="user_sis.username", read_only=True
    )
    user_sis_email = serializers.CharField(source="user_sis.email", read_only=True)
    user_sis_name = serializers.CharField(
        source="user_sis.get_full_name", read_only=True
    )

    class Meta:
        model = EdxUserMapping
        fields = [
            "id",
            "user_sis",
            "user_sis_username",
            "user_sis_email",
            "user_sis_name",
            "username_edx",
            "user_id_edx",
            "date_sync",
            "actif",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "date_sync"]


class EdxCourseMappingSerializer(serializers.ModelSerializer):
    """Serializer pour les mappings cours EdX."""

    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)

    class Meta:
        model = EdxCourseMapping
        fields = [
            "id",
            "ecue",
            "ecue_code",
            "ecue_nom",
            "course_id",
            "course_name",
            "date_creation",
            "actif",
        ]
        read_only_fields = ["id", "date_creation"]


class EdxEnrollmentSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions EdX."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    course_name = serializers.CharField(source="course.course_name", read_only=True)
    course_id_edx = serializers.CharField(source="course.course_id", read_only=True)

    class Meta:
        model = EdxEnrollment
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "course",
            "course_name",
            "course_id_edx",
            "enrollment_id",
            "is_active",
            "date_inscription",
            "date_desinscription",
            "progression",
            "last_sync",
        ]
        read_only_fields = ["id", "date_inscription", "last_sync"]


class EdxGradeLogSerializer(serializers.ModelSerializer):
    """Serializer pour les logs de notes EdX."""

    etudiant_matricule = serializers.CharField(
        source="enrollment.etudiant.matricule", read_only=True
    )
    course_id = serializers.CharField(
        source="enrollment.course.course_id", read_only=True
    )

    class Meta:
        model = EdxGradeLog
        fields = [
            "id",
            "enrollment",
            "etudiant_matricule",
            "course_id",
            "subsection_id",
            "score",
            "max_score",
            "completion",
            "timestamp_lms",
            "imported_to_sis",
            "note_sis",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class OutboxEventSerializer(serializers.ModelSerializer):
    """Serializer pour les événements outbox."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = OutboxEvent
        fields = [
            "id",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "payload",
            "statut",
            "statut_display",
            "nb_tentatives",
            "derniere_tentative",
            "erreur",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SyncUserRequestSerializer(serializers.Serializer):
    """Serializer pour les requêtes de synchronisation utilisateur."""

    user_id = serializers.IntegerField(required=True)
    role = serializers.ChoiceField(
        choices=["student", "staff", "instructor"], default="student"
    )


class SyncCourseRequestSerializer(serializers.Serializer):
    """Serializer pour les requêtes de synchronisation cours."""

    ecue_id = serializers.IntegerField(required=True)
    annee_id = serializers.IntegerField(required=True)
    display_name = serializers.CharField(required=False, max_length=200)


class SyncEnrollmentRequestSerializer(serializers.Serializer):
    """Serializer pour les requêtes d'inscription."""

    etudiant_id = serializers.IntegerField(required=True)
    course_mapping_id = serializers.IntegerField(required=True)
    mode = serializers.ChoiceField(
        choices=["audit", "verified", "honor"], default="audit"
    )


class WebhookPayloadSerializer(serializers.Serializer):
    """Serializer de base pour les webhooks entrants."""

    event_type = serializers.CharField(required=True)
    timestamp = serializers.DateTimeField(required=False)
    data = serializers.DictField(required=True)
