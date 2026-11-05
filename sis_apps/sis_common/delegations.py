"""Explicit extra access, isolated from the learner's personal dossier and role."""

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import filter_queryset_by_scopes, has_business_permission
from sis_common.complaints import user_label
from sis_common.module_registry import require_module
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

MANAGE = "core.manage_accessdelegation"
LEARNERS = ("eleve", "etudiant", "doctorant")
Delegation = apps.get_model("core.AccessDelegation")


class ActiveTenantAccess(IsAuthenticated):
    def has_permission(self, request, view):
        return bool(
            super().has_permission(request, view)
            and request.user.is_active
            and getattr(request, "tenant", None)
            and request.user.etablissement_id == request.tenant.pk
        )


def manager_user(user, tenant):
    return (
        has_business_permission(user, MANAGE, context={"etablissement_id": tenant.pk})
        and user.is_active
        and user.etablissement_id == tenant.pk
        and (user.is_superuser or user.role not in LEARNERS)
    )


def can_manage(request):
    return manager_user(request.user, request.tenant)


def catalogue():
    if settings.SIS_VARIANT == "secondaire":
        return {"classes": ("Classes", "classes.Classe", {"classes": "pk", "annees": "annee_scolaire_id"})}
    return {
        "formations": ("Formations", "formations.Formation", {"formations": "pk", "departements": "departement_id"}),
        "stages": ("Conventions de stage", "stages.ConventionStage", {"stages": "pk", "etudiants": "etudiant_id"}),
    }


def resource_queryset(resource, tenant):
    if resource not in catalogue():
        raise ValidationError({"ressource": "Cette ressource n'est pas délégable."})
    _, model, _ = catalogue()[resource]
    queryset = apps.get_model(model).objects.all()
    if resource == "classes":
        return queryset.filter(etablissement=tenant).select_related("niveau")
    if resource == "stages":
        return queryset.filter(etudiant__universite=tenant).select_related("etudiant__user", "entreprise")
    # Formations without a department belong to the current tenant schema.
    return queryset.filter(
        Q(departement__faculte__universite=tenant)
        | Q(ecole_doctorale__universite=tenant)
        | Q(departement__isnull=True, ecole_doctorale__isnull=True)
    )


def grantable_queryset(user, tenant, resource):
    queryset = resource_queryset(resource, tenant)
    _, model, scopes = catalogue()[resource]
    app, name = model.lower().split(".")
    permission = f"{app}.view_{name}"
    if not user.has_perm(permission):
        raise PermissionDenied("Vous ne pouvez pas déléguer des données que vous ne pouvez pas consulter.")
    return filter_queryset_by_scopes(queryset, user, permission, scopes)


class DelegationSerializer(serializers.ModelSerializer):
    beneficiaire_nom = serializers.SerializerMethodField()
    responsable_nom = serializers.SerializerMethodField()
    statut = serializers.CharField(read_only=True)
    dossiers_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=100)

    class Meta:
        model = Delegation
        fields = [
            "id",
            "beneficiaire",
            "beneficiaire_nom",
            "responsable_nom",
            "ressource",
            "dossiers_ids",
            "debut",
            "fin",
            "motif",
            "statut",
            "revoque_le",
            "motif_revocation",
            "created_at",
        ]
        read_only_fields = ["id", "revoque_le", "motif_revocation", "created_at"]

    def get_beneficiaire_nom(self, obj):
        return user_label(obj.beneficiaire)

    def get_responsable_nom(self, obj):
        return user_label(obj.accorde_par)

    def validate(self, attrs):
        request = self.context["request"]
        beneficiary = attrs["beneficiaire"]
        if not (
            beneficiary.is_active
            and beneficiary.etablissement_id == request.tenant.pk
            and beneficiary.role in LEARNERS
            and not beneficiary.is_superuser
        ):
            raise ValidationError({"beneficiaire": "Choisissez un apprenant actif de cet établissement."})
        if attrs["fin"] <= attrs["debut"] or attrs["fin"] <= timezone.now():
            raise ValidationError({"fin": "La fin doit être future et postérieure au début."})
        ids = sorted(set(attrs["dossiers_ids"]))
        if grantable_queryset(request.user, request.tenant, attrs["ressource"]).filter(pk__in=ids).count() != len(ids):
            raise ValidationError({"dossiers_ids": "Un dossier est absent ou hors de vos autorisations."})
        attrs["dossiers_ids"] = ids
        return attrs


class DelegationViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [ActiveTenantAccess]
    serializer_class = DelegationSerializer
    filter_backends = [SearchFilter]
    search_fields = ["motif", "beneficiaire__first_name", "beneficiaire__last_name", "beneficiaire__username"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.tenant, "sis.delegations")

    def get_queryset(self):
        queryset = Delegation.objects.filter(etablissement=self.request.tenant).select_related(
            "beneficiaire", "accorde_par"
        )
        if not can_manage(self.request):
            queryset = queryset.filter(beneficiaire=self.request.user)
        resource = self.request.query_params.get("ressource")
        return queryset.filter(ressource=resource) if resource else queryset

    def require_manager(self):
        if not can_manage(self.request):
            raise PermissionDenied("La gestion des missions exige une habilitation explicite.")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        self.require_manager()
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        delegation = serializer.save(etablissement=self.request.tenant, accorde_par=self.request.user)
        record_workflow_event(
            self.request,
            delegation,
            "delegation_accordee",
            "Accès de mission accordé",
            message=delegation.motif,
            recipients=[delegation.beneficiaire],
        )

    @action(detail=False, methods=["get"])
    def catalogue(self, request):
        return Response([{"code": code, "label": values[0]} for code, values in catalogue().items()])

    @action(detail=False, methods=["get"])
    def beneficiaires(self, request):
        self.require_manager()
        queryset = (
            get_user_model()
            .objects.filter(etablissement=request.tenant, is_active=True, is_superuser=False, role__in=LEARNERS)
            .order_by("last_name", "first_name", "pk")
        )
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(
            [{"id": user.pk, "label": f"{user.get_full_name()} ({user.username})"} for user in page]
        )

    @action(detail=False, methods=["get"])
    def choix(self, request):
        self.require_manager()
        queryset = grantable_queryset(request.user, request.tenant, request.query_params.get("ressource")).order_by(
            "pk"
        )
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([{"id": obj.pk, "label": str(obj)} for obj in page])

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def revoquer(self, request, pk=None):
        self.require_manager()
        delegation = get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
        motif = serializers.CharField(trim_whitespace=True).run_validation(request.data.get("motif"))
        if delegation.revoque_le:
            raise ValidationError("Cette mission est déjà révoquée.")
        delegation.revoque_le = timezone.now()
        delegation.revoque_par = request.user
        delegation.motif_revocation = motif
        delegation.save(update_fields=["revoque_le", "revoque_par", "motif_revocation"])
        record_workflow_event(
            request,
            delegation,
            "delegation_revoquee",
            "Accès de mission révoqué",
            message=motif,
            recipients=[delegation.beneficiaire],
        )
        return Response(self.get_serializer(delegation).data)

    @action(detail=True, methods=["get"])
    def dossiers(self, request, pk=None):
        delegation = self.get_object()
        if delegation.statut != "active":
            raise PermissionDenied("Cette mission n'est pas active.")
        if not manager_user(delegation.accorde_par, request.tenant):
            raise PermissionDenied("Le responsable n'est plus habilité à accorder cette mission.")
        queryset = grantable_queryset(delegation.accorde_par, request.tenant, delegation.ressource).filter(
            pk__in=delegation.dossiers_ids
        )
        page = self.paginate_queryset(queryset.order_by("pk"))
        record_workflow_event(request, delegation, "consultation_mission", "Dossiers de mission consultés")
        return self.get_paginated_response(
            [
                {
                    "id": obj.pk,
                    "label": str(obj),
                    "statut": getattr(obj, "statut", ""),
                    "date_fin": getattr(obj, "date_fin", None),
                }
                for obj in page
            ]
        )

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        from apps.core.serializers import WorkflowEventSerializer

        return Response(WorkflowEventSerializer(workflow_history_queryset(self.get_object()), many=True).data)
