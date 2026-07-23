"""API views for utilisateurs (ViewSets DRF) - SIS Supérieur."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Utilisateur
from .serializers import (
    UtilisateurListSerializer,
    UtilisateurDetailSerializer,
    UtilisateurCreateSerializer,
    ChangePasswordSerializer,
    UtilisateurProfileSerializer,
)


class UtilisateursViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour utilisateurs."""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['role', 'is_active', 'etablissement']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['username', 'last_name', 'date_joined']
    ordering = ['-date_joined']

    def get_queryset(self):
        """Filtre par établissement du tenant courant."""
        user = self.request.user
        qs = Utilisateur.objects.select_related('etablissement')
        
        # Les admins voient tous les utilisateurs de leur établissement
        if hasattr(user, 'etablissement') and user.etablissement:
            qs = qs.filter(etablissement=user.etablissement)
        
        # Les non-admins ne voient que leur propre profil
        if not user.is_staff and not getattr(user, 'is_admin', False):
            qs = qs.filter(pk=user.pk)
        
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return UtilisateurListSerializer
        elif self.action == 'create':
            return UtilisateurCreateSerializer
        elif self.action == 'me':
            return UtilisateurDetailSerializer
        elif self.action == 'update_profile':
            return UtilisateurProfileSerializer
        elif self.action == 'change_password':
            return ChangePasswordSerializer
        return UtilisateurDetailSerializer

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsAdminUser()]
        return super().get_permissions()

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Retourne le profil de l'utilisateur connecté."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """Met à jour le profil de l'utilisateur connecté."""
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change le mot de passe de l'utilisateur connecté."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': "Mot de passe actuel incorrect."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.doit_changer_mdp = False
        user.save()
        
        return Response({'detail': "Mot de passe modifié avec succès."})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def toggle_active(self, request, pk=None):
        """Active ou désactive un utilisateur."""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return Response({
            'id': user.id,
            'is_active': user.is_active,
            'detail': f"Utilisateur {'activé' if user.is_active else 'désactivé'}."
        })
