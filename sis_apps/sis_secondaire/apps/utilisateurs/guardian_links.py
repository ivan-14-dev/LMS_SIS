"""Tenant-bound management of family affiliations using the existing pupil links."""

from copy import copy

from apps.eleves.models import Eleve, EleveTuteur, Tuteur
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import filter_queryset_by_scopes, has_business_permission, is_current_tenant_user
from sis_common.serializers import TenantBoundSerializerMixin
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

from .models import Utilisateur


def _permission(view):
    operation = {
        "create": "add",
        "update": "change",
        "partial_update": "change",
        "destroy": "delete",
    }.get(view.action, "view")
    return f"eleves.{operation}_{view.permission_model}"


class CanManageFamily(IsAuthenticated):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.is_active
            and is_current_tenant_user(request)
            and request.user.has_perm(_permission(view))
        )


class GuardianSerializer(TenantBoundSerializerMixin, serializers.ModelSerializer):
    compte = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Tuteur
        fields = [
            "id",
            "etablissement",
            "user",
            "compte",
            "nom",
            "prenom",
            "lien_parente",
            "telephone",
            "email",
        ]
        read_only_fields = ["id", "etablissement"]
        extra_kwargs = {"user": {"required": True, "allow_null": False}}

    def get_fields(self):
        fields = super().get_fields()
        if getattr(self.context.get("view"), "swagger_fake_view", False):
            fields["user"].queryset = Utilisateur.objects.none()
            return fields
        fields["user"].queryset = Utilisateur.objects.filter(
            etablissement=self.context["request"].tenant,
            role="parent",
            is_active=True,
        )
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and attrs.get("user", self.instance.user) != self.instance.user:
            raise serializers.ValidationError({"user": "Le compte d'un profil parent ne peut pas être transféré."})
        return attrs


class GuardianLinkSerializer(serializers.ModelSerializer):
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    tuteur_nom = serializers.CharField(source="tuteur.__str__", read_only=True)

    class Meta:
        model = EleveTuteur
        fields = [
            "id",
            "eleve",
            "eleve_nom",
            "tuteur",
            "tuteur_nom",
            "autorise_acces_portail",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {"autorise_acces_portail": {"required": True}}

    def get_fields(self):
        fields = super().get_fields()
        if getattr(self.context.get("view"), "swagger_fake_view", False):
            fields["eleve"].queryset = Eleve.objects.none()
            fields["tuteur"].queryset = Tuteur.objects.none()
            return fields
        tenant = self.context["request"].tenant
        fields["eleve"].queryset = Eleve.objects.filter(etablissement=tenant, user__etablissement=tenant)
        fields["tuteur"].queryset = Tuteur.objects.filter(
            etablissement=tenant,
            user__etablissement=tenant,
            user__role="parent",
            user__is_active=True,
        )
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance:
            for name in ("eleve", "tuteur"):
                if attrs.get(name, getattr(self.instance, name)) != getattr(self.instance, name):
                    raise serializers.ValidationError({name: "Retirez la liaison avant d'en créer une autre."})
        return attrs


class FamilyAuditViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageFamily]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    def scoped_queryset(self, queryset, scope_fields):
        visible_ids = (
            filter_queryset_by_scopes(
                queryset,
                self.request.user,
                _permission(self),
                scope_fields,
            )
            .order_by()
            .values("pk")
        )
        # DISTINCT belongs in the authorization subquery, not the row lock.
        return queryset.filter(pk__in=visible_ids)

    def _context(self, instance):
        if isinstance(instance, EleveTuteur):
            return {
                "eleves": instance.eleve_id,
                "classes": instance.eleve.classe_actuelle_id,
                "tuteurs": instance.tuteur_id,
            }
        return {"tuteurs": instance.pk, "comptes": instance.user_id}

    def _check_write(self, instance):
        if not has_business_permission(self.request.user, _permission(self), context=self._context(instance)):
            raise PermissionDenied("Cette affiliation est hors de votre périmètre.")

    def _snapshot(self, instance):
        names = (
            ("eleve_id", "tuteur_id", "autorise_acces_portail")
            if isinstance(instance, EleveTuteur)
            else ("user_id", "nom", "prenom", "lien_parente", "telephone", "email")
        )
        return {name: getattr(instance, name) for name in names}

    def _audit(self, instance, operation, before, after):
        record_workflow_event(
            self.request,
            instance,
            f"family_{operation}",
            "Affiliation parent",
            metadata={"before": before, "after": after},
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            queryset = queryset.select_for_update(of=("self",))
        obj = get_object_or_404(queryset, pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        instance = serializer.Meta.model(**serializer.validated_data)
        self._check_write(instance)
        instance = serializer.save()
        self._audit(instance, "created", None, self._snapshot(instance))

    def perform_update(self, serializer):
        self._check_write(serializer.instance)
        before = self._snapshot(serializer.instance)
        instance = serializer.save()
        self._audit(instance, "updated", before, self._snapshot(instance))

    def perform_destroy(self, instance):
        self._check_write(instance)
        if isinstance(instance, Tuteur) and instance.enfants_lies.exists():
            raise serializers.ValidationError({"detail": "Retirez d'abord les liaisons de ce parent."})
        before = self._snapshot(instance)
        identity = copy(instance)
        instance.delete()
        self._audit(identity, "deleted", before, None)

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        instance = self.get_object()
        if not has_business_permission(request.user, "core.view_workflowevent"):
            raise PermissionDenied("La consultation de l'historique exige une permission explicite.")
        events = workflow_history_queryset(instance).filter(tenant_id=request.tenant.pk)
        page = self.paginate_queryset(events)
        data = [
            {
                "id": event.pk,
                "action": event.action,
                "created_at": event.created_at,
                "actor_id": event.actor_id,
                "metadata": event.metadata,
            }
            for event in (page if page is not None else events)
        ]
        return self.get_paginated_response(data) if page is not None else Response(data)


class GuardiansViewSet(FamilyAuditViewSet):
    serializer_class = GuardianSerializer
    permission_model = "tuteur"

    def get_queryset(self):
        return self.scoped_queryset(
            Tuteur.objects.filter(etablissement=self.request.tenant)
            .filter(
                Q(user__isnull=True) | Q(user__etablissement=self.request.tenant),
            )
            .select_related("user"),
            {"tuteurs": "pk", "comptes": "user_id"},
        ).order_by("nom", "prenom", "pk")


class GuardianLinksViewSet(FamilyAuditViewSet):
    serializer_class = GuardianLinkSerializer
    permission_model = "elevetuteur"

    def get_queryset(self):
        tenant = self.request.tenant
        return self.scoped_queryset(
            EleveTuteur.objects.filter(
                eleve__etablissement=tenant,
                eleve__user__etablissement=tenant,
                tuteur__etablissement=tenant,
                tuteur__user__etablissement=tenant,
            ).select_related("eleve__user", "tuteur__user"),
            {"eleves": "eleve_id", "classes": "eleve__classe_actuelle_id", "tuteurs": "tuteur_id"},
        ).order_by("pk")
