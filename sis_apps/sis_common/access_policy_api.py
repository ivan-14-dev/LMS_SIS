"""Audited account-level grants, denials and additional role assignments."""

import hashlib
import json

from django.contrib.auth.models import Permission
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from sis_common.access_policy import FEATURES, policy_for, public_policy
from sis_common.authorization import can_delegate_permissions, has_business_permission, is_current_tenant_user
from sis_common.workflow_tracking import record_workflow_event


class PolicySerializer(serializers.Serializer):
    version = serializers.RegexField(r"^[0-9a-f]{64}$")
    additional_roles = serializers.ListField(child=serializers.CharField(max_length=100), max_length=30)
    user_permissions = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=2000)
    denied_permissions = serializers.ListField(child=serializers.CharField(max_length=240), max_length=2000)
    disabled_features = serializers.ListField(
        child=serializers.ChoiceField(choices=list(FEATURES)), max_length=len(FEATURES)
    )

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise ValidationError({"detail": "La demande contient des champs inconnus."})
        return super().to_internal_value(data)


def _snapshot(user):
    return {
        "primary_role": user.role,
        "policy": policy_for(user),
        "user_permissions": list(user.user_permissions.order_by("pk").values_list("pk", flat=True)),
    }


def _version(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def policy_response(user, actor):
    snapshot = _snapshot(user)
    policy = snapshot["policy"]
    protected = user.is_superuser or user.pk == actor.pk
    return {
        **public_policy(user),
        "version": _version(snapshot),
        "additional_roles": policy.get("additional_roles", []),
        "disabled_features": policy.get("disabled_features", []),
        "user_permissions": snapshot["user_permissions"],
        "effective_permissions": ["*"] if user.is_superuser else sorted(user.get_all_permissions()),
        "editable": not protected,
        "can_edit_roles": actor.is_superuser and not protected,
        "can_restore_features": actor.is_superuser and not protected,
        "role_options": [
            {"code": code, "label": label}
            for code, label in user.ROLE_CHOICES
            if code not in ("super_admin", user.role)
        ],
        "features": [{"code": code, "label": feature["label"]} for code, feature in FEATURES.items()],
    }


class AccountAccessPolicyMixin:
    @action(detail=True, methods=["get", "put"], url_path="access-policy")
    def access_policy(self, request, pk=None):
        if not is_current_tenant_user(request) or not all(
            has_business_permission(request.user, permission)
            for permission in ("utilisateurs.view_utilisateur", "utilisateurs.change_utilisateur", "auth.change_group")
        ):
            raise PermissionDenied("La gestion des comptes et des autorisations est requise.")
        target = self.get_object()
        if request.method == "GET":
            response = Response(policy_response(target, request.user))
        else:
            response = self._update_access_policy(request, target)
        response["Cache-Control"] = "private, no-store"
        return response

    @transaction.atomic
    def _update_access_policy(self, request, target):
        target = get_object_or_404(self.get_queryset().select_for_update(), pk=target.pk)
        if target.is_superuser or target.pk == request.user.pk:
            raise PermissionDenied("Les droits de votre propre compte et des super-utilisateurs sont protégés.")
        serializer = PolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        before = _snapshot(target)
        if data["version"] != _version(before):
            return Response({"detail": "Les droits ont changé. Rechargez le compte avant de recommencer."}, status=409)

        roles = sorted(set(data["additional_roles"]))
        allowed_roles = dict(target.ROLE_CHOICES).keys() - {"super_admin", target.role}
        if set(roles) - allowed_roles:
            raise ValidationError({"additional_roles": "Un rôle est inconnu, protégé ou déjà principal."})
        if not request.user.is_superuser and set(roles) != set(before["policy"].get("additional_roles", [])):
            raise PermissionDenied("L'attribution des rôles métier requiert un super-utilisateur.")

        permissions = list(Permission.objects.select_related("content_type"))
        by_id = {permission.pk: permission for permission in permissions}
        by_code = {
            f"{permission.content_type.app_label}.{permission.codename}": permission for permission in permissions
        }
        grants = set(data["user_permissions"])
        denials = set(data["denied_permissions"])
        if grants - by_id.keys() or denials - by_code.keys():
            raise ValidationError("Une permission est inconnue.")
        restored = set(before["policy"].get("denied_permissions", [])) - denials
        delegated = [by_id[pk] for pk in grants - set(before["user_permissions"])]
        delegated.extend(by_code[code] for code in restored if code in by_code)
        if not can_delegate_permissions(request.user, delegated):
            raise PermissionDenied("Vous ne pouvez pas attribuer ou rétablir une permission hors de votre périmètre.")
        if not request.user.is_superuser and (
            set(before["policy"].get("disabled_features", [])) - set(data["disabled_features"])
        ):
            raise PermissionDenied("Le rétablissement des accès hérités requiert un super-utilisateur.")

        target.attributs_acces = {
            **target.attributs_acces,
            "access_policy": {
                "additional_roles": roles,
                "denied_permissions": sorted(denials),
                "disabled_features": sorted(set(data["disabled_features"])),
            },
        }
        target.save(update_fields=["attributs_acces"])
        target.user_permissions.set(grants)
        for cache in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            target.__dict__.pop(cache, None)
        record_workflow_event(
            request,
            target,
            "account_access_updated",
            "Modification des accès individuels",
            metadata={"before": before, "after": _snapshot(target)},
        )
        from sis_common.lms_access_sync import queue_revoked_access

        queue_revoked_access()
        return Response(policy_response(target, request.user))
