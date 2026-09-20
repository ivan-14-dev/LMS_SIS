"""API views for utilisateurs (ViewSets DRF) - SIS Secondaire."""

from django.contrib.auth.models import Group, Permission
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import permission_snapshot

from .models import Utilisateur
from .serializers import (
    ChangePasswordSerializer,
    UtilisateurCreateSerializer,
    UtilisateurDetailSerializer,
    UtilisateurListSerializer,
    UtilisateurProfileSerializer,
    GroupSerializer,
    PermissionSerializer,
)


class IsDirectionOrReadOnly(IsAuthenticated):
    """Permission: direction pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "directeur",
            "proviseur",
            "principal",
        )


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

        # Exclure les superusers pour les non-superusers
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
        return Response(permission_snapshot(request.user))

    @action(detail=False, methods=["patch"])
    def update_profile(self, request):
        """Met à jour le profil de l'utilisateur connecté."""
        serializer = UtilisateurProfileSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        """Change le mot de passe de l'utilisateur connecté."""
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
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
    permission_classes = [IsAdminUser]
    serializer_class = PermissionSerializer
    queryset = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label", "codename"
    )
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["content_type__app_label"]
    search_fields = ["codename", "name"]


class GroupesPermissionsViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = GroupSerializer
    queryset = Group.objects.prefetch_related("permissions").order_by("name")
