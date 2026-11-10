"""Reciprocal workspace declarations, without cross-database grants or identity guessing."""

import hashlib
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sis_common.authorization import is_current_tenant_user
from sis_common.institutional_profiles import TYPE_PROFILES
from sis_common.workflow_tracking import record_workflow_event


def workspace_snapshot(tenant, user):
    configuration = {
        "id": str(tenant.workspace_id),
        "peer": str(tenant.workspace_peer) if tenant.workspace_peer else None,
        "home": str(tenant.workspace_home) if tenant.workspace_home else None,
        "revision": tenant.workspace_revision,
    }
    profiles = TYPE_PROFILES.get(tenant.type, ())
    variants = []
    if "secondary" in profiles or "primary" in profiles:
        variants.append("secondaire")
    if "higher_education" in profiles:
        variants.append("superieur")
    return {
        **configuration,
        "version": hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest(),
        "variant": settings.SIS_VARIANT,
        "name": tenant.nom,
        "type": tenant.type,
        "variants": variants or [settings.SIS_VARIANT],
        "user": user.pk,
        "account": user.get_full_name() or user.username,
        "account_link": user.workspace_link,
        "can_configure": user.is_superuser,
    }


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise ValidationError({"detail": "La demande contient des champs inconnus."})
        return super().to_internal_value(data)


class DeclarationSerializer(StrictSerializer):
    version = serializers.RegexField(r"^[0-9a-f]{64}$")
    peer = serializers.UUIDField(allow_null=True)
    home = serializers.UUIDField(allow_null=True)


class AccountLinkSerializer(StrictSerializer):
    peer = serializers.UUIDField(allow_null=True)
    user = serializers.IntegerField(min_value=1, allow_null=True)


class InstitutionWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_current_tenant_user(request):
            raise PermissionDenied("Un compte de cet établissement est requis.")
        response = Response(workspace_snapshot(request.tenant, request.user))
        response["Cache-Control"] = "private, no-store"
        return response

    @transaction.atomic
    def put(self, request):
        if not is_current_tenant_user(request) or not request.user.is_superuser:
            raise PermissionDenied("Le rattachement institutionnel requiert un super-utilisateur.")
        serializer = DeclarationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant = type(request.tenant).objects.select_for_update().get(pk=request.tenant.pk)
        before = workspace_snapshot(tenant, request.user)
        if before["version"] != data["version"]:
            return Response({"detail": "Le rattachement a changé. Rechargez les deux espaces."}, status=409)
        if data["peer"] is None:
            if data["home"] is not None:
                raise ValidationError({"home": "Un espace détaché ne possède pas de siège commun."})
        elif data["peer"] == tenant.workspace_id or data["home"] not in (tenant.workspace_id, data["peer"]):
            raise ValidationError({"peer": "Choisissez un autre espace et l'un des deux comme siège."})
        tenant.workspace_peer = data["peer"]
        tenant.workspace_home = data["home"]
        tenant.workspace_revision += 1
        tenant.save(update_fields=["workspace_peer", "workspace_home", "workspace_revision"])
        record_workflow_event(
            request,
            tenant,
            "institution_workspace_changed",
            "Rattachement d'un espace institutionnel",
            metadata={"before": before, "after": workspace_snapshot(tenant, request.user)},
        )
        request.tenant = tenant
        return self.get(request)


class WorkspaceAccountMixin:
    @action(detail=False, methods=["put"], url_path="workspace-link")
    @transaction.atomic
    def workspace_link(self, request):
        if not is_current_tenant_user(request):
            raise PermissionDenied("Un compte de cet établissement est requis.")
        fields = AccountLinkSerializer(data=request.data)
        fields.is_valid(raise_exception=True)
        data = fields.validated_data
        if (data["peer"] is None) != (data["user"] is None):
            raise ValidationError("L'identité doit être complètement renseignée ou retirée.")
        if data["peer"] is not None and data["peer"] != request.tenant.workspace_peer:
            raise PermissionDenied("Cet espace n'est pas rattaché à votre établissement.")
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        before = user.workspace_link
        link = (
            {
                "peer": str(data["peer"]),
                "user": data["user"],
                "version": workspace_snapshot(request.tenant, user)["version"],
            }
            if data["peer"]
            else None
        )
        user.workspace_link = link
        user.save(update_fields=["workspace_link"])
        record_workflow_event(
            request,
            user,
            "workspace_account_link_changed",
            "Association volontaire de mes espaces",
            metadata={"before": before, "after": link},
        )
        response = Response({"detail": "Déclaration enregistrée. L'autre compte doit aussi la confirmer."})
        response["Cache-Control"] = "private, no-store"
        return response
