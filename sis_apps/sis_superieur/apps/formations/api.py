"""API views for formations (ViewSets DRF) - SIS Supérieur."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Formation, Parcours, MaquetteFormation
from .serializers import (
    FormationListSerializer,
    FormationDetailSerializer,
    ParcoursSerializer,
    MaquetteFormationSerializer,
)


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture, authentifié pour lecture."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        return user.is_staff or getattr(user, 'role', '') in (
            'scolarite', 'directeur_etudes', 'responsable_formation', 'doyen'
        )


class FormationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour formations."""
    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['type', 'niveau', 'departement', 'regime', 'actif']
    search_fields = ['code', 'nom', 'description']
    ordering_fields = ['code', 'nom', 'type', 'created_at']
    ordering = ['code']

    def get_queryset(self):
        return Formation.objects.select_related(
            'departement', 'ecole_doctorale', 'responsable'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return FormationListSerializer
        return FormationDetailSerializer

    @action(detail=True, methods=['get'])
    def parcours(self, request, pk=None):
        """Liste les parcours de la formation."""
        formation = self.get_object()
        parcours = formation.parcours.all()
        serializer = ParcoursSerializer(parcours, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def maquettes(self, request, pk=None):
        """Liste les maquettes de la formation."""
        formation = self.get_object()
        maquettes = formation.maquettes.select_related('annee_universitaire')
        serializer = MaquetteFormationSerializer(maquettes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Statistiques de la formation."""
        formation = self.get_object()
        # Compter les étudiants inscrits via InscriptionAdministrative
        from apps.etudiants.models import InscriptionAdministrative
        nb_inscrits = InscriptionAdministrative.objects.filter(
            formation=formation, statut='validee'
        ).count()
        return Response({
            'formation_id': formation.id,
            'nb_parcours': formation.parcours.count(),
            'nb_inscrits': nb_inscrits,
            'credits_total': formation.credits_total,
            'duree_annees': formation.duree_annees,
        })


class ParcoursViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour parcours."""
    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = ParcoursSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['formation']
    search_fields = ['code', 'nom', 'specialisation']

    def get_queryset(self):
        return Parcours.objects.select_related('formation')


class MaquettesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour maquettes de formation."""
    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = MaquetteFormationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['formation', 'annee_universitaire', 'statut']

    def get_queryset(self):
        return MaquetteFormation.objects.select_related(
            'formation', 'annee_universitaire'
        )
