"""Persist desired access before I/O; replay only the latest decision."""

import logging
from datetime import timedelta

import requests
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .lms_courses import course_sync_requested_at

logger = logging.getLogger(__name__)

REVOKED_LEARNER_STATUSES = ("suspendu", "abandon", "sortant", "transfere", "transfert", "diplome")


def permanent_access_failure(error):
    if isinstance(error, (ValueError, ObjectDoesNotExist)):
        return True
    response = getattr(error, "response", None)
    return (
        isinstance(error, requests.HTTPError)
        and response is not None
        and 400 <= response.status_code < 500
        and response.status_code not in (408, 429)
    )


def learner_model():
    if apps.is_installed("apps.classes"):
        return apps.get_model("eleves", "Eleve"), "eleve"
    return apps.get_model("etudiants", "Etudiant"), "etudiant"


def learner_registration_revoked(learner, course):
    if learner.statut in REVOKED_LEARNER_STATUSES:
        return True
    if apps.is_installed("apps.classes"):
        registrations = learner.inscriptions.filter(annee_scolaire_id=course.classe.annee_scolaire_id)
        return registrations.exclude(statut="validee", classe_id=course.classe_id).exists()
    registrations = learner.inscriptions_admin.filter(
        annee_universitaire_id=course.ecue.ue.semestre.annee_universitaire_id,
        formation_id=course.ecue.ue.maquette.formation_id,
    )
    return registrations.exclude(statut="validee").exists()


def revocation_reason(user, course, mapping, kind):
    if not user.is_active or not mapping.actif or not course.actif:
        return "Un compte ou une association révoquée ne peut pas recevoir un accès LMS."
    if kind == "teaching" and user.role != "enseignant":
        return "Un profil enseignant est requis pour attribuer des droits Studio."
    if kind == "enrollment":
        model, _ = learner_model()
        learner = model.objects.filter(user=user).first()
        if learner is None:
            return "Le dossier apprenant doit exister avant toute inscription LMS."
        if learner_registration_revoked(learner, course):
            return "La scolarité suspendue, retirée ou non validée ne permet pas cet accès LMS."
    return None


def validate_grant(user, course, mapping, kind, active):
    if active and (reason := revocation_reason(user, course, mapping, kind)):
        raise ValueError(reason)


def access_retry_ready():
    now = timezone.now()
    ready = Q(derniere_tentative__isnull=True)
    for attempts in range(6):
        ready |= Q(nb_tentatives=attempts, derniere_tentative__lte=now - timedelta(seconds=5 * 2**attempts))
    return ready | Q(nb_tentatives__gte=6, derniere_tentative__lte=now - timedelta(seconds=320))


def recover_interrupted_access():
    from apps.integration.models import EdxAccessIntent, OutboxEvent

    recovered = 0
    with transaction.atomic():
        events = (
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(
                event_type="access.set",
                statut="processing",
                derniere_tentative__lt=timezone.now() - timedelta(minutes=10),
            )
            .order_by("derniere_tentative")[:100]
        )
        for event in events:
            try:
                intents = EdxAccessIntent.objects.filter(pk=event.aggregate_id)
                intent = intents.select_for_update(skip_locked=True).first()
            except (TypeError, ValueError):
                logger.error("Invalid access intent in interrupted event_id=%s", event.pk)
                event.statut = "dead"
                event.erreur = "Identifiant de décision d'accès invalide."
            else:
                if intent is None:
                    if intents.exists():
                        continue
                    logger.error("Missing access intent in interrupted event_id=%s", event.pk)
                    event.statut = "dead"
                    event.erreur = "La décision d'accès interrompue n'existe plus."
                else:
                    event.statut = "pending"
                    event.erreur = "Reprise de la même décision après interruption du traitement."
                    recovered += 1
                    logger.warning("Recovering interrupted access event_id=%s intent_id=%s", event.pk, intent.pk)
            event.save(update_fields=["statut", "erreur", "updated_at"])
    return recovered


def save_claimed_outbox_event(event):
    from apps.integration.models import OutboxEvent

    updated = OutboxEvent.objects.filter(
        pk=event.pk, statut="processing", derniere_tentative=event.derniere_tentative
    ).update(statut=event.statut, erreur=event.erreur, nb_tentatives=event.nb_tentatives, updated_at=timezone.now())
    if not updated:
        logger.warning("Ignoring result from superseded outbox claim event_id=%s", event.pk)
    return bool(updated)


def queue_access(user, course, *, kind, active, requested_at=None, only_if_revoked=False):
    from apps.integration.models import EdxAccessIntent, EdxCourseMapping, EdxUserMapping, OutboxEvent

    if kind not in ("enrollment", "teaching") or type(active) is not bool or (only_if_revoked and active):
        raise ValueError("Décision d'accès invalide.")
    explicit = requested_at is None
    requested_at = course_sync_requested_at(requested_at)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user.pk)
        course = EdxCourseMapping.objects.select_for_update().get(pk=course.pk)
        mapping = EdxUserMapping.objects.select_for_update().get(user_sis=user)
        intent = EdxAccessIntent.objects.select_for_update().filter(user=user, course=course, kind=kind).first()
        if intent and intent.mapping_id != mapping.pk:
            raise ValueError("L'identité LMS associée à la décision d'accès a changé.")
        if only_if_revoked and revocation_reason(user, course, mapping, kind) is None:
            logger.info(
                "Automatic withdrawal cancelled: eligibility restored user_id=%s course_id=%s", user.pk, course.pk
            )
            return intent, None
        if intent:
            if explicit:
                requested_at = max(requested_at, intent.requested_at + timedelta(microseconds=1))
            if requested_at < intent.requested_at:
                logger.info("Access request superseded intent_id=%s", intent.pk)
                return intent, None
            if requested_at == intent.requested_at and active != intent.is_active:
                raise ValueError("Une même version ne peut pas changer de décision d'accès.")
        else:
            intent = EdxAccessIntent(user=user, mapping=mapping, course=course, kind=kind)
        validate_grant(user, course, mapping, kind, active)
        intent.is_active = active
        intent.requested_at = requested_at
        intent.save()
        event, _ = OutboxEvent.objects.get_or_create(
            event_type="access.set",
            aggregate_type="access",
            aggregate_id=str(intent.pk),
            payload={"requested_at": requested_at.isoformat()},
            defaults={"statut": "pending"},
        )
    return intent, event


