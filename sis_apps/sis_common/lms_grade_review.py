"""Persist LMS proposals and require a named reviewer before creating a SIS grade."""

from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.academic_lifecycle import ensure_academic_open
from sis_common.authorization import is_current_tenant_user, request_has_business_access
from sis_common.grade_entry import ensure_numeric_import, validate_offering_grade
from sis_common.workflow_tracking import record_workflow_event


class GradeProposalConflict(APIException):
    status_code = 409
    default_detail = "Cette proposition ne peut plus être validée."


def evaluation_academic_context(evaluation):
    context = {"date": evaluation.date.isoformat()}
    if hasattr(evaluation, "periode_id"):
        context.update(
            period=evaluation.periode_id,
            year=evaluation.periode.annee_scolaire_id,
            school_class=evaluation.classe_id,
            class_year=evaluation.classe.annee_scolaire_id,
            subject=evaluation.matiere_id,
        )
    else:
        context.update(
            semester=evaluation.semestre_id,
            year=evaluation.semestre.annee_universitaire_id,
            subject=evaluation.ecue_id,
            curriculum=evaluation.ecue.ue.maquette_id,
            curriculum_year=evaluation.ecue.ue.maquette.annee_universitaire_id,
        )
    return context


def stage_lms_grade(grade_log, evaluation):
    evaluation = type(evaluation).objects.select_for_update().get(pk=evaluation.pk)
    score = Decimal(str(grade_log.score))
    maximum = Decimal(str(grade_log.max_score))
    if not score.is_finite() or not maximum.is_finite() or maximum <= 0 or not 0 <= score <= maximum:
        raise ValueError("LMS grade must be finite and between zero and max_score")
    grade_log.proposed_evaluation = evaluation
    grade_log.proposed_scale = evaluation.bareme
    grade_log.proposed_academic_context = evaluation_academic_context(evaluation)
    grade_log.proposed_value = (score * evaluation.bareme / maximum).quantize(Decimal("0.01"))
    grade_log.review_status = "pending"
    grade_log.save(
        update_fields=[
            "proposed_evaluation",
            "proposed_scale",
            "proposed_academic_context",
            "proposed_value",
            "review_status",
        ]
    )


class GradeProposalDecisionSerializer(serializers.Serializer):
    proposal_id = serializers.IntegerField(min_value=1)
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        if attrs["decision"] == "reject" and not attrs.get("reason"):
            raise serializers.ValidationError({"reason": "Le motif du refus est obligatoire."})
        return attrs


