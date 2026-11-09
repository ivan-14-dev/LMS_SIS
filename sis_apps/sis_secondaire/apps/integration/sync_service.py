"""Services de synchronisation SIS ↔ Open edX (LMS + CMS) - SIS Secondaire."""

import logging

from django.db import transaction
from django.utils import timezone

from sis_common.lms_courses import course_sync_requested_at
from sis_common.lms_delivery import begin_delivery, finish_delivery
from sis_common.lms_identity import lms_course_number, lms_username
from sis_common.lms_tenants import lms_schema_tenant_id

from .edx_client import get_edx_client
from .models import EdxCourseMapping, EdxEnrollment, EdxUserMapping

logger = logging.getLogger(__name__)


class SyncService:
    """Orchestration des synchronisations bidirectionnelles."""

    def __init__(self, enqueue_failures: bool = True):
        self._client = None
        # Le rejeu depuis l'outbox (voir tasks.publish_outbox_events) gère lui-même
        # les tentatives/l'état de l'événement d'origine ; il désactive ce
        # ré-enfilage automatique pour éviter de dupliquer des événements outbox
        # à chaque nouvel échec de rejeu.
        self.enqueue_failures = enqueue_failures

    @property
    def client(self):
        if self._client is None:
            self._client = get_edx_client()
        return self._client

    # ====================== SIS → LMS ======================

    def sync_user_to_lms(self, user_sis, role: str = "student") -> EdxUserMapping:
        """Crée/met à jour un utilisateur dans le LMS."""
        event = begin_delivery(self, "user.sync", "user", user_sis.pk, {"role": role})
        try:
            with transaction.atomic():
                user_sis = type(user_sis).objects.select_for_update().get(pk=user_sis.pk)
                if not user_sis.is_active:
                    raise ValueError("Un compte SIS désactivé ne peut pas être provisionné.")
                if user_sis.etablissement_id not in (None, lms_schema_tenant_id()):
                    raise ValueError("Le compte doit appartenir à l'établissement courant.")
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
                        {
                            "email": user_sis.email,
                            "name": full_name,
                        },
                        user_id=mapping.user_id_edx,
                    )
                mapping.date_sync = timezone.now()
                mapping.actif = True
                mapping.save()
                logger.info(f"User {username} synced to LMS")
                finish_delivery(event)
                return mapping
        except Exception as e:
            finish_delivery(event, e)
            raise

    def sync_course_to_cms(self, matiere, classe, display_name: str, *, requested_at=None) -> EdxCourseMapping:
        """Crée ou met à jour un cours sans changer son identité à la reprise."""
        requested_at = course_sync_requested_at(requested_at)
        event = begin_delivery(
            self,
            "course.create",
            "matiere",
            matiere.pk,
            {"classe_id": classe.pk, "display_name": display_name, "requested_at": requested_at.isoformat()},
        )
        try:
            with transaction.atomic():
                matiere = type(matiere).objects.select_for_update().get(pk=matiere.pk)
                classe = type(classe).objects.select_for_update().get(pk=classe.pk)
                tenant_id = lms_schema_tenant_id()
                if (
                    matiere.etablissement_id not in (None, tenant_id)
                    or classe.etablissement_id not in (None, tenant_id)
                    or classe.annee_scolaire.etablissement_id != tenant_id
                    or classe.niveau.etablissement_id != tenant_id
                ):
                    raise ValueError("La matière et la classe doivent appartenir au même établissement.")
                mapping = EdxCourseMapping.objects.select_for_update().filter(matiere=matiere, classe=classe).first()
                if mapping:
                    if not mapping.actif:
                        raise ValueError("Une association de cours révoquée ne peut pas être réactivée.")
                    if mapping.last_sync_requested_at and requested_at < mapping.last_sync_requested_at:
                        logger.info("Course sync superseded mapping_id=%s", mapping.pk)
                        finish_delivery(event)
                        return mapping
                    result = self.client.update_course(mapping.course_id, {"display_name": display_name})
                else:
                    result = self.client.create_course(
                        org="SIS",
                        number=lms_course_number(matiere, namespace=classe),
                        run="sis",
                        display_name=display_name,
                    )
                mapping, _ = EdxCourseMapping.objects.update_or_create(
                    matiere=matiere,
                    classe=classe,
                    defaults={
                        "course_id": result["id"],
                        "course_name": result["display_name"],
                        "last_sync_requested_at": requested_at,
                    },
                )
                finish_delivery(event)
                return mapping
        except Exception as e:
            finish_delivery(event, e)
            raise

    def sync_enrollment_to_lms(self, eleve, course_mapping, mode="audit", *, active=True, requested_at=None):
        from sis_common.lms_access_sync import dispatch_access

        if mode != "audit":
            raise ValueError("Le contrat d'inscription à droits limités accepte uniquement le mode audit.")
        dispatch_access(self, eleve.user, course_mapping, kind="enrollment", active=active, requested_at=requested_at)
        return EdxEnrollment.objects.filter(eleve=eleve, course=course_mapping).first()

    def sync_teaching_to_lms(self, user, course_mapping, *, active):
        from sis_common.lms_access_sync import dispatch_access

        return dispatch_access(self, user, course_mapping, kind="teaching", active=active)

    def bulk_sync_enrollments_to_lms(self, eleves, course_mapping, mode="audit"):
        """Inscription en masse."""
        return [self.sync_enrollment_to_lms(eleve, course_mapping, mode=mode) for eleve in eleves]

    def sync_grade_to_lms(self, eleve, course_mapping, subsection_id, score, max_score=20.0):
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
        return self.client.issue_certificate(course_mapping.course_id, mapping.username_edx, cert_type)

    # ====================== LMS → SIS (import) ======================

    def import_grades_from_lms(self, course_mapping) -> int:
        """Importe les notes LMS pour un cours."""
        mapping = EdxCourseMapping.objects.get(pk=course_mapping.pk)
        enrollments = EdxEnrollment.objects.filter(course=mapping, is_active=True)
        count = 0
        for enrollment in enrollments.select_related("eleve__user"):
            try:
                mapping_user = EdxUserMapping.objects.get(user_sis=enrollment.eleve.user)
                grades = self.client.get_grades(mapping.course_id, mapping_user.username_edx)
                enrollment.progression = min(max(float(grades.get("percent", 0)) * 100, 0), 100)
                enrollment.last_sync = timezone.now()
                enrollment.save()
                count += 1
            except Exception as e:
                logger.error(f"Failed to import grades for {enrollment.eleve}: {e}")
        return count
