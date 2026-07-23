"""API views for enseignants (ViewSets DRF) - SIS Secondaire."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Sum

from .models import Personnel, MatiereEnseignee, AffectationEnseignant
from .serializers import (
    PersonnelListSerializer,
    PersonnelDetailSerializer,
    PersonnelCreateSerializer,
    MatiereEnseigneeSerializer,
    AffectationEnseignantSerializer,
)


class IsDirectionOrReadOnly(IsAuthenticated):
    """Permission: direction pour écriture, authentifié pour lecture."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        return user.is_staff or getattr(user, 'role', '') in (
            'directeur', 'proviseur', 'principal'
        )


class PersonnelViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour personnel."""
    permission_classes = [IsDirectionOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['statut', 'user__role']
    search_fields = ['matricule', 'user__first_name', 'user__last_name', 'user__email', 'corps']
    ordering_fields = ['user__last_name', 'date_embauche', 'created_at']
    ordering = ['user__last_name', 'user__first_name']

    def get_queryset(self):
        qs = Personnel.objects.select_related('user')
        # Filtrer par établissement du tenant
        if hasattr(self.request, 'tenant'):
            qs = qs.filter(user__etablissement=self.request.tenant)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return PersonnelListSerializer
        elif self.action == 'create':
            return PersonnelCreateSerializer
        return PersonnelDetailSerializer

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Retourne le profil personnel de l'utilisateur connecté."""
        try:
            personnel = Personnel.objects.get(user=request.user)
            serializer = PersonnelDetailSerializer(personnel)
            return Response(serializer.data)
        except Personnel.DoesNotExist:
            return Response({'error': "Vous n'êtes pas membre du personnel."}, status=404)

    @action(detail=False, methods=['get'])
    def enseignants(self, request):
        """Liste uniquement les enseignants."""
        qs = self.get_queryset().filter(user__role='enseignant')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = PersonnelListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = PersonnelListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def matieres(self, request, pk=None):
        """Liste les matières enseignées par ce personnel."""
        personnel = self.get_object()
        matieres = personnel.matieres_enseignees.select_related('matiere')
        serializer = MatiereEnseigneeSerializer(matieres, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def affectations(self, request, pk=None):
        """Liste les affectations de ce personnel."""
        personnel = self.get_object()
        affectations = personnel.affectations.select_related(
            'matiere', 'annee_scolaire'
        ).prefetch_related('classes').order_by('-annee_scolaire__date_debut')
        serializer = AffectationEnseignantSerializer(affectations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def heures_total(self, request, pk=None):
        """Calcule le total des heures d'enseignement."""
        personnel = self.get_object()
        annee_id = request.query_params.get('annee')
        qs = personnel.affectations.all()
        if annee_id:
            qs = qs.filter(annee_scolaire_id=annee_id)
        total = qs.aggregate(total=Sum('heures_semaine'))['total'] or 0
        return Response({
            'personnel_id': personnel.id,
            'heures_contractuelles': float(personnel.heures_contractuelles),
            'heures_affectees': float(total),
            'ecart': float(total) - float(personnel.heures_contractuelles),
        })


class MatiereEnseigneeViewSet(viewsets.ModelViewSet):
    """ViewSet pour les matières enseignées."""
    permission_classes = [IsDirectionOrReadOnly]
    serializer_class = MatiereEnseigneeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['enseignant', 'matiere']

    def get_queryset(self):
        return MatiereEnseignee.objects.select_related('enseignant__user', 'matiere')


class AffectationEnseignantViewSet(viewsets.ModelViewSet):
    """ViewSet pour les affectations enseignant."""
    permission_classes = [IsDirectionOrReadOnly]
    serializer_class = AffectationEnseignantSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['enseignant', 'matiere', 'annee_scolaire']
    ordering = ['-annee_scolaire__date_debut']

    def get_queryset(self):
        return AffectationEnseignant.objects.select_related(
            'enseignant__user', 'matiere', 'annee_scolaire'
        ).prefetch_related('classes')