class LMSGradeReviewMixin:
    def _lms_review_evaluation(self, request, permission):
        if not request.user.is_active or not is_current_tenant_user(request):
            raise PermissionDenied("Compte hors de cet établissement.")
        evaluation = self.get_object()
        if request.method == "POST":
            # A reassignment may have committed while get_object waited for its row lock.
            evaluation = get_object_or_404(self.get_queryset(), pk=evaluation.pk)
        context = self.lms_grade_context(evaluation)
        if not self.lms_evaluation_is_local(evaluation, request.tenant):
            raise PermissionDenied("Évaluation hors de cet établissement.")
        if not request_has_business_access(request, permission, self.lms_grade_roles, context=context):
            raise PermissionDenied("La permission de gestion des notes est requise.")
        return evaluation

    def _lms_proposals(self, evaluation):
        learner = self.lms_learner_field
        return (
            apps.get_model("integration.EdxGradeLog")
            .objects.select_related("enrollment")
            .filter(
                proposed_evaluation=evaluation,
                **{
                    f"enrollment__{learner}__{self.lms_learner_owner_field}": self.request.tenant,
                    f"enrollment__{learner}__user__etablissement": self.request.tenant,
                },
            )
        )

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def propositions_lms(self, request, pk=None):
        evaluation = self._lms_review_evaluation(request, "notes.view_note")
        proposals = self._lms_proposals(evaluation).order_by("-timestamp_lms", "-pk")
        page = self.paginate_queryset(proposals)
        rows = [
            {
                "id": item.pk,
                "learner_id": getattr(item.enrollment, f"{self.lms_learner_field}_id"),
                "event_id": item.event_id,
                "score": item.score,
                "max_score": item.max_score,
                "proposed_value": item.proposed_value,
                "proposed_scale": item.proposed_scale,
                "review_status": item.review_status,
                "reviewed_by": item.reviewed_by_id,
                "reviewed_at": item.reviewed_at,
                "review_reason": item.review_reason,
                "note_id": item.note_sis_id,
                "timestamp_lms": item.timestamp_lms,
            }
            for item in page
        ]
        return self.get_paginated_response(rows)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    @transaction.atomic
    def examiner_proposition_lms(self, request, pk=None):
        evaluation = self._lms_review_evaluation(request, "notes.change_note")
        data = GradeProposalDecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        decision = data.validated_data["decision"]
        proposal = get_object_or_404(
            self._lms_proposals(evaluation).select_for_update(),
            pk=data.validated_data["proposal_id"],
        )
        if proposal.review_status != "pending":
            raise GradeProposalConflict("Cette proposition a déjà été traitée.")

        note = None
        if decision == "approve":
            ensure_academic_open(evaluation, paths=self.academic_period_paths)
            self.ensure_lms_grade_entry(evaluation)
            ensure_numeric_import(evaluation)
            validate_offering_grade(evaluation, proposal.proposed_value, {}, "presente")
            self._validate_lms_proposal(proposal, evaluation)
            learner_id = getattr(proposal.enrollment, f"{self.lms_learner_field}_id")
            if not self.eligible_lms_learners(evaluation).filter(pk=learner_id).exists():
                raise GradeProposalConflict("L'apprenant n'est plus inscrit à cette évaluation.")
            Note = apps.get_model("notes.Note")
            key = {"evaluation": evaluation, f"{self.lms_learner_field}_id": learner_id}
            if Note.objects.filter(**key).exists():
                raise GradeProposalConflict("Une note SIS existe déjà. Utilisez le circuit de rectification.")
            try:
                with transaction.atomic():
                    note = Note.objects.create(
                        **key,
                        valeur=proposal.proposed_value,
                        statut="presente",
                        saisi_par=self.lms_grade_author(request),
                    )
            except IntegrityError:
                if Note.objects.filter(**key).exists():
                    raise GradeProposalConflict("Une note SIS a été enregistrée simultanément.") from None
                raise

        proposal.review_status = "approved" if note else "rejected"
        proposal.reviewed_by = request.user
        proposal.reviewed_at = timezone.now()
        proposal.review_reason = data.validated_data.get("reason", "")
        proposal.note_sis = note
        proposal.imported_to_sis = note is not None
        proposal.save(
            update_fields=[
                "review_status",
                "reviewed_by",
                "reviewed_at",
                "review_reason",
                "note_sis",
                "imported_to_sis",
            ]
        )
        record_workflow_event(
            request,
            evaluation,
            "lms_grade_review",
            "Proposition LMS examinée",
            metadata={"proposal_id": proposal.pk, "decision": decision, "note_id": note.pk if note else None},
        )
        return Response({"id": proposal.pk, "review_status": proposal.review_status, "note_id": proposal.note_sis_id})

    def _validate_lms_proposal(self, proposal, evaluation):
        enrollment = proposal.enrollment
        learner = getattr(enrollment, self.lms_learner_field)
        Assessment = apps.get_model("integration.EdxAssessmentMapping")
        UserMapping = apps.get_model("integration.EdxUserMapping")
        assessment = Assessment.objects.filter(
            course=enrollment.course, subsection_id=proposal.subsection_id, evaluation=evaluation, actif=True
        ).first()
        if (
            not learner.user.is_active
            or not enrollment.is_active
            or not enrollment.course.actif
            or not UserMapping.objects.filter(user_sis=learner.user, actif=True).exists()
            or assessment is None
        ):
            raise GradeProposalConflict("L'accès LMS ou le rattachement de l'évaluation a été révoqué.")
        try:
            assessment.clean()
        except ModelValidationError as error:
            raise GradeProposalConflict("Le cours LMS ne correspond plus à cette évaluation.") from error
        if evaluation.bareme != proposal.proposed_scale:
            raise GradeProposalConflict("Le barème a changé depuis la réception de cette proposition.")
        if evaluation_academic_context(evaluation) != proposal.proposed_academic_context:
            raise GradeProposalConflict("Le rattachement académique a changé depuis la réception de cette proposition.")
        newer = (
            type(proposal)
            .objects.filter(enrollment=enrollment, subsection_id=proposal.subsection_id)
            .filter(
                Q(timestamp_lms__gt=proposal.timestamp_lms)
                | Q(timestamp_lms=proposal.timestamp_lms, pk__gt=proposal.pk)
            )
        )
        if newer.exists():
            raise GradeProposalConflict("Une proposition LMS plus récente doit être examinée.")
