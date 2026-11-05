"""Tenant module activation with preview, optimistic concurrency and audit."""

from django.apps import apps
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from sis_common.module_registry import (
    effective_modules,
    module_configuration,
    module_snapshot,
    validate_module_changes,
)
from sis_common.workflow_tracking import record_workflow_event


class ModuleChangeSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    enabled = serializers.JSONField()
    reason = serializers.CharField(max_length=1000)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise ValidationError({"non_field_errors": "Seuls revision, enabled et reason sont acceptés."})
        return super().to_internal_value(data)


class StaleModuleConfiguration(APIException):
    status_code = 409
    default_detail = "La configuration des modules a changé. Rechargez-la avant de réessayer."


class ModuleConfigurationMixin:
    def checked_tenant(self, request):
        tenant = self.get_tenant(request)
        if tenant is None:
            raise NotFound("Aucun établissement n'est associé à ce domaine.")
        if not request.user.is_active or request.user.etablissement_id != tenant.pk:
            raise PermissionDenied("La configuration est réservée à votre établissement.")
        return tenant

    def get(self, request):
        return Response(module_snapshot(self.checked_tenant(request)))

    def proposed(self, request, configuration):
        serializer = ModuleChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["revision"] != (configuration.revision if configuration else 0):
            raise StaleModuleConfiguration()
        current = configuration.enabled if configuration else {}
        proposed = validate_module_changes(current, data["enabled"])
        before, after = effective_modules(current), effective_modules(proposed)
        changes = {
            identifier: {"before": before[identifier], "after": after[identifier]}
            for identifier in before
            if before[identifier] != after[identifier]
        }
        return proposed, changes, data["reason"]

    def post(self, request):
        tenant = self.checked_tenant(request)
        proposed, changes, _reason = self.proposed(request, module_configuration(tenant))
        return Response({"enabled": effective_modules(proposed), "changes": changes, "saved": False})

    @transaction.atomic
    def patch(self, request):
        tenant = self.checked_tenant(request)
        model = apps.get_model("core.ModuleConfiguration")
        configuration, _created = model.objects.get_or_create(etablissement_id=tenant.pk)
        configuration = model.objects.select_for_update().get(pk=configuration.pk)
        proposed, changes, reason = self.proposed(request, configuration)
        if changes:
            configuration.enabled = proposed
            configuration.revision += 1
            configuration.save(update_fields=["enabled", "revision", "updated_at"])
            record_workflow_event(
                request,
                configuration,
                "configuration_modules",
                "Modules de l'établissement modifiés",
                message=reason,
                metadata={"revision": configuration.revision, "changes": changes},
            )
        return Response(module_snapshot(tenant))
