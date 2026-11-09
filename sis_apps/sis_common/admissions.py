"""Admissions decisions and year-to-year transitions that preserve prior records."""

from collections.abc import Mapping

from django.apps import apps
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from sis_common.academic_lifecycle import ensure_academic_open
from sis_common.authorization import filter_queryset_by_scopes, has_business_permission
from sis_common.delegations import ActiveTenantAccess, resource_queryset
from sis_common.enrollment_states import transition_status, validate_enrollment_dates
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset


def admission_fields(model):
    if model._meta.app_label == "eleves":
        return "eleve", "annee_scolaire", "classe", "en_cours", "motif"
    return "etudiant", "annee_universitaire", "formation", "provisoire", "motif_refus"


def admission_scope_fields(model):
    learner, year, target, _, _ = admission_fields(model)
    return {f"{learner}s": f"{learner}_id", "annees": f"{year}_id", f"{target}s": f"{target}_id"}


def ensure_enrollment_dates(enrollment, *, ongoing=False):
    year = getattr(enrollment, "annee_scolaire", None) or enrollment.annee_universitaire
    try:
        validate_enrollment_dates(year.date_debut, year.date_fin, timezone.localdate(), ongoing=ongoing)
    except ValueError as error:
        raise serializers.ValidationError({"calendrier": str(error)}) from error


def ensure_school_capacity(classe, learner):
    occupants = (
        type(learner)
        .objects.filter(Q(classe_actuelle=classe) | Q(inscriptions__classe=classe, inscriptions__statut="validee"))
        .exclude(pk=learner.pk)
        .distinct()
        .count()
    )
    if occupants >= classe.effectif_max:
        raise serializers.ValidationError({"classe": "La classe a atteint sa capacité."})


def ensure_active_enrollment(enrollment):
    if enrollment.statut != "validee":
        raise serializers.ValidationError({"inscription": "Une inscription annuelle validée et active est requise."})
    ensure_enrollment_dates(enrollment)


