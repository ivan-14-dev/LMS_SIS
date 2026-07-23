"""API views for etablissement (ViewSets DRF) - SIS Secondaire."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Etablissement, AnneeScolaire, Periode, Niveau
from .serializers import (
    EtablissementSerializer,
    AnneeScolaireSerializer,
    PeriodeSerializer,
)


class IsAdminOrReadOnly(IsAuthenticated):
    """Permission: admin pour écriture."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.is_staff


class EtablissementsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour établissements."""
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = EtablissementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['type', 'pays', 'actif']
    search_fields = ['nom', 'uai', 'ville']
    ordering = ['nom']

    def get_queryset(self):
        return Etablissement.objects.prefetch_related('annees_scolaires')

    @action(detail=True, methods=['get'])
    def annees(self, request, pk=None):
        """Liste les années scolaires."""
        etablissement = self.get_object()
        annees = etablissement.annees_scolaires.all().order_by('-date_debut')
        serializer = AnneeScolaireSerializer(annees, many=True)
        return Response(serializer.data)


class AnneesScolairesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour années scolaires."""
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = AnneeScolaireSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['etablissement', 'en_cours', 'cloturee']
    ordering = ['-date_debut']

    def get_queryset(self):
        return AnneeScolaire.objects.select_related('etablissement')

    @action(detail=True, methods=['get'])
    def periodes(self, request, pk=None):
        """Liste les périodes de l'année."""
        annee = self.get_object()
        periodes = annee.periodes.all().order_by('numero')
        serializer = PeriodeSerializer(periodes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activer(self, request, pk=None):
        """Active l'année scolaire."""
        annee = self.get_object()
        # Désactiver les autres années du même établissement
        AnneeScolaire.objects.filter(
            etablissement=annee.etablissement,
            en_cours=True
        ).exclude(pk=annee.pk).update(en_cours=False)
        
        annee.en_cours = True
        annee.save(update_fields=['en_cours'])
        return Response({'detail': "Année activée.", 'id': annee.id})

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """Clôture l'année scolaire."""
        annee = self.get_object()
        if annee.cloturee:
            return Response({'error': "Année déjà clôturée."}, status=400)
        annee.cloturee = True
        annee.en_cours = False
        annee.save(update_fields=['cloturee', 'en_cours'])
        return Response({'detail': "Année clôturée.", 'id': annee.id})


class PeriodesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour périodes."""
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = PeriodeSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['annee_scolaire', 'type', 'cloture']
    ordering = ['annee_scolaire', 'numero']

    def get_queryset(self):
        return Periode.objects.select_related('annee_scolaire')

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """Clôture la période."""
        periode = self.get_object()
        if periode.cloture:
            return Response({'error': "Période déjà clôturée."}, status=400)
        periode.cloture = True
        periode.save(update_fields=['cloture'])
        return Response({'detail': "Période clôturée.", 'id': periode.id})


class NiveauxViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour niveaux."""
    permission_classes = [IsAdminOrReadOnly]
    
    def get_queryset(self):
        return Niveau.objects.all().order_by('cycle', 'code')
    
    def list(self, request):
        niveaux = self.get_queryset()
        data = [{
            "id": n.id,
            "code": n.code,
            "libelle": n.libelle,
            "cycle": n.cycle,
        } for n in niveaux]
        return Response(data)
