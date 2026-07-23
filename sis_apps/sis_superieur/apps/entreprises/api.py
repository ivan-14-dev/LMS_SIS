"""API views for entreprises (ViewSets DRF) - SIS Supérieur."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count

from .models import Entreprise, ContactEntreprise
from .serializers import (
    EntrepriseListSerializer,
    EntrepriseDetailSerializer,
    ContactEntrepriseSerializer,
)


class IsRelationsEntreprisesOrReadOnly(IsAuthenticated):
    """Permission: relations entreprises pour écriture."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        return user.is_staff or getattr(user, 'role', '') in (
            'relations_entreprises', 'scolarite', 'responsable_formation', 'doyen'
        )


class EntreprisesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour entreprises."""
    permission_classes = [IsRelationsEntreprisesOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['type', 'secteur', 'pays', 'actif']
    search_fields = ['raison_sociale', 'siret', 'ville', 'description']
    ordering_fields = ['raison_sociale', 'cree_le']
    ordering = ['raison_sociale']

    def get_queryset(self):
        return Entreprise.objects.prefetch_related('contacts', 'offres_stage')

    def get_serializer_class(self):
        if self.action == 'list':
            return EntrepriseListSerializer
        return EntrepriseDetailSerializer

    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """Liste les contacts de l'entreprise."""
        entreprise = self.get_object()
        contacts = entreprise.contacts.filter(actif=True).order_by('nom')
        serializer = ContactEntrepriseSerializer(contacts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def offres(self, request, pk=None):
        """Liste les offres de stage de l'entreprise."""
        entreprise = self.get_object()
        from apps.stages.serializers import OffreStageListSerializer
        offres = entreprise.offres_stage.all().order_by('-created_at')
        serializer = OffreStageListSerializer(offres, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def conventions(self, request, pk=None):
        """Liste les conventions avec l'entreprise."""
        entreprise = self.get_object()
        from apps.stages.serializers import ConventionStageListSerializer
        conventions = entreprise.conventions.select_related('etudiant__user', 'offre')
        serializer = ConventionStageListSerializer(conventions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """Statistiques des entreprises."""
        qs = self.get_queryset()
        stats = {
            'total': qs.count(),
            'actives': qs.filter(actif=True).count(),
        }
        by_secteur = qs.values('secteur').annotate(count=Count('id'))
        stats['par_secteur'] = {s['secteur']: s['count'] for s in by_secteur}
        by_type = qs.values('type').annotate(count=Count('id'))
        stats['par_type'] = {t['type']: t['count'] for t in by_type}
        return Response(stats)


class ContactsEntrepriseViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour contacts."""
    permission_classes = [IsRelationsEntreprisesOrReadOnly]
    serializer_class = ContactEntrepriseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['entreprise', 'role', 'actif']
    search_fields = ['nom', 'prenom', 'email', 'fonction']
    ordering = ['nom', 'prenom']

    def get_queryset(self):
        return ContactEntreprise.objects.select_related('entreprise')
