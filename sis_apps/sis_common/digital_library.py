"""The same tenant, permission and licence gate for every library download."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404
from django.utils import timezone
from django.views.static import serve
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from sis_common.authorization import has_business_permission, is_current_tenant_user

DIGITAL_FIELDS = {"ressource_numerique", "licence_active", "licence_reference", "licence_expire_le"}


def library_permission(request, permission, livre=None):
    if request is None or not is_current_tenant_user(request) or not request.user.is_active:
        return False
    # A request-local fresh account avoids stale Django permission caches, including
    # when a client reuses its authenticated user after a grant has been revoked.
    if not hasattr(request, "_library_user"):
        request._library_user = get_user_model()._default_manager.filter(pk=request.user.pk).first()
    user = request._library_user
    if user is None or not user.is_active or user.etablissement_id != request.user.etablissement_id:
        return False
    context = {"etablissement_id": request.tenant.pk}
    if livre is not None:
        context["livre_id"] = livre.pk
    return has_business_permission(user, permission, context=context)


def can_consult_library_resource(request, livre):
    return bool(
        livre.ressource_numerique
        and livre.licence_active
        and livre.licence_reference.strip()
        and (livre.licence_expire_le is None or livre.licence_expire_le >= timezone.localdate())
        and library_permission(request, "bibliotheque.consulter_ressource_numerique", livre)
    )


def library_file_response(request, livre):
    if not can_consult_library_resource(request, livre):
        raise PermissionDenied("Permission de consultation et licence active non expirée requises.")
    try:
        stream = livre.ressource_numerique.open("rb")
    except FileNotFoundError as error:
        raise Http404("Ressource indisponible.") from error
    response = FileResponse(stream, as_attachment=True, filename=Path(livre.ressource_numerique.name).name)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class LibraryFileField(serializers.FileField):
    def to_representation(self, value):
        if not value or not can_consult_library_resource(self.context.get("request"), value.instance):
            return None
        return f"/api/v1/bibliotheque/livres/{value.instance.pk}/numerique/"


class DigitalLibrarySerializerMixin:
    def get_peut_consulter_ressource(self, obj):
        return can_consult_library_resource(self.context.get("request"), obj)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if DIGITAL_FIELDS.intersection(attrs):
            if not library_permission(self.context.get("request"), "bibliotheque.change_livre", self.instance):
                raise PermissionDenied("Le droit explicite de modifier ce livre est requis.")
            active = attrs.get("licence_active", getattr(self.instance, "licence_active", False))
            reference = attrs.get("licence_reference", getattr(self.instance, "licence_reference", ""))
            if active and not reference.strip():
                raise ValidationError({"licence_reference": "Un justificatif est obligatoire pour activer la licence."})
        return attrs


class LibraryTenantPermission(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and is_current_tenant_user(request)


class DigitalLibraryViewSetMixin:
    @action(detail=True, methods=["get"])
    def numerique(self, request, pk=None):
        return library_file_response(request, self.get_object())

    def perform_create(self, serializer):
        if not library_permission(self.request, "bibliotheque.change_livre"):
            raise PermissionDenied("Le droit explicite de modifier les livres est requis.")
        serializer.save()

    def perform_update(self, serializer):
        if not library_permission(self.request, "bibliotheque.change_livre", serializer.instance):
            raise PermissionDenied("Le droit explicite de modifier ce livre est requis.")
        serializer.save()

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "numerique"):
            return [LibraryTenantPermission()]
        return super().get_permissions()


class LegacyLibraryMediaView(APIView):
    permission_classes = [LibraryTenantPermission]

    def get(self, request, path):
        from apps.bibliotheque.models import Livre

        books = list(Livre.objects.filter(ressource_numerique=path))
        # A legacy shared path must satisfy every associated declaration.
        if not books:
            raise Http404
        if not all(can_consult_library_resource(request, book) for book in books):
            raise PermissionDenied("Ressource non autorisée.")
        return library_file_response(request, books[0])


def library_media(request, path):
    """Intercept old library URLs before Django's DEBUG media fallback."""
    # Reject aliases before dispatch: the static fallback performs its own normalization.
    if "\\" in path or any(part in ("", ".", "..") for part in path.split("/")):
        raise Http404
    if path == "bibliotheque/numerique" or path.startswith("bibliotheque/numerique/"):
        return LegacyLibraryMediaView.as_view()(request, path=path)
    if settings.DEBUG:
        return serve(request, path, document_root=settings.MEDIA_ROOT)
    raise Http404
