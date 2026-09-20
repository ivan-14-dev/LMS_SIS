"""Handlers de webhooks entrants (LMS + CMS) - SIS Supérieur."""

import hashlib
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Traite les webhooks entrants LMS / CMS."""

    def __init__(
        self,
        edx_user_mapping_model,
        edx_course_mapping_model,
        edx_enrollment_model,
        edx_grade_log_model,
        etudiant_model,
        note_model,
    ):
        self.EdxUserMapping = edx_user_mapping_model
        self.EdxCourseMapping = edx_course_mapping_model
        self.EdxEnrollment = edx_enrollment_model
        self.EdxGradeLog = edx_grade_log_model
        self.Etudiant = etudiant_model
        self.Note = note_model

    def handle_user_created(self, payload: dict):
        username = (payload.get("user") or {}).get("username")
        if not username:
            return
        user_data = payload.get("user", {})
        self.EdxUserMapping.objects.update_or_create(
            username_edx=username,
            defaults={
                "user_id_edx": user_data.get("id"),
                "actif": True,
                "date_sync": timezone.now(),
            },
        )
        logger.info(f"LMS user synced: {username}")

    def handle_user_updated(self, payload: dict):
        username = (payload.get("user") or {}).get("username")
        if not username:
            return
        try:
            mapping = self.EdxUserMapping.objects.get(username_edx=username)
            mapping.user_id_edx = payload["user"].get("id", mapping.user_id_edx)
            mapping.date_sync = timezone.now()
            mapping.save()
        except self.EdxUserMapping.DoesNotExist:
            self.handle_user_created(payload)

    def handle_enrollment_created(self, payload: dict):
        username = (payload.get("user") or {}).get("username")
        course_key = (payload.get("course") or {}).get("course_key")
        if not username or not course_key:
            return
        try:
            mapping = self.EdxUserMapping.objects.get(username_edx=username)
            course_mapping = self.EdxCourseMapping.objects.get(course_id=course_key)
            self.EdxEnrollment.objects.update_or_create(
                etudiant=mapping.user_sis.etudiant_profile,
                course=course_mapping,
                defaults={
                    "enrollment_id": (payload.get("enrollment") or {}).get("id"),
                    "is_active": True,
                    "last_sync": timezone.now(),
                },
            )
        except Exception as e:
            logger.error(f"Failed to sync enrollment: {e}")

    def handle_enrollment_updated(self, payload: dict):
        enrollment_id = (payload.get("enrollment") or {}).get("id")
        is_active = (payload.get("enrollment") or {}).get("is_active", True)
        if enrollment_id is None:
            return
        self.EdxEnrollment.objects.filter(enrollment_id=enrollment_id).update(
            is_active=is_active, last_sync=timezone.now()
        )

    def handle_enrollment_deleted(self, payload: dict):
        enrollment_id = (payload.get("enrollment") or {}).get("id")
        if enrollment_id is None:
            return
        self.EdxEnrollment.objects.filter(enrollment_id=enrollment_id).update(
            is_active=False, date_desinscription=timezone.now()
        )

    def handle_grade_updated(self, payload: dict):
        username = (payload.get("user") or {}).get("username")
        course_key = (payload.get("course") or {}).get("course_key")
        subsection_id = payload.get("subsection_id")
        score = payload.get("score")
        max_score = payload.get("max_score", 100.0)
        completion = payload.get("completion", 0.0)
        timestamp = parse_datetime(payload.get("timestamp", "")) or timezone.now()
        if not (username and course_key and subsection_id) or score is None:
            return False
        try:
            mapping = self.EdxUserMapping.objects.get(username_edx=username)
            enrollment = self.EdxEnrollment.objects.get(
                etudiant=mapping.user_sis.etudiant_profile,
                course__course_id=course_key,
            )
            event_id = payload.get("_event_id") or payload.get("event_id")
            if not event_id:
                material = (
                    f"{username}|{course_key}|{subsection_id}|{score}|"
                    f"{max_score}|{timestamp.isoformat()}"
                )
                event_id = hashlib.sha256(material.encode()).hexdigest()

            with transaction.atomic():
                grade_log, created = self.EdxGradeLog.objects.get_or_create(
                    event_id=event_id,
                    defaults={
                        "enrollment": enrollment,
                        "subsection_id": subsection_id,
                        "score": score,
                        "max_score": max_score,
                        "completion": completion,
                        "timestamp_lms": timestamp,
                    },
                )
                if not created:
                    return True

                assessment = (
                    enrollment.course.assessments.select_related("evaluation")
                    .filter(subsection_id=subsection_id, actif=True)
                    .first()
                )
                if not assessment:
                    logger.info(
                        "Grade retained without SIS import: no mapping for %s",
                        subsection_id,
                    )
                    return True

                max_score_decimal = Decimal(str(max_score))
                if max_score_decimal <= 0:
                    raise ValueError("max_score must be greater than zero")
                evaluation = assessment.evaluation
                value = (
                    Decimal(str(score)) * evaluation.bareme / max_score_decimal
                ).quantize(Decimal("0.01"))
                value = min(max(value, Decimal("0")), evaluation.bareme)
                note, _ = self.Note.objects.update_or_create(
                    evaluation=evaluation,
                    etudiant=enrollment.etudiant,
                    defaults={"valeur": value, "statut": "presente"},
                )
                grade_log.note_sis = note
                grade_log.imported_to_sis = True
                grade_log.save(update_fields=["note_sis", "imported_to_sis"])
            return True
        except Exception as e:
            logger.exception("Failed to import LMS grade: %s", e)
            return False

    def handle_certificate_awarded(self, payload: dict):
        username = (payload.get("user") or {}).get("username")
        course_key = (payload.get("course") or {}).get("course_key")
        if not (username and course_key):
            return
        try:
            mapping = self.EdxUserMapping.objects.get(username_edx=username)
            enrollment = self.EdxEnrollment.objects.get(
                etudiant=mapping.user_sis.etudiant_profile,
                course__course_id=course_key,
            )
            enrollment.progression = 100.0
            enrollment.save()
        except Exception as e:
            logger.error(f"Failed to log certificate: {e}")

    def handle_course_published(self, payload: dict):
        course_key = payload.get("course_key")
        if not course_key:
            return
        self.EdxCourseMapping.objects.filter(course_id=course_key).update(actif=True)

    def handle_course_deleted(self, payload: dict):
        course_key = payload.get("course_key")
        if not course_key:
            return
        self.EdxCourseMapping.objects.filter(course_id=course_key).update(actif=False)
        self.EdxEnrollment.objects.filter(course__course_id=course_key).update(
            is_active=False, date_desinscription=timezone.now()
        )

    def handle_xblock_published(self, payload: dict):
        logger.info(
            f"XBlock published: {payload.get('block_id')} in {payload.get('course_id')}"
        )

    def handle_asset_uploaded(self, payload: dict):
        logger.info(f"Asset uploaded: {payload.get('asset_id')}")

    def handle(self, event_type: str, payload: dict):
        router = {
            "user.created": self.handle_user_created,
            "user.updated": self.handle_user_updated,
            "enrollment.created": self.handle_enrollment_created,
            "enrollment.updated": self.handle_enrollment_updated,
            "enrollment.deleted": self.handle_enrollment_deleted,
            "grade.updated": self.handle_grade_updated,
            "certificate.issued": self.handle_certificate_awarded,
            "certificate.revoked": self.handle_certificate_awarded,
            "course.published": self.handle_course_published,
            "course.deleted": self.handle_course_deleted,
            "xblock.published": self.handle_xblock_published,
            "asset.uploaded": self.handle_asset_uploaded,
            "org.openedx.learning.user.created.v1": self.handle_user_created,
            "org.openedx.learning.user.updated.v1": self.handle_user_updated,
            "org.openedx.learning.enrollment.created.v1": self.handle_enrollment_created,
            "org.openedx.learning.enrollment.updated.v1": self.handle_enrollment_updated,
            "org.openedx.learning.enrollment.deleted.v1": self.handle_enrollment_deleted,
            "org.openedx.learning.course.grade.updated.v1": self.handle_grade_updated,
            "org.openedx.learning.course.assessment.grade.changed.v1": self.handle_grade_updated,
            "org.openedx.learning.certificate.issued.v1": self.handle_certificate_awarded,
            "org.openedx.learning.certificate.revoked.v1": self.handle_certificate_awarded,
            "org.openedx.studio.course.published.v1": self.handle_course_published,
            "org.openedx.studio.course.deleted.v1": self.handle_course_deleted,
            "org.openedx.studio.xblock.published.v1": self.handle_xblock_published,
            "org.openedx.studio.asset.uploaded.v1": self.handle_asset_uploaded,
        }
        handler = router.get(event_type)
        if not handler:
            logger.warning(f"Unknown event type: {event_type}")
            return False
        try:
            handler(payload)
            return True
        except Exception as e:
            logger.error(f"Handler error for {event_type}: {e}")
            return False