def validate_learner_lifecycle(instance, attrs):
    status = attrs.get("statut", instance.statut)
    if status != instance.statut and (status in ("suspendu", "abandon") or instance.statut in ("suspendu", "abandon")):
        raise serializers.ValidationError({"statut": "Utilisez les actions motivées de l'inscription annuelle."})


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
        if self.instance and expected != pending and not self.context.get("controlled_transfer"):
            if any(value != getattr(self.instance, field) for field, value in attrs.items()):
                raise serializers.ValidationError(
                    {"detail": "Ce dossier a déjà fait l'objet d'une décision. Utilisez une action motivée."}
                )
        destination_year = attrs.get(year, getattr(self.instance, year, None))
        if destination_year:
            try:
                validate_enrollment_dates(destination_year.date_debut, destination_year.date_fin, timezone.localdate())
            except ValueError as error:
                raise serializers.ValidationError({year: str(error)}) from error
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
    def get_object(self):
        if connection.in_atomic_block and self.request.method not in ("GET", "HEAD", "OPTIONS"):
            queryset = self.filter_queryset(self.get_queryset())
            lookup = self.lookup_url_kwarg or self.lookup_field
            enrollment = get_object_or_404(queryset, **{self.lookup_field: self.kwargs[lookup]})
            self.check_object_permissions(self.request, enrollment)
            learner_field, _, _, _, _ = admission_fields(type(enrollment))
            learner_model = enrollment._meta.get_field(learner_field).remote_field.model
            # Match pupil transfers and new admissions: learner before enrollment/class.
            learner_model.objects.select_for_update().get(pk=getattr(enrollment, f"{learner_field}_id"))
        return super().get_object()

    def save_academic(self, serializer, **kwargs):
        if serializer.instance is None:
            model = serializer.Meta.model
            learner_field, year_field, _, _, _ = admission_fields(model)
            learner = serializer.validated_data[learner_field]
            type(learner).objects.select_for_update().get(pk=learner.pk)
            if model.objects.filter(
                **{
                    learner_field: learner,
                    year_field: serializer.validated_data[year_field],
                }
            ).exists():
                raise serializers.ValidationError(
                    {"detail": "Une inscription existe déjà pour cet apprenant et cette année."}
                )
        return super().save_academic(serializer, **kwargs)

    def perform_destroy(self, instance):
        raise serializers.ValidationError(
            {"detail": "Conservez l'historique : annulez la demande ou enregistrez un abandon."}
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def suspendre(self, request, pk=None):
        return self.enrollment_transition(request, "suspendre")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def abandonner(self, request, pk=None):
        return self.enrollment_transition(request, "abandonner")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reprendre(self, request, pk=None):
        return self.enrollment_transition(request, "reprendre")

    def enrollment_transition(self, request, operation):
        enrollment = self.get_object()
        if not isinstance(request.data, Mapping) or set(request.data) - {"motif"}:
            raise serializers.ValidationError({"detail": "Seul le motif de cette transition est attendu."})
        motif = serializers.CharField(trim_whitespace=True, max_length=2000).run_validation(request.data.get("motif"))
        try:
            destination = transition_status(enrollment.statut, operation)
        except ValueError as error:
            raise serializers.ValidationError({"statut": str(error)}) from error
        ensure_academic_open(enrollment, paths=self.academic_period_paths)
        ensure_enrollment_dates(enrollment, ongoing=True)
        learner_field, year_field, _, _, _ = admission_fields(type(enrollment))
        learner = getattr(enrollment, learner_field)
        learner = type(learner).objects.select_for_update().get(pk=learner.pk)
        if learner.statut in ("sortant", "transfere", "transfert", "diplome", "abandon"):
            raise serializers.ValidationError(
                {"statut": "Ce dossier apprenant est sorti du parcours. Une nouvelle inscription est nécessaire."}
            )
        year = getattr(enrollment, year_field)
        if (
            type(enrollment)
            .objects.filter(
                **{
                    learner_field: learner,
                    f"{year_field}__date_debut__gt": year.date_debut,
                    f"{year_field}__date_debut__lte": timezone.localdate(),
                    "statut__in": ("validee", "suspendue", "abandonnee"),
                }
            )
            .exists()
        ):
            raise serializers.ValidationError({"detail": "Un parcours plus récent a déjà commencé."})
        school = learner_field == "eleve"
        if school:
            if learner.classe_actuelle_id not in (None, enrollment.classe_id):
                raise serializers.ValidationError(
                    {"detail": "La classe actuelle ne correspond plus à cette inscription."}
                )
            classe = type(enrollment.classe).objects.select_for_update().get(pk=enrollment.classe_id)
            if operation == "reprendre":
                ensure_school_capacity(classe, learner)
        elif (
            learner.annee_universitaire_actuelle_id
            and learner.annee_universitaire_actuelle.date_debut > year.date_debut
            and learner.annee_universitaire_actuelle.date_debut <= timezone.localdate()
        ):
            raise serializers.ValidationError({"detail": "L'étudiant a déjà commencé une année ultérieure."})

        previous = enrollment.statut
        if previous == "validee":
            enrollment.statut_apprenant_avant_interruption = learner.statut
        enrollment.statut = destination
        fields = ["statut", "statut_apprenant_avant_interruption"]
        if hasattr(enrollment, "updated_at"):
            fields.append("updated_at")
        enrollment.save(update_fields=fields)
        if operation == "reprendre":
            restored = enrollment.statut_apprenant_avant_interruption
            learner.statut = restored if restored in ("inscrit", "redoublant") else "inscrit"
        else:
            learner.statut = "suspendu" if operation == "suspendre" else "abandon"
        fields = ["statut", "updated_at"]
        if school:
            learner.classe_actuelle = classe if operation == "reprendre" else None
            fields.append("classe_actuelle")
        else:
            learner.annee_universitaire_actuelle = year
            fields.append("annee_universitaire_actuelle")
        learner.save(update_fields=fields)
        titles = {
            "suspendre": "Inscription suspendue",
            "abandonner": "Abandon enregistré",
            "reprendre": "Reprise validée",
        }
        record_workflow_event(
            request,
            enrollment,
            operation,
            titles[operation],
            message=motif,
            recipients=[learner.user],
            metadata={"statut_avant": previous, "statut_apres": destination, "annee_id": year.pk},
        )
        return Response(self.get_serializer(enrollment).data)

    def first_admission_learner(self, *, lock=False):
        request = self.request
        model = self.serializer_class.Meta.model
        learner_field, _, _, _, _ = admission_fields(model)
        roles = ("eleve",) if learner_field == "eleve" else ("etudiant", "doctorant")
        if request.user.role not in roles or request.user.is_superuser:
            raise PermissionDenied("Seul un apprenant peut déposer sa première demande d'admission.")
        learner_model = model._meta.get_field(learner_field).remote_field.model
        owner_field = "etablissement" if learner_field == "eleve" else "universite"
        queryset = learner_model.objects.filter(user=request.user, **{owner_field: request.tenant})
        learner = (queryset.select_for_update() if lock else queryset).first()
        if learner is None:
            raise PermissionDenied("Aucun profil d'apprenant ne vous est attribué dans cet établissement.")
        if model.objects.filter(**{learner_field: learner}).exists():
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Un dossier existe déjà pour cet apprenant. "
                        "Adressez-vous à la scolarité pour une réinscription."
                    )
                }
            )
        return learner

    @action(detail=False, methods=["get"], permission_classes=[ActiveTenantAccess])
    def catalogue(self, request):
        self.first_admission_learner()
        model = self.serializer_class.Meta.model
        learner_field, year_field, _, _, _ = admission_fields(model)
        school = learner_field == "eleve"
        owner_field = "etablissement" if school else "universite"
        years = (
            model._meta.get_field(year_field)
            .remote_field.model.objects.filter(
                **{owner_field: request.tenant}, cloturee=False, date_fin__gte=timezone.localdate()
            )
            .order_by("date_debut", "pk")
        )
        targets = resource_queryset("classes" if school else "formations", request.tenant)
        if school:
            targets = targets.filter(annee_scolaire__in=years)
            choices = list(targets.order_by("nom", "pk").values("id", "nom", "annee_scolaire"))
            paths = []
        else:
            targets = targets.filter(actif=True)
            choices = list(targets.order_by("nom", "pk").values("id", "nom"))
            paths = list(
                apps.get_model("formations.Parcours")
                .objects.filter(formation__in=targets)
                .order_by("nom", "pk")
                .values("id", "nom", "formation")
            )
        return Response(
            {"years": list(years.values("id", "libelle")), "targets": choices, "paths": paths},
            headers={"Cache-Control": "private, no-store"},
        )

    @action(detail=False, methods=["post"], permission_classes=[ActiveTenantAccess])
    @transaction.atomic
    def deposer(self, request):
        model = self.serializer_class.Meta.model
        learner_field, year_field, target_field, _, _ = admission_fields(model)
        learner = self.first_admission_learner(lock=True)
        if not isinstance(request.data, Mapping):
            raise serializers.ValidationError({"detail": "Un dossier d'admission est attendu."})
        allowed = {year_field, target_field, "motif"}
        if target_field == "formation":
            allowed.add("parcours")
        if set(request.data) - allowed:
            raise serializers.ValidationError({"detail": "Ce dossier contient des champs non autorisés."})
        motif = serializers.CharField(allow_blank=True, max_length=2000).run_validation(request.data.get("motif", ""))
        data = {
            learner_field: learner.pk,
            year_field: request.data.get(year_field),
            target_field: request.data.get(target_field),
            "date_inscription": timezone.localdate(),
        }
        if learner_field == "eleve":
            data["motif"] = motif
        else:
            data["regime"] = learner.regime
            if "parcours" in request.data:
                data["parcours"] = request.data["parcours"]
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        enrollment = self.save_academic(serializer)
        record_workflow_event(
            request,
            enrollment,
            "admission_deposee",
            "Demande d'admission déposée",
            message=motif,
            recipients=[request.user],
        )
        return Response(self.get_serializer(enrollment).data, status=201)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reinscrire(self, request, pk=None):
        source = self.get_object()
        learner_field, year_field, target_field, pending, _ = admission_fields(type(source))
        if source.statut not in ("validee", "suspendue", "abandonnee"):
            raise serializers.ValidationError("La réinscription exige un parcours précédemment validé.")
        if not isinstance(request.data, Mapping):
            raise serializers.ValidationError({"detail": "Un dossier de réinscription est attendu."})
        motif = serializers.CharField(trim_whitespace=True, max_length=2000).run_validation(request.data.get("motif"))
        learner = getattr(source, learner_field)
        type(learner).objects.select_for_update().get(pk=learner.pk)
        fields = [year_field, target_field, "date_inscription"]
        if target_field == "formation":
            fields += ["parcours", "regime"]
        if set(request.data) - {*fields, "motif"}:
            raise serializers.ValidationError({"detail": "Ce dossier contient des champs non autorisés."})
        data = {field: request.data[field] for field in fields if field in request.data}
        if target_field == "formation":
            data.setdefault("regime", source.regime)
        data[learner_field] = learner.pk
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        destination_year = serializer.validated_data[year_field]
        if destination_year.date_debut <= getattr(source, year_field).date_fin:
            raise serializers.ValidationError({year_field: "Choisissez une année postérieure, sans chevauchement."})
        if (
            type(source)
            .objects.filter(
                **{
                    f"{learner_field}_id": learner.pk,
                    f"{year_field}__date_debut__gt": getattr(source, year_field).date_debut,
                    "statut__in": (pending, "validee", "suspendue", "abandonnee"),
                }
            )
            .exists()
        ):
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
        if not isinstance(request.data, Mapping):
            raise serializers.ValidationError({"detail": "Un motif de décision est attendu."})
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
        if learner.statut in ("suspendu", "abandon"):
            learner.statut = "inscrit"
        learner.save(update_fields=["classe_actuelle", "statut", "updated_at"])
