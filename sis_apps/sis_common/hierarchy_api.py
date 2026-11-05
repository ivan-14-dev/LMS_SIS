"""Publication and simulation of tenant configuration; no arbitrary user code."""

from copy import copy

from django.apps import apps
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from sis_common.hierarchy import SETTING_SCHEMA, latest_revision, resolve_configuration, unit_path, validate_settings
from sis_common.hierarchy_attachments import (
    configuration_admin,
    readable_targets,
    target_detail,
    target_registry,
    target_summary,
)
from sis_common.module_configuration import StaleModuleConfiguration
from sis_common.pagination import SISPagination
from sis_common.workflow_tracking import record_workflow_event

Unit = apps.get_model("core.OrganizationUnit")
Revision = apps.get_model("core.ConfigurationRevision")


def checked_tenant(request):
    tenant = getattr(request, "tenant", None)
    if tenant is None or not request.user.is_active or request.user.etablissement_id != tenant.pk:
        raise PermissionDenied("Cette configuration est réservée à votre établissement.")
    return tenant


class UnitSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="__str__", read_only=True)
    parent_label = serializers.StringRelatedField(source="parent", read_only=True)
    kind_label = serializers.SerializerMethodField()
    topology_label = serializers.CharField(source="get_topology_version_display", read_only=True)

    def get_kind_label(self, instance):
        return instance.category_label or instance.get_kind_display()

    class Meta:
        model = Unit
        fields = [
            "id", "code", "nom", "kind", "kind_label", "category_label", "topology_version", "topology_label",
            "parent", "label", "parent_label",
        ]

    def validate(self, attrs):
        tenant = checked_tenant(self.context["request"])
        if self.instance:
            for field in ("code", "kind", "parent", "topology_version"):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise ValidationError({field: "Le rattachement et le code sont figés pour conserver l'historique."})
        parent = attrs.get("parent")
        if parent:
            unit_path(tenant, parent)
        proposed = copy(self.instance) if self.instance else Unit(etablissement=tenant)
        for field, value in attrs.items():
            setattr(proposed, field, value)
        try:
            proposed.clean()
        except ModelValidationError as error:
            raise ValidationError(error.message_dict if hasattr(error, "message_dict") else error.messages) from error
        code = attrs.get("code", self.instance.code if self.instance else "")
        duplicates = Unit.objects.filter(etablissement_id=tenant.pk, code=code)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError({"code": "Ce code existe déjà dans cet établissement."})
        return attrs


class AttachmentInput(serializers.Serializer):
        kind = serializers.ChoiceField(choices=tuple(target_registry()))
        object_id = serializers.IntegerField(min_value=1)
        confirm = serializers.BooleanField()

        def to_internal_value(self, data):
            if not isinstance(data, dict) or set(data) - set(self.fields):
                raise ValidationError({"detail": "Seuls le type, l’objet et la confirmation sont acceptés."})
            return super().to_internal_value(data)

        def validate_confirm(self, value):
            if not value:
                raise ValidationError("Confirmez le rattachement sans modification des droits ni des règles historisées.")
            return value


class OrganizationUnitsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = UnitSerializer
    pagination_class = SISPagination
    filter_backends = [SearchFilter]
    search_fields = ["code", "nom", "category_label"]

    def get_queryset(self):
        return Unit.objects.filter(etablissement_id=checked_tenant(self.request).pk).select_related("parent")

    @transaction.atomic
    def perform_create(self, serializer):
        tenant = checked_tenant(self.request)
        type(tenant).objects.select_for_update().get(pk=tenant.pk)
        if Unit.objects.filter(etablissement_id=tenant.pk, code=serializer.validated_data["code"]).exists():
            raise ValidationError({"code": "Ce code existe déjà dans cet établissement."})
        item = serializer.save(etablissement=tenant)
        record_workflow_event(self.request, item, "creation", "Unité organisationnelle créée")

    @transaction.atomic
    def perform_update(self, serializer):
        item = serializer.save()
        record_workflow_event(self.request, item, "modification", "Unité organisationnelle renommée")

    def attachment_admin(self):
        tenant = checked_tenant(self.request)
        if not configuration_admin(self.request.user):
            raise PermissionDenied("Les rattachements sont réservés aux administrateurs de l’établissement.")
        return tenant

    @action(detail=False, methods=["get"])
    def catalogue(self, request):
        self.attachment_admin()
        return Response({
            "kinds": [{"value": value, "label": label} for value, label in Unit.KINDS],
            "targets": [
                {"kind": kind, "label": target.label, "category": target.category}
                for kind, target in target_registry().items()
            ],
        })

    @action(detail=False, methods=["get"])
    def references(self, request):
        self.attachment_admin()
        kind = request.query_params.get("kind")
        target, queryset, _native = readable_targets(kind, request)
        search = request.query_params.get("search", "").strip()
        if len(search) > 200:
            raise ValidationError({"search": "Recherche limitée à 200 caractères."})
        if search:
            condition = Q()
            for field in target.search:
                condition |= Q(**{f"{field}__icontains": search})
            queryset = queryset.filter(condition)
        page = self.paginate_queryset(queryset.order_by("pk"))
        return self.get_paginated_response([target_summary(kind, target, item) for item in page])

    @action(detail=True, methods=["get", "post"])
    def attachments(self, request, pk=None):
        tenant = self.attachment_admin()
        unit = self.get_object()
        unit_path(tenant, unit)
        if request.method == "GET":
            kind = request.query_params.get("kind")
            target, queryset, _native = readable_targets(kind, request)
            if target.direct:
                queryset = queryset.filter(organisation_unit=unit)
            else:
                ids = apps.get_model("core.OrganizationAttachment").objects.filter(unit=unit).values(f"{kind}_id")
                queryset = queryset.filter(pk__in=ids)
            page = self.paginate_queryset(queryset.order_by("pk"))
            return self.get_paginated_response([target_summary(kind, target, item) for item in page])
        payload = AttachmentInput(data=request.data)
        payload.is_valid(raise_exception=True)
        kind = payload.validated_data["kind"]
        with transaction.atomic():
            type(tenant).objects.select_for_update().get(pk=tenant.pk)
            target, queryset, native = readable_targets(kind, request)
            # A simple row lock avoids SELECT FOR UPDATE on nullable joins from the native list.
            model = apps.get_model(target.model)
            item = model.objects.select_for_update().filter(
                pk=payload.validated_data["object_id"], pk__in=queryset.values("pk"),
            ).first()
            if item is None:
                raise ValidationError({"object_id": "Objet introuvable ou inaccessible dans cet établissement."})
            native.check_object_permissions(native.request, item)
            if target.direct:
                if item.organisation_unit_id is not None:
                    raise ValidationError({"object_id": "Cette classe ou formation possède déjà une unité d’origine figée."})
                item.organisation_unit = unit
                item.save(update_fields=["organisation_unit"])
            else:
                model = apps.get_model("core.OrganizationAttachment")
                if model.objects.filter(**{f"{kind}_id": item.pk}).exists():
                    raise ValidationError({"object_id": "Cet objet possède déjà un rattachement figé."})
                model.objects.create(unit=unit, created_by=request.user, **{kind: item})
            record_workflow_event(
                request, unit, "rattachement_organisation", "Objet existant rattaché à l’organisation",
                metadata={"kind": kind, "object_id": item.pk, "unit": unit.pk, "preserved_configuration": True},
            )
        return Response(target_summary(kind, target, item), status=201)

    @action(detail=True, methods=["get"], url_path="attached-object")
    def attached_object(self, request, pk=None):
        tenant = self.attachment_admin()
        unit = self.get_object()
        unit_path(tenant, unit)
        kind = request.query_params.get("kind")
        target, queryset, native = readable_targets(kind, request)
        identifier = serializers.IntegerField(min_value=1).run_validation(request.query_params.get("object_id"))
        if target.direct:
            queryset = queryset.filter(organisation_unit=unit)
        else:
            ids = apps.get_model("core.OrganizationAttachment").objects.filter(unit=unit).values(f"{kind}_id")
            queryset = queryset.filter(pk__in=ids)
        item = queryset.filter(pk=identifier).first()
        if item is None:
            raise ValidationError({"object_id": "Objet non rattaché ou inaccessible."})
        native.check_object_permissions(native.request, item)
        return Response(target_detail(kind, target, item, request))


class ScopeSerializer(serializers.Serializer):
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.all(), allow_null=True, required=False, default=None
    )
    at = serializers.DateTimeField(required=False)

    def validate_unit(self, value):
        unit_path(checked_tenant(self.context["request"]), value)
        return value


