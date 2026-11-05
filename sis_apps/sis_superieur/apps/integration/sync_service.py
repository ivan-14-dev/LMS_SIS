"""Services de synchronisation SIS ↔ Open edX (LMS + CMS) - SIS Supérieur."""

import logging

from django.db import transaction
from django.utils import timezone

from sis_common.lms_courses import course_sync_requested_at
from sis_common.lms_identity import lms_course_number, lms_username
from sis_common.lms_tenants import lms_schema_tenant_id

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
        try:
            with transaction.atomic():
                user_sis = type(user_sis).objects.select_for_update().get(pk=user_sis.pk)
                if not user_sis.is_active:
                    raise ValueError("Un compte SIS désactivé ne peut pas être provisionné.")
                mapping, created = EdxUserMapping.objects.select_for_update().get_or_create(
                    user_sis=user_sis,
                    defaults={"username_edx": lms_username(user_sis)},
                )
                if not mapping.actif:
                    raise ValueError("Une association LMS révoquée ne peut pas être réactivée par synchronisation.")
                username = mapping.username_edx
                full_name = user_sis.get_full_name() or user_sis.username
                if created or not mapping.user_id_edx:
                    data = {
                        "username": username,
                        "email": user_sis.email,
                        "full_name": full_name,
                        "role": role,
                    }
                    result = self.client.create_user(**data)
                    mapping.user_id_edx = result.get("id")
                else:
                    self.client.update_user(
                        username,
                        {"email": user_sis.email, "name": full_name},
                        user_id=mapping.user_id_edx,
                    )
                mapping.date_sync = timezone.now()
                mapping.actif = True
                mapping.save()
                return mapping
        except Exception as e:
            # Enregistrée hors de la transaction ci-dessus afin que l'événement
            # outbox ne soit pas annulé par le rollback déclenché par l'échec.
            self._enqueue_outbox("user.sync", "user", str(user_sis.id), {"error": str(e), "role": role})
            raise

    def sync_course_to_cms(
        self, ecue, annee_universitaire, display_name: str, *, requested_at=None
    ) -> EdxCourseMapping:
        requested_at = course_sync_requested_at(requested_at)
        try:
            with transaction.atomic():
                ecue = type(ecue).objects.select_for_update().get(pk=ecue.pk)
                annee_universitaire = (
                    type(annee_universitaire).objects.select_for_update().get(pk=annee_universitaire.pk)
                )
                if (
                    annee_universitaire.universite_id != lms_schema_tenant_id()
                    or ecue.ue.semestre.annee_universitaire_id != annee_universitaire.pk
                    or ecue.ue.maquette.annee_universitaire_id != annee_universitaire.pk
                ):
                    raise ValueError("L'année demandée doit appartenir à l'université et à l'ECUE.")
                mapping = EdxCourseMapping.objects.select_for_update().filter(ecue=ecue).first()
                if mapping:
                    if not mapping.actif:
                        raise ValueError("Une association de cours révoquée ne peut pas être réactivée.")
                    if mapping.last_sync_requested_at and requested_at < mapping.last_sync_requested_at:
                        logger.info("Course sync superseded mapping_id=%s", mapping.pk)
                        return mapping
                    result = self.client.update_course(mapping.course_id, {"display_name": display_name})
                else:
                    result = self.client.create_course(
                        org="SIS-U", number=lms_course_number(ecue), run="sis", display_name=display_name
                    )
                mapping, _ = EdxCourseMapping.objects.update_or_create(
                    ecue=ecue,
                    defaults={
                        "course_id": result["id"],
                        "course_name": result["display_name"],
                        "last_sync_requested_at": requested_at,
                    },
                )
                return mapping
        except Exception as e:
            self._enqueue_outbox(
                "course.create",
                "ecue",
                str(ecue.id),
                {
                    "error": str(e),
                    "annee_universitaire_id": annee_universitaire.id,
                    "display_name": display_name,
                    "requested_at": requested_at.isoformat(),
                },
            )
            raise

    def sync_enrollment_to_lms(self, etudiant, course_mapping, mode="audit", *, active=True, requested_at=None):
        from sis_common.lms_access_sync import dispatch_access

        if mode != "audit":
            raise ValueError("Le contrat d'inscription à droits limités accepte uniquement le mode audit.")
        dispatch_access(self, etudiant.user, course_mapping, kind="enrollment", active=active, requested_at=requested_at)
        return EdxEnrollment.objects.filter(etudiant=etudiant, course=course_mapping).first()

    def sync_teaching_to_lms(self, user, course_mapping, *, active):
        from sis_common.lms_access_sync import dispatch_access

        return dispatch_access(self, user, course_mapping, kind="teaching", active=active)

    def bulk_sync_enrollments_to_lms(self, etudiants, course_mapping, mode="audit"):
        return [self.sync_enrollment_to_lms(etudiant, course_mapping, mode=mode) for etudiant in etudiants]

    def sync_grade_to_lms(self, etudiant, course_mapping, subsection_id, score, max_score=20.0):
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
        return self.client.issue_certificate(course_mapping.course_id, mapping.username_edx, cert_type)

    # ====================== LMS → SIS (import) ======================

    def import_grades_from_lms(self, course_mapping) -> int:
        mapping = EdxCourseMapping.objects.get(pk=course_mapping.pk)
        enrollments = EdxEnrollment.objects.filter(course=mapping, is_active=True)
        count = 0
        for enrollment in enrollments.select_related("etudiant__user"):
            try:
                m = EdxUserMapping.objects.get(user_sis=enrollment.etudiant.user)
                grades = self.client.get_grades(mapping.course_id, m.username_edx)
                enrollment.progression = min(max(float(grades.get("percent", 0)) * 100, 0), 100)
                enrollment.last_sync = timezone.now()
                enrollment.save()
                count += 1
            except Exception as e:
                logger.error(f"Failed to import grades: {e}")
        return count

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
