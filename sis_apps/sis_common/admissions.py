"""Admissions decisions and year-to-year transitions that preserve prior records."""

from django.apps import apps
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from sis_common.academic_lifecycle import ensure_academic_open
from sis_common.authorization import filter_queryset_by_scopes, has_business_permission
from sis_common.delegations import ActiveTenantAccess
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset


def admission_fields(model):
    if model._meta.app_label == "eleves":
        return "eleve", "annee_scolaire", "classe", "en_cours", "motif"
    return "etudiant", "annee_universitaire", "formation", "provisoire", "motif_refus"


def admission_scope_fields(model):
    learner, year, target, _, _ = admission_fields(model)
    return {f"{learner}s": f"{learner}_id", "annees": f"{year}_id", f"{target}s": f"{target}_id"}


class AdmissionTenantAccess(ActiveTenantAccess):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and (
            request.method in ("GET", "HEAD", "OPTIONS")
            or request.user.is_superuser
            or request.user.role not in ("eleve", "etudiant", "doctorant", "parent")
        )


class AdmissionSerializerMixin:
    def validate(self, attrs):
        attrs = super().validate(attrs)
        learner, year, target, pending, _ = admission_fields(self.Meta.model)
        expected = self.instance.statut if self.instance else pending
        if attrs.get("statut", expected) != expected:
            raise serializers.ValidationError({"statut": "Utilisez les actions de décision d'admission."})
        request = self.context.get("request")
        if request and not request.user.is_superuser:
            permission = f"{self.Meta.model._meta.app_label}.change_{self.Meta.model._meta.model_name}"
            scopes = (request.user.attributs_acces or {}).get("permission_scopes", {}).get(permission)
            if scopes:
                context = {
                    name: getattr(attrs.get(field, getattr(self.instance, field, None)), "pk", None)
                    for name, field in ((f"{learner}s", learner), ("annees", year), (f"{target}s", target))
                }
                if not has_business_permission(request.user, permission, context):
                    raise PermissionDenied("La destination de l'admission est hors de votre périmètre.")
        return attrs


def scoped_admissions(queryset, request):
    prefix = "view" if request.method in ("GET", "HEAD", "OPTIONS") else "change"
    model = queryset.model
    permission = f"{model._meta.app_label}.{prefix}_{model._meta.model_name}"
    return filter_queryset_by_scopes(queryset, request.user, permission, admission_scope_fields(model))


class ReenrollmentMixin:
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reinscrire(self, request, pk=None):
        source = self.get_object()
        learner_field, year_field, target_field, pending, _ = admission_fields(type(source))
        if source.statut != "validee":
            raise serializers.ValidationError("La réinscription exige une inscription d'origine validée.")
        motif = serializers.CharField(trim_whitespace=True, max_length=2000).run_validation(request.data.get("motif"))
        learner = getattr(source, learner_field)
        type(learner).objects.select_for_update().get(pk=learner.pk)
        fields = [year_field, target_field, "date_inscription"]
        if target_field == "formation":
            fields += ["parcours", "regime"]
        data = {field: request.data[field] for field in fields if field in request.data}
        data[learner_field] = learner.pk
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        destination_year = serializer.validated_data[year_field]
        if destination_year.date_debut <= getattr(source, year_field).date_fin:
            raise serializers.ValidationError({year_field: "Choisissez une année postérieure, sans chevauchement."})
        if type(source).objects.filter(
            **{
                f"{learner_field}_id": learner.pk,
                f"{year_field}__date_debut__gt": getattr(source, year_field).date_debut,
                "statut__in": (pending, "validee"),
            }
        ).exists():
            raise serializers.ValidationError(
                {year_field: "Une inscription ultérieure est déjà en cours ou validée pour cet apprenant."}
            )
        destination = self.save_academic(serializer)
        record_workflow_event(
            request,
            destination,
            "reinscription",
            "Nouvelle inscription à examiner",
            message=motif,
            recipients=[learner.user],
            metadata={"origine_id": source.pk, "annee_origine_id": getattr(source, f"{year_field}_id")},
        )
        record_workflow_event(
            request,
            source,
            "reinscription_initiee",
            "Inscription vers une nouvelle année",
            message=motif,
            metadata={"destination_id": destination.pk, "annee_destination_id": destination_year.pk},
        )
        return Response(self.get_serializer(destination).data, status=201)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def annuler(self, request, pk=None):
        return self.pending_decision(request, "annulee")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def refuser(self, request, pk=None):
        return self.pending_decision(request, "refusee")

    def pending_decision(self, request, decision):
        enrollment = self.get_object()
        learner, _, _, pending, reason_field = admission_fields(type(enrollment))
        ensure_academic_open(enrollment, paths=self.academic_period_paths)
        if enrollment.statut != pending:
            raise serializers.ValidationError("Seule une demande d'admission en attente peut être refusée ou annulée.")
        motif = serializers.CharField(trim_whitespace=True, max_length=2000).run_validation(request.data.get("motif"))
        enrollment.statut = decision
        setattr(enrollment, reason_field, motif)
        fields = ["statut", reason_field] + (["updated_at"] if hasattr(enrollment, "updated_at") else [])
        enrollment.save(update_fields=fields)
        record_workflow_event(
            request,
            enrollment,
            "admission_decision",
            enrollment.get_statut_display(),
            message=motif,
            recipients=[getattr(enrollment, learner).user],
        )
        return Response({"detail": "Décision enregistrée.", "id": enrollment.pk})

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        from apps.core.serializers import WorkflowEventSerializer

        return Response(WorkflowEventSerializer(workflow_history_queryset(self.get_object()), many=True).data)


def activate_school_enrollment(enrollment):
    learner = apps.get_model("eleves.Eleve").objects.select_for_update().get(pk=enrollment.eleve_id)
    year = enrollment.annee_scolaire
    current_year = learner.classe_actuelle.annee_scolaire if learner.classe_actuelle_id else None
    if year.date_debut <= timezone.localdate() <= year.date_fin and (
        current_year is None or current_year.date_debut <= year.date_debut
    ):
        learner.classe_actuelle = enrollment.classe
        learner.save(update_fields=["classe_actuelle", "updated_at"])
