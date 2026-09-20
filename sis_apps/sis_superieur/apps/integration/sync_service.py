"""Services de synchronisation SIS ↔ Open edX (LMS + CMS) - SIS Supérieur."""

import logging

from django.db import transaction
from django.utils import timezone

from .edx_client import get_edx_client
from .models import EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent

logger = logging.getLogger(__name__)


class SyncService:
    """Orchestration des synchronisations bidirectionnelles."""

    def __init__(self):
        self.client = get_edx_client()

    # ====================== SIS → LMS ======================

    @transaction.atomic
    def sync_user_to_lms(self, user_sis, role: str = "student") -> EdxUserMapping:
        mapping, created = EdxUserMapping.objects.get_or_create(
            user_sis=user_sis,
            defaults={"username_edx": f"sis-u-{user_sis.id}"},
        )
        username = mapping.username_edx
        try:
            if created or not mapping.user_id_edx:
                data = {
                    "username": username,
                    "email": user_sis.email,
                    "name": user_sis.get_full_name(),
                    "role": role,
                }
                if user_sis.is_staff or user_sis.is_superuser:
                    data["is_staff"] = True
                result = self.client.create_user(**data)
                mapping.user_id_edx = result.get("id")
            else:
                self.client.update_user(
                    username,
                    {"email": user_sis.email, "name": user_sis.get_full_name()},
                )
            mapping.date_sync = timezone.now()
            mapping.actif = True
            mapping.save()
            return mapping
        except Exception as e:
            self._enqueue_outbox(
                "user.sync", "user", str(user_sis.id), {"error": str(e)}
            )
            raise

    def sync_course_to_cms(
        self, ecue, annee_universitaire, display_name: str
    ) -> EdxCourseMapping:
        org = "SIS-U"
        number = f"{ecue.code}".replace(" ", "")[:20]
        run = str(annee_universitaire.date_debut.year)
        course_key = f"course-v1:{org}+{number}+{run}"
        try:
            self.client.create_course(
                org=org,
                number=number,
                run=run,
                display_name=display_name,
            )
            mapping, _ = EdxCourseMapping.objects.update_or_create(
                ecue=ecue,
                defaults={"course_id": course_key, "course_name": display_name},
            )
            return mapping
        except Exception as e:
            self._enqueue_outbox(
                "course.create", "ecue", str(ecue.id), {"error": str(e)}
            )
            raise

    def sync_enrollment_to_lms(
        self, etudiant, course_mapping, mode: str = "audit"
    ) -> EdxEnrollment:
        try:
            mapping = EdxUserMapping.objects.get(user_sis=etudiant.user)
            result = self.client.enroll_user(
                course_mapping.course_id, mapping.username_edx, mode=mode
            )
            enrollment, _ = EdxEnrollment.objects.update_or_create(
                etudiant=etudiant,
                course=course_mapping,
                defaults={
                    "enrollment_id": result.get("id"),
                    "is_active": True,
                    "last_sync": timezone.now(),
                },
            )
            return enrollment
        except Exception as e:
            self._enqueue_outbox(
                "enrollment.create",
                "etudiant",
                str(etudiant.id),
                {"course": course_mapping.course_id, "error": str(e)},
            )
            raise

    def bulk_sync_enrollments_to_lms(self, etudiants, course_mapping, mode="audit"):
        usernames = []
        enrollments = []
        for etu in etudiants:
            try:
                m = EdxUserMapping.objects.get(user_sis=etu.user)
                usernames.append(m.username_edx)
                enrollments.append((etu, m))
            except EdxUserMapping.DoesNotExist:
                logger.warning(f"No LMS mapping for etudiant {etu.id}")
        if not usernames:
            return []
        results = self.client.bulk_enroll(
            course_mapping.course_id, usernames, mode=mode
        )
        out = []
        for (etu, _mapping), result in zip(enrollments, results, strict=False):
            enrollment, _ = EdxEnrollment.objects.update_or_create(
                etudiant=etu,
                course=course_mapping,
                defaults={
                    "enrollment_id": result.get("id"),
                    "is_active": True,
                    "last_sync": timezone.now(),
                },
            )
            out.append(enrollment)
        return out

    def sync_grade_to_lms(
        self, etudiant, course_mapping, subsection_id, score, max_score=20.0
    ):
        mapping = EdxUserMapping.objects.get(user_sis=etudiant.user)
        return self.client.post_grade(
            course_mapping.course_id,
            mapping.username_edx,
            subsection_id,
            score,
            max_score,
        )

    def sync_certificate_to_lms(self, etudiant, course_mapping, cert_type="honor"):
        mapping = EdxUserMapping.objects.get(user_sis=etudiant.user)
        return self.client.issue_certificate(
            course_mapping.course_id, mapping.username_edx, cert_type
        )

    # ====================== LMS → SIS (import) ======================

    def import_grades_from_lms(self, course_mapping) -> int:
        mapping = EdxCourseMapping.objects.get(pk=course_mapping.pk)
        enrollments = EdxEnrollment.objects.filter(course=mapping, is_active=True)
        count = 0
        for enrollment in enrollments.select_related("etudiant__user"):
            try:
                m = EdxUserMapping.objects.get(user_sis=enrollment.etudiant.user)
                grades = self.client.get_grades(mapping.course_id, m.username_edx)
                enrollment.progression = min(
                    max(float(grades.get("percent", 0)) * 100, 0), 100
                )
                enrollment.last_sync = timezone.now()
                enrollment.save()
                count += 1
            except Exception as e:
                logger.error(f"Failed to import grades: {e}")
        return count

    def _enqueue_outbox(self, event_type, aggregate_type, aggregate_id, payload):
        OutboxEvent.objects.create(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            statut="pending",
        )