class PublicationSerializer(ScopeSerializer):
    base_revision = serializers.IntegerField(min_value=0)
    values = serializers.JSONField()
    locks = serializers.JSONField()
    reason = serializers.CharField(max_length=1000)
    effective_from = serializers.DateTimeField(required=False, allow_null=True)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - (set(self.fields) - {"at"}):
            raise ValidationError({"detail": "Champ de publication inconnu."})
        return super().to_internal_value(data)

    def validate(self, attrs):
        validate_settings(attrs["values"], attrs["locks"])
        if attrs.get("effective_from") is not None and attrs["effective_from"] < timezone.now():
            raise ValidationError({"effective_from": "Une publication ne peut pas être antidatée."})
        return attrs


class ConfigurationHierarchyMixin:
    def get(self, request):
        tenant = checked_tenant(request)
        data = ScopeSerializer(data=request.query_params, context={"request": request})
        data.is_valid(raise_exception=True)
        unit = data.validated_data["unit"]
        history = Revision.objects.filter(etablissement_id=tenant.pk, unit=unit).select_related("published_by")[:50]
        return Response(
            {
                "revision": latest_revision(tenant),
                "schema": SETTING_SCHEMA,
                "effective": resolve_configuration(tenant, unit, data.validated_data.get("at")),
                "history": [
                    {
                        "revision": item.revision,
                        "values": item.values,
                        "locks": item.locks,
                        "effective_from": item.effective_from,
                        "published_at": item.published_at,
                        "published_by": item.published_by.get_full_name() or item.published_by.username,
                        "reason": item.reason,
                    }
                    for item in history
                ],
            }
        )

    def prepare(self, request, tenant):
        serializer = PublicationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        revision = latest_revision(tenant)
        if data["base_revision"] != revision:
            raise StaleModuleConfiguration("La configuration a changé. Rechargez-la avant de publier.")
        effective_from = data.get("effective_from") or timezone.now()
        publications = list(Revision.objects.filter(etablissement_id=tenant.pk).order_by("effective_from", "revision"))
        unit = data["unit"]
        if unit:
            ancestors = resolve_configuration(tenant, unit.parent, effective_from, publications=publications)
            if set(data["values"]) & ancestors["locks"].keys():
                raise ValidationError({"values": "Un paramètre est verrouillé par un périmètre supérieur."})
        proposed = {
            "unit_id": unit.pk if unit else None,
            "values": data["values"],
            "locks": data["locks"],
            "revision": revision + 1,
            "effective_from": effective_from.isoformat(),
        }
        impacts = []
        for descendant in Unit.objects.filter(etablissement_id=tenant.pk).select_related("parent__parent"):
            ancestors = unit_path(tenant, descendant)
            if unit is None or unit in ancestors:
                result = resolve_configuration(tenant, descendant, effective_from, proposed, publications)
                if result["ignored_overrides"]:
                    impacts.append(
                        {"unit": descendant.pk, "nom": descendant.nom, "ignored": result["ignored_overrides"]}
                    )
        result = resolve_configuration(tenant, unit, effective_from, proposed, publications)
        return data, effective_from, result, impacts

    def post(self, request):
        tenant = checked_tenant(request)
        _data, _effective_from, result, impacts = self.prepare(request, tenant)
        return Response({"saved": False, "effective": result, "impacts": impacts})

    @transaction.atomic
    def patch(self, request):
        tenant = checked_tenant(request)
        type(tenant).objects.select_for_update().get(pk=tenant.pk)
        data, effective_from, result, impacts = self.prepare(request, tenant)
        publication = Revision.objects.create(
            etablissement=tenant,
            unit=data["unit"],
            revision=data["base_revision"] + 1,
            values=data["values"],
            locks=data["locks"],
            effective_from=effective_from,
            reason=data["reason"],
            published_by=request.user,
        )
        record_workflow_event(
            request,
            publication,
            "publication_configuration",
            "Configuration institutionnelle publiée",
            message=data["reason"],
            metadata={
                "revision": publication.revision,
                "unit": publication.unit_id,
                "effective_from": effective_from.isoformat(),
                "locks": data["locks"],
            },
        )
        return Response({"revision": publication.revision, "effective": result, "impacts": impacts}, status=201)