def apply_access(client, intent_id, requested_at):
    from apps.integration.models import EdxAccessIntent, EdxCourseMapping, EdxEnrollment, EdxUserMapping

    requested_at = course_sync_requested_at(requested_at)
    source = EdxAccessIntent.objects.get(pk=intent_id)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=source.user_id)
        course = EdxCourseMapping.objects.select_for_update().get(pk=source.course_id)
        intent = EdxAccessIntent.objects.select_for_update().get(pk=intent_id)
        if requested_at != intent.requested_at or intent.applied_requested_at == requested_at:
            logger.info("Access replay superseded or already confirmed intent_id=%s", intent.pk)
            return
        mapping = EdxUserMapping.objects.select_for_update().get(user_sis=user)
        if mapping.pk != intent.mapping_id:
            raise ValueError("L'identité LMS associée à la décision d'accès a changé.")
        validate_grant(user, course, mapping, intent.kind, intent.is_active)
        learner = None
        if intent.kind == "enrollment":
            model, field = learner_model()
            learner = model.objects.select_for_update().filter(user=user).first()
            if learner is None and intent.is_active:
                raise ValueError("Le dossier apprenant doit exister avant toute inscription LMS.")
        result = client.set_course_access(
            course.course_id,
            mapping.username_edx,
            kind=intent.kind,
            active=intent.is_active,
            requested_at=requested_at,
        )
        if intent.kind == "enrollment" and learner is not None:
            EdxEnrollment.objects.update_or_create(
                **{field: learner, "course": course},
                defaults={
                    "enrollment_id": result.get("id"),
                    "is_active": intent.is_active,
                    "last_sync": timezone.now(),
                    "date_desinscription": None if intent.is_active else timezone.now(),
                },
            )
        intent.applied_requested_at = requested_at
        intent.save(update_fields=["applied_requested_at"])


def dispatch_access(service, user, course, *, kind, active, requested_at=None):
    intent, event = queue_access(user, course, kind=kind, active=active, requested_at=requested_at)
    if event is None:
        return intent
    try:
        apply_access(service.client, intent.pk, event.payload["requested_at"])
    except Exception as error:
        event.erreur = str(error)
        if permanent_access_failure(error):
            event.statut = "dead"
        event.save(update_fields=["erreur", "statut"])
        logger.exception("LMS access dispatch failed intent_id=%s", intent.pk)
        raise
    event.statut = "done"
    event.save(update_fields=["statut"])
    return intent


def replay_access(service, event):
    apply_access(service.client, event.aggregate_id, event.payload["requested_at"])


def queue_revoked_access():
    from apps.integration.models import EdxAccessIntent, EdxEnrollment, EdxUserMapping

    model, field = learner_model()
    registration_model = apps.get_model(
        "eleves", "Inscription"
    ) if field == "eleve" else apps.get_model("etudiants", "InscriptionAdministrative")
    blocked_learners = model.objects.filter(
        Q(statut__in=REVOKED_LEARNER_STATUSES)
        | Q(pk__in=registration_model.objects.exclude(statut="validee").values(f"{field}_id"))
    ).values("user_id")
    revoked_users = EdxUserMapping.objects.filter(
        Q(actif=False) | Q(user_sis__is_active=False) | Q(user_sis_id__in=blocked_learners)
    ).values("user_sis_id")
    moved_intents = Q(pk__in=[])
    moved_enrollments = Q(pk__in=[])
    if field == "eleve":
        moved = registration_model.objects.filter(
            annee_scolaire_id=OuterRef("course__classe__annee_scolaire_id"),
        ).exclude(classe_id=OuterRef("course__classe_id"))
        moved_intents = Q(kind="enrollment") & Q(Exists(moved.filter(eleve__user_id=OuterRef("user_id"))))
        moved_enrollments = Q(Exists(moved.filter(eleve_id=OuterRef("eleve_id"))))
    intents = (
        EdxAccessIntent.objects.filter(is_active=True)
        .filter(
            Q(user_id__in=revoked_users)
            | Q(course__actif=False)
            | moved_intents
            | (Q(kind="teaching") & ~Q(user__role="enseignant"))
            | (Q(kind="enrollment") & ~Q(user_id__in=model.objects.values("user_id")))
        )
        .select_related("user", "course")
    )
    for intent in intents.iterator():
        queue_access(intent.user, intent.course, kind=intent.kind, active=False, only_if_revoked=True)
    # Historical enrollments also need a withdrawal intent after a revocation.
    enrollments = (
        EdxEnrollment.objects.filter(is_active=True)
        .filter(Q(**{f"{field}__user_id__in": revoked_users}) | Q(course__actif=False) | moved_enrollments)
        .select_related(f"{field}__user", "course")
    )
    for enrollment in enrollments.iterator():
        user = getattr(enrollment, field).user
        if not EdxAccessIntent.objects.filter(
            user=user, course=enrollment.course, kind="enrollment", is_active=False
        ).exists():
            queue_access(user, enrollment.course, kind="enrollment", active=False, only_if_revoked=True)
