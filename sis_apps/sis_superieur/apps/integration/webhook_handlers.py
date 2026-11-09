"""Handlers de webhooks entrants (LMS + CMS) - SIS Supérieur."""

import hashlib
import logging

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from sis_common.lms_grade_review import stage_lms_grade
from sis_common.lms_receipts import confirm_account, enrollment_receipt_allowed, update_enrollment_receipts

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

    @staticmethod
    def _event_data(payload):
        return payload.get("data", payload)

    @classmethod
    def _username(cls, payload, container_name=None):
        data = cls._event_data(payload)
        container = data.get(container_name, data) if container_name else data
        user = container.get("user") or data.get("user") or {}
        return user.get("username") or (user.get("pii") or {}).get("username")

    @classmethod
    def _course_key(cls, payload, container_name=None):
        data = cls._event_data(payload)
        container = data.get(container_name, data) if container_name else data
        course = container.get("course") or data.get("course") or {}
        return course.get("course_key") or course.get("id")

    def handle_user_created(self, payload: dict):
        return confirm_account(self.EdxUserMapping, payload)

    def handle_user_updated(self, payload: dict):
        return confirm_account(self.EdxUserMapping, payload)

    def handle_enrollment_created(self, payload: dict):
        payload = self._event_data(payload)
        enrollment_data = payload.get("enrollment") or payload
        username = self._username(payload, "enrollment")
        course_key = self._course_key(payload, "enrollment")
        if not username or not course_key:
            return
        try:
            mapping = self.EdxUserMapping.objects.get(username_edx=username)
            course_mapping = self.EdxCourseMapping.objects.get(course_id=course_key)
            if not enrollment_receipt_allowed(mapping, course_mapping, enrollment_data.get("is_active", True)):
                return False
            self.EdxEnrollment.objects.update_or_create(
                etudiant=mapping.user_sis.etudiant_profile,
                course=course_mapping,
                defaults={
                    "enrollment_id": enrollment_data.get("id"),
                    "is_active": enrollment_data.get("is_active", True),
                    "last_sync": timezone.now(),
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to sync enrollment: {e}")
            return False

    def handle_enrollment_updated(self, payload: dict):
        payload = self._event_data(payload)
        enrollment_data = payload.get("enrollment") or payload
        enrollment_id = enrollment_data.get("id")
        is_active = enrollment_data.get("is_active", True)
        if enrollment_id is not None:
            queryset = self.EdxEnrollment.objects.filter(enrollment_id=enrollment_id)
        else:
            username = self._username(payload, "enrollment")
            course_key = self._course_key(payload, "enrollment")
            if not (username and course_key):
                return False
            try:
                mapping = self.EdxUserMapping.objects.get(username_edx=username)
                queryset = self.EdxEnrollment.objects.filter(
                    etudiant=mapping.user_sis.etudiant_profile,
                    course__course_id=course_key,
                )
            except Exception as e:
                logger.error(f"Failed to find enrollment: {e}")
                return False
        return update_enrollment_receipts(queryset, "etudiant", is_active)

    def handle_enrollment_deleted(self, payload: dict):
        payload = self._event_data(payload)
        enrollment_data = payload.get("enrollment") or payload
        enrollment_id = enrollment_data.get("id")
        if enrollment_id is not None:
            queryset = self.EdxEnrollment.objects.filter(enrollment_id=enrollment_id)
        else:
            username = self._username(payload, "enrollment")
            course_key = self._course_key(payload, "enrollment")
            if not (username and course_key):
                return False
            try:
                mapping = self.EdxUserMapping.objects.get(username_edx=username)
                queryset = self.EdxEnrollment.objects.filter(
                    etudiant=mapping.user_sis.etudiant_profile,
                    course__course_id=course_key,
                )
            except Exception as e:
                logger.error(f"Failed to find enrollment: {e}")
                return False
        return update_enrollment_receipts(queryset, "etudiant", False)

    def handle_grade_updated(self, payload: dict):
        payload = {**self._event_data(payload), "_event_id": payload.get("_event_id")}
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

                evaluation = assessment.evaluation
                if (
                    not mapping.actif
                    or not enrollment.is_active
                    or not enrollment.course.actif
                    or evaluation.semestre.cloture
                    or evaluation.semestre.annee_universitaire.cloturee
                ):
                    logger.info("Grade retained without SIS import: inactive access or closed period for %s", event_id)
                    return True

                if self.EdxGradeLog.objects.filter(
                    enrollment=enrollment,
                    subsection_id=subsection_id,
                    imported_to_sis=True,
                    timestamp_lms__gt=timestamp,
                ).exists():
                    logger.info("Ignored out-of-order grade event %s", event_id)
                    return True

                stage_lms_grade(grade_log, evaluation)
            return True
        except Exception as e:
            logger.exception("Failed to import LMS grade: %s", e)
            return False

    def handle_course_grade_changed(self, payload: dict):
        """Met à jour la progression depuis l'événement public de note globale."""
        data = self._event_data(payload)
        grade = data.get("grade") or data
        course_key = self._course_key({"data": grade})
        user_id = grade.get("user_id") or (grade.get("user") or {}).get("id")
        if not (course_key and user_id):
            return False
        try:
            mapping = self.EdxUserMapping.objects.get(user_id_edx=user_id)
            enrollment = self.EdxEnrollment.objects.get(
                etudiant=mapping.user_sis.etudiant_profile,
                course__course_id=course_key,
            )
            percent = float(grade.get("percent_grade", 0))
            enrollment.progression = min(
                max(percent * 100 if percent <= 1 else percent, 0), 100
            )
            enrollment.last_sync = timezone.now()
            enrollment.save(update_fields=["progression", "last_sync"])
            return True
        except Exception as e:
            logger.exception("Failed to import LMS course grade: %s", e)
            return False

    def handle_certificate_awarded(self, payload: dict):
        payload = self._event_data(payload)
        username = self._username(payload, "certificate")
        course_key = self._course_key(payload, "certificate")
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
            return True
        except Exception as e:
            logger.error(f"Failed to log certificate: {e}")
            return False

    def handle_certificate_revoked(self, payload: dict):
        payload = self._event_data(payload)
        username = self._username(payload, "certificate")
        course_key = self._course_key(payload, "certificate")
        logger.info("Certificate revoked: %s → %s", username, course_key)
        return bool(username and course_key)

    def handle_course_published(self, payload: dict):
        payload = self._event_data(payload)
        course_key = payload.get("course_key")
        if not course_key:
            return False
        return self.EdxCourseMapping.objects.filter(course_id=course_key).exists()

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
            "certificate.revoked": self.handle_certificate_revoked,
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
            "org.openedx.learning.course.persistent_grade_summary.changed.v1": self.handle_course_grade_changed,
            "org.openedx.learning.certificate.issued.v1": self.handle_certificate_awarded,
            "org.openedx.learning.certificate.created.v1": self.handle_certificate_awarded,
            "org.openedx.learning.certificate.changed.v1": self.handle_certificate_awarded,
            "org.openedx.learning.certificate.revoked.v1": self.handle_certificate_revoked,
            "org.openedx.learning.course.enrollment.created.v1": self.handle_enrollment_created,
            "org.openedx.learning.course.enrollment.changed.v1": self.handle_enrollment_updated,
            "org.openedx.learning.course.unenrollment.completed.v1": self.handle_enrollment_deleted,
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
            return handler(payload) is not False
        except Exception as e:
            logger.error(f"Handler error for {event_type}: {e}")
            return False
