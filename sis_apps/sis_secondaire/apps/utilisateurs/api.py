"""API views for utilisateurs (ViewSets DRF) - SIS Secondaire."""

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common import mfa as mfa_service
from sis_common.academic_lifecycle import AcademicLifecycleMixin
from sis_common.authorization import (
    can_delegate_permissions,
    has_business_permission,
    has_business_permission_or_role,
    is_current_tenant_user,
    permission_snapshot,
)
from sis_common.branding import branding_snapshot
from sis_common.module_registry import module_snapshot
from sis_common.session_security import (
    list_active_sessions,
    revoke_all_sessions,
    revoke_session,
)

from .models import Utilisateur
from .serializers import (
    ChangePasswordSerializer,
    GroupAssignmentSerializer,
    GroupSerializer,
    MFACodeSerializer,
    MFADisableSerializer,
    PermissionSerializer,
    RevokeSessionSerializer,
    UtilisateurCreateSerializer,
    UtilisateurDetailSerializer,
    UtilisateurListSerializer,
    UtilisateurProfileSerializer,
)


class IsDirectionOrReadOnly(IsAuthenticated):
    """Permission: direction pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        if view.action in (
            "update_profile",
            "change_password",
            "revoke_sessions",
            "sessions",
            "revoke_session",
            "mfa_enroll",
            "mfa_activate",
            "mfa_disable",
        ):
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        if not is_current_tenant_user(request):
            return False
        permission = {
            "create": "utilisateurs.add_utilisateur",
            "destroy": "utilisateurs.delete_utilisateur",
        }.get(view.action, "utilisateurs.change_utilisateur")
        return has_business_permission_or_role(
            user,
            permission,
            ("direction", "responsable_pedagogique"),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=("academic_admin_secondary",),
        )


class CanManageAuthorization(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view) or not is_current_tenant_user(request):
            return False
        if view.action in ("assign", "unassign"):
            return has_business_permission(request.user, "auth.change_group") and has_business_permission(
                request.user, "utilisateurs.change_utilisateur"
            )
        permission = {
            "GET": "auth.view_group",
            "HEAD": "auth.view_group",
            "OPTIONS": "auth.view_group",
            "POST": "auth.add_group",
            "DELETE": "auth.delete_group",
        }.get(request.method, "auth.change_group")
        return has_business_permission(request.user, permission)


class UtilisateursViewSet(AcademicLifecycleMixin, viewsets.ModelViewSet):
    """ViewSet CRUD pour utilisateurs."""

    permission_classes = [IsDirectionOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["role", "is_active", "etablissement"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "last_name", "date_joined"]
    ordering = ["last_name", "first_name"]

    def get_queryset(self):
        """Retourne les utilisateurs de l'établissement courant."""
        qs = Utilisateur.objects.select_related("etablissement")

        # Filtrer par établissement du tenant
        request = self.request
        if hasattr(request, "tenant"):
            qs = qs.filter(etablissement=request.tenant)

        can_list = has_business_permission_or_role(
            request.user,
            "utilisateurs.view_utilisateur",
            ("direction", "responsable_pedagogique"),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=("academic_admin_secondary",),
        )
        if not can_list:
            return qs.filter(pk=request.user.pk)
        if not request.user.is_superuser:
            qs = qs.filter(is_superuser=False)

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return UtilisateurListSerializer
        elif self.action == "create":
            return UtilisateurCreateSerializer
        elif self.action in ("update_profile", "me"):
            return UtilisateurProfileSerializer
        return UtilisateurDetailSerializer

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Retourne le profil de l'utilisateur connecté."""
        serializer = UtilisateurDetailSerializer(request.user)
        return Response({**serializer.data, "branding": branding_snapshot(request)})

    @action(detail=False, methods=["get"])
    def capabilities(self, request):
        from apps.portail.api import portal_capabilities

        snapshot = permission_snapshot(request.user, getattr(request.tenant, "configuration_academique", {}))
        snapshot["modules"] = module_snapshot(request.tenant)["enabled"]
        snapshot.update(portal_capabilities(request))
        return Response(snapshot)

    @action(detail=False, methods=["patch"])
    def update_profile(self, request):
        """Met à jour le profil de l'utilisateur connecté."""
        serializer = UtilisateurProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        """Change le mot de passe de l'utilisateur connecté."""
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        # Un changement de mot de passe doit invalider toutes les sessions
        # existantes (jeton DRF + jetons JWT actifs) pour éviter qu'une
        # session déjà compromise reste valide après la remédiation.
        revoke_all_sessions(request.user)
        return Response({"detail": "Mot de passe modifié avec succès."})

    @action(detail=False, methods=["post"])
    def revoke_sessions(self, request):
        """Déconnecte l'utilisateur connecté de toutes ses sessions actives."""
        summary = revoke_all_sessions(request.user)
        return Response(
            {
                "detail": "Toutes les sessions actives ont été révoquées.",
                **summary,
            }
        )

    @action(detail=False, methods=["get"])
    def sessions(self, request):
        """Liste les sessions JWT actives (une par appareil/navigateur connecté)."""
        return Response(list_active_sessions(request.user))

    @action(detail=False, methods=["post"])
    def revoke_session(self, request):
        """Révoque une seule session JWT de l'utilisateur connecté, par `jti`."""
        serializer = RevokeSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = revoke_session(request.user, serializer.validated_data["jti"])
        if result is None:
            return Response(
                {"detail": "Session introuvable pour cet utilisateur."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"detail": "Session révoquée.", **result})

    @action(detail=False, methods=["post"])
    def mfa_enroll(self, request):
        """Démarre l'enrôlement MFA (TOTP) : génère un secret non activé."""
        secret, provisioning_uri = mfa_service.begin_enrollment(request.user)
        return Response(
            {
                "secret": secret,
                "provisioning_uri": provisioning_uri,
                "detail": "Scannez le QR code puis confirmez avec un code via mfa_activate.",
            }
        )

    @action(detail=False, methods=["post"])
    def mfa_activate(self, request):
        """Confirme l'enrôlement MFA avec un premier code TOTP valide."""
        serializer = MFACodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not mfa_service.confirm_enrollment(request.user, serializer.validated_data["code"]):
            return Response({"code": "Code MFA invalide."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "MFA activé avec succès.", "mfa_active": True})

    @action(detail=False, methods=["post"])
    def mfa_disable(self, request):
        """Désactive le MFA (requiert le mot de passe et un code TOTP valide)."""
        serializer = MFADisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["password"]):
            return Response({"password": "Mot de passe incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        if not mfa_service.verify_code(user.mfa_secret, serializer.validated_data["code"]):
            return Response({"code": "Code MFA invalide."}, status=status.HTTP_400_BAD_REQUEST)
        mfa_service.disable_mfa(user)
        return Response({"detail": "MFA désactivé.", "mfa_active": False})

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        """Active/désactive un utilisateur."""
        user = self.get_object()
        if user == request.user:
            return Response(
                {"error": "Vous ne pouvez pas vous désactiver vous-même."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        action_str = "activé" if user.is_active else "désactivé"
        return Response(
            {
                "id": user.id,
                "is_active": user.is_active,
                "detail": f"Utilisateur {action_str}.",
            }
        )

    @action(detail=True, methods=["post"])
    def force_logout(self, request, pk=None):
        """Révoque toutes les sessions actives d'un autre utilisateur (action admin)."""
        user = self.get_object()
        summary = revoke_all_sessions(user)
        return Response(
            {
                "id": user.id,
                "detail": f"Sessions de {user} révoquées.",
                **summary,
            }
        )


class PermissionsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [CanManageAuthorization]
    serializer_class = PermissionSerializer
    queryset = Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename")
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["content_type__app_label"]
    search_fields = ["codename", "name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            return queryset
        granted = self.request.user.get_all_permissions()
        scopes = (self.request.user.attributs_acces or {}).get("permission_scopes", {})
        return queryset.filter(
            pk__in=[
                permission.pk
                for permission in queryset
                if f"{permission.content_type.app_label}.{permission.codename}" in granted
                and f"{permission.content_type.app_label}.{permission.codename}" not in scopes
            ]
        )


class GroupesPermissionsViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageAuthorization]
    serializer_class = GroupSerializer
    queryset = Group.objects.prefetch_related("permissions").order_by("name")

    def get_object(self):
        group = super().get_object()
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            group = Group.objects.select_for_update().prefetch_related("permissions").get(pk=group.pk)
        if self.request.method not in ("GET", "HEAD", "OPTIONS") and not self.request.user.is_superuser:
            if self.request.user.groups.filter(pk=group.pk).exists() or not can_delegate_permissions(
                self.request.user, group.permissions.all()
            ):
                raise PermissionDenied("Ce groupe ne peut pas être administré par cet utilisateur.")
        return group

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def assign(self, request, pk=None):
        group = self.get_object()
        serializer = GroupAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._assignment_target(request, serializer.validated_data["user_id"])
        user.groups.add(group)
        return Response({"user_id": user.pk, "group_id": group.pk})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def unassign(self, request, pk=None):
        group = self.get_object()
        serializer = GroupAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._assignment_target(request, serializer.validated_data["user_id"])
        user.groups.remove(group)
        return Response({"user_id": user.pk, "group_id": group.pk})

    def _assignment_target(self, request, user_id):
        user = get_object_or_404(Utilisateur.objects.select_for_update(), pk=user_id, etablissement=request.tenant)
        if not request.user.is_superuser and (user.pk == request.user.pk or user.is_superuser):
            raise PermissionDenied("Impossible de modifier vos propres groupes ou un super-utilisateur.")
        return user
