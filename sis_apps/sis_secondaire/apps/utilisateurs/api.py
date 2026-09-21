"""API views for utilisateurs (ViewSets DRF) - SIS Secondaire."""

from django.contrib.auth.models import Group, Permission
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import (
    has_business_permission_or_role,
    permission_snapshot,
)

from .models import Utilisateur
from .serializers import (
    ChangePasswordSerializer,
    GroupSerializer,
    PermissionSerializer,
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
        if view.action in ("update_profile", "change_password"):
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
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
        if not super().has_permission(request, view):
            return False
        permission = {
            "GET": "auth.view_group",
            "HEAD": "auth.view_group",
            "OPTIONS": "auth.view_group",
            "POST": "auth.add_group",
            "DELETE": "auth.delete_group",
        }.get(request.method, "auth.change_group")
        return request.user.is_staff or request.user.has_perm(permission)


class UtilisateursViewSet(viewsets.ModelViewSet):
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
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def capabilities(self, request):
        return Response(
            permission_snapshot(
                request.user,
                getattr(request.tenant, "configuration_academique", {}),
            )
        )

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
        return Response({"detail": "Mot de passe modifié avec succès."})

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


class PermissionsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [CanManageAuthorization]
    serializer_class = PermissionSerializer
    queryset = Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename")
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["content_type__app_label"]
    search_fields = ["codename", "name"]


class GroupesPermissionsViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageAuthorization]
    serializer_class = GroupSerializer
    queryset = Group.objects.prefetch_related("permissions").order_by("name")
