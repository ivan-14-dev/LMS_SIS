"""Services de synchronisation SIS ↔ Open edX (LMS + CMS) - SIS Secondaire."""

import logging

from django.db import transaction
from django.utils import timezone

from .edx_client import get_edx_client
from .models import EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent

logger = logging.getLogger(__name__)


class SyncService:
    """Orchestration des synchronisations bidirectionnelles."""

    def __init__(self, enqueue_failures: bool = True):
        self.client = get_edx_client()
        # Le rejeu depuis l'outbox (voir tasks.publish_outbox_events) gère lui-même
        # les tentatives/l'état de l'événement d'origine ; il désactive ce
        # ré-enfilage automatique pour éviter de dupliquer des événements outbox
        # à chaque nouvel échec de rejeu.
        self.enqueue_failures = enqueue_failures

    # ====================== SIS → LMS ======================

    def sync_user_to_lms(self, user_sis, role: str = "student") -> EdxUserMapping:
        """Crée/met à jour un utilisateur dans le LMS."""
        try:
            with transaction.atomic():
                mapping, created = EdxUserMapping.objects.get_or_create(
                    user_sis=user_sis,
                    defaults={"username_edx": f"sis-{user_sis.id}"},
                )
                username = mapping.username_edx
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
                        {
                            "email": user_sis.email,
                            "name": user_sis.get_full_name(),
                        },
                    )
                mapping.date_sync = timezone.now()
                mapping.actif = True
                mapping.save()
                logger.info(f"User {username} synced to LMS")
                return mapping
        except Exception as e:
            # Enregistrée hors de la transaction ci-dessus afin que l'événement
            # outbox ne soit pas annulé par le rollback déclenché par l'échec.
            self._enqueue_outbox(
                "user.sync", "user", str(user_sis.id), {"error": str(e), "role": role}
            )
            raise

    def sync_course_to_cms(
        self, matiere, classe, display_name: str
    ) -> EdxCourseMapping:
        """Crée un cours dans Studio (CMS)."""
        org = "SIS"
        number = f"{matiere.code}{classe.nom}".replace(" ", "")[:20]
        run = timezone.now().strftime("%Y")
        course_key = f"course-v1:{org}+{number}+{run}"
        try:
            self.client.create_course(
                org=org,
                number=number,
                run=run,
                display_name=display_name,
            )
            mapping, _ = EdxCourseMapping.objects.update_or_create(
                matiere=matiere,
                classe=classe,
                defaults={"course_id": course_key, "course_name": display_name},
            )
            return mapping
        except Exception as e:
            self._enqueue_outbox(
                "course.create",
                "matiere",
                str(matiere.id),
                {"error": str(e), "classe_id": classe.id, "display_name": display_name},
            )
            raise

    def sync_enrollment_to_lms(
        self, eleve, course_mapping, mode: str = "audit"
    ) -> EdxEnrollment:
        """Inscrit un élève à un cours LMS."""
        try:
            mapping = EdxUserMapping.objects.get(user_sis=eleve.user)
            username = mapping.username_edx
            result = self.client.enroll_user(
                course_mapping.course_id, username, mode=mode
            )
            enrollment, _ = EdxEnrollment.objects.update_or_create(
                eleve=eleve,
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
                "eleve",
                str(eleve.id),
                {
                    "course": course_mapping.course_id,
                    "course_mapping_id": course_mapping.id,
                    "mode": mode,
                    "error": str(e),
                },
            )
            raise

    def bulk_sync_enrollments_to_lms(self, eleves, course_mapping, mode="audit"):
        """Inscription en masse."""
        usernames = []
        enrollments = []
        for eleve in eleves:
            try:
                mapping = EdxUserMapping.objects.get(user_sis=eleve.user)
                usernames.append(mapping.username_edx)
                enrollments.append((eleve, mapping))
            except EdxUserMapping.DoesNotExist:
                logger.warning(f"No LMS mapping for eleve {eleve.id}")
        if not usernames:
            return []
        results = self.client.bulk_enroll(
            course_mapping.course_id, usernames, mode=mode
        )
        out = []
        for (eleve, _mapping), result in zip(enrollments, results, strict=False):
            enrollment, _ = EdxEnrollment.objects.update_or_create(
                eleve=eleve,
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
        self, eleve, course_mapping, subsection_id, score, max_score=20.0
    ):
        """Envoie une note vers le LMS (override)."""
        mapping = EdxUserMapping.objects.get(user_sis=eleve.user)
        return self.client.post_grade(
            course_mapping.course_id,
            mapping.username_edx,
            subsection_id,
            score,
            max_score,
        )

    def sync_certificate_to_lms(self, eleve, course_mapping, cert_type="honor"):
        """Délivre un certificat LMS."""
        mapping = EdxUserMapping.objects.get(user_sis=eleve.user)
        return self.client.issue_certificate(
            course_mapping.course_id, mapping.username_edx, cert_type
        )

    # ====================== LMS → SIS (import) ======================

    def import_grades_from_lms(self, course_mapping) -> int:
        """Importe les notes LMS pour un cours."""
        mapping = EdxCourseMapping.objects.get(pk=course_mapping.pk)
        enrollments = EdxEnrollment.objects.filter(course=mapping, is_active=True)
        count = 0
        for enrollment in enrollments.select_related("eleve__user"):
            try:
                mapping_user = EdxUserMapping.objects.get(
                    user_sis=enrollment.eleve.user
                )
                grades = self.client.get_grades(
                    mapping.course_id, mapping_user.username_edx
                )
                enrollment.progression = min(
                    max(float(grades.get("percent", 0)) * 100, 0), 100
                )
                enrollment.last_sync = timezone.now()
                enrollment.save()
                count += 1
            except Exception as e:
                logger.error(f"Failed to import grades for {enrollment.eleve}: {e}")
        return count

    # ====================== OUTBOX ======================

    def _enqueue_outbox(self, event_type, aggregate_type, aggregate_id, payload):
        if not self.enqueue_failures:
            return
        OutboxEvent.objects.create(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            statut="pending",
        )
