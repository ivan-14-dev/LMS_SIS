"""API views for utilisateurs (ViewSets DRF) - SIS Supérieur."""

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


class CanManageUsers(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if view.action in ("me", "capabilities", "update_profile", "change_password"):
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        permission = {
            "create": "utilisateurs.add_utilisateur",
            "destroy": "utilisateurs.delete_utilisateur",
        }.get(view.action, "utilisateurs.change_utilisateur")
        return has_business_permission_or_role(
            request.user,
            permission,
            (
                "president",
                "vice_president",
                "doyen",
                "directeur_etudes",
                "scolarite",
            ),
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

    permission_classes = [CanManageUsers]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["role", "is_active", "etablissement"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "last_name", "date_joined"]
    ordering = ["-date_joined"]

    def get_queryset(self):
        """Filtre par établissement du tenant courant."""
        user = self.request.user
        qs = Utilisateur.objects.select_related("etablissement")

        # Les admins voient tous les utilisateurs de leur établissement
        if hasattr(user, "etablissement") and user.etablissement:
            qs = qs.filter(etablissement=user.etablissement)

        can_list = has_business_permission_or_role(
            user,
            "utilisateurs.view_utilisateur",
            (
                "president",
                "vice_president",
                "doyen",
                "directeur_etudes",
                "scolarite",
            ),
        )
        if not can_list:
            qs = qs.filter(pk=user.pk)

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return UtilisateurListSerializer
        elif self.action == "create":
            return UtilisateurCreateSerializer
        elif self.action == "me":
            return UtilisateurDetailSerializer
        elif self.action == "update_profile":
            return UtilisateurProfileSerializer
        elif self.action == "change_password":
            return ChangePasswordSerializer
        return UtilisateurDetailSerializer

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Retourne le profil de l'utilisateur connecté."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def capabilities(self, request):
        return Response(permission_snapshot(request.user))

    @action(detail=False, methods=["patch"])
    def update_profile(self, request):
        """Met à jour le profil de l'utilisateur connecté."""
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        """Change le mot de passe de l'utilisateur connecté."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": "Mot de passe actuel incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.doit_changer_mdp = False
        user.save()

        return Response({"detail": "Mot de passe modifié avec succès."})

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        """Active ou désactive un utilisateur."""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response(
            {
                "id": user.id,
                "is_active": user.is_active,
                "detail": f"Utilisateur {'activé' if user.is_active else 'désactivé'}.",
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
