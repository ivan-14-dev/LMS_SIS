"""API views for recherche (ViewSets DRF) - SIS Supérieur."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Sum

from .models import Laboratoire, ProjetRecherche, ProductionScientifique, These
from .serializers import (
    LaboratoireListSerializer,
    LaboratoireDetailSerializer,
    ProjetRechercheListSerializer,
    ProjetRechercheDetailSerializer,
    ProductionScientifiqueSerializer,
    TheseListSerializer,
    TheseDetailSerializer,
)


class IsRechercheOrReadOnly(IsAuthenticated):
    """Permission: recherche/direction pour écriture."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        return user.is_staff or getattr(user, 'role', '') in (
            'recherche', 'directeur_laboratoire', 'vice_president_recherche', 'doyen'
        )


class LaboratoiresViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour laboratoires."""
    permission_classes = [IsRechercheOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['faculte', 'type', 'directeur']
    search_fields = ['nom', 'acronyme']
    ordering = ['nom']

    def get_queryset(self):
        return Laboratoire.objects.select_related(
            'faculte', 'directeur__user'
        ).prefetch_related('projets', 'theses')

    def get_serializer_class(self):
        if self.action == 'list':
            return LaboratoireListSerializer
        return LaboratoireDetailSerializer

    @action(detail=True, methods=['get'])
    def projets(self, request, pk=None):
        """Liste les projets du laboratoire."""
        labo = self.get_object()
        projets = labo.projets.select_related('responsable__user').order_by('-date_debut')
        serializer = ProjetRechercheListSerializer(projets, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def theses(self, request, pk=None):
        """Liste les thèses du laboratoire."""
        labo = self.get_object()
        theses = labo.theses.select_related('doctorant__user', 'directeur__user')
        serializer = TheseListSerializer(theses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def productions(self, request, pk=None):
        """Liste les productions du laboratoire."""
        labo = self.get_object()
        productions = labo.productions.prefetch_related('auteurs').order_by('-annee')
        serializer = ProductionScientifiqueSerializer(productions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Statistiques du laboratoire."""
        labo = self.get_object()
        return Response({
            'nb_projets': labo.projets.count(),
            'nb_projets_en_cours': labo.projets.filter(statut='en_cours').count(),
            'nb_theses': labo.theses.count(),
            'nb_theses_en_cours': labo.theses.filter(statut='en_cours').count(),
            'nb_publications': labo.productions.count(),
            'budget_total': labo.projets.aggregate(total=Sum('budget'))['total'] or 0,
        })


class ProjetsRechercheViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour projets de recherche."""
    permission_classes = [IsRechercheOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['laboratoire', 'responsable', 'statut', 'financeur']
    search_fields = ['titre', 'acronyme', 'description']
    ordering = ['-date_debut']

    def get_queryset(self):
        return ProjetRecherche.objects.select_related(
            'laboratoire', 'responsable__user'
        ).prefetch_related('membres')

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjetRechercheListSerializer
        return ProjetRechercheDetailSerializer

    @action(detail=True, methods=['post'])
    def demarrer(self, request, pk=None):
        """Démarre le projet."""
        projet = self.get_object()
        if projet.statut != 'accepte':
            return Response({'error': "Le projet doit être accepté."}, status=400)
        projet.statut = 'en_cours'
        projet.save(update_fields=['statut'])
        return Response({'detail': "Projet démarré.", 'id': projet.id})

    @action(detail=True, methods=['post'])
    def terminer(self, request, pk=None):
        """Termine le projet."""
        projet = self.get_object()
        projet.statut = 'termine'
        projet.save(update_fields=['statut'])
        return Response({'detail': "Projet terminé.", 'id': projet.id})


class ProductionsScientifiquesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour productions scientifiques."""
    permission_classes = [IsRechercheOrReadOnly]
    serializer_class = ProductionScientifiqueSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['laboratoire', 'projet', 'type', 'annee']
    search_fields = ['titre', 'doi']
    ordering = ['-annee', '-created_at']

    def get_queryset(self):
        return ProductionScientifique.objects.select_related(
            'laboratoire', 'projet'
        ).prefetch_related('auteurs')

    @action(detail=False, methods=['get'])
    def par_annee(self, request):
        """Statistiques par année."""
        stats = self.get_queryset().values('annee').annotate(
            count=Count('id')
        ).order_by('-annee')
        return Response(list(stats))


class ThesesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour thèses."""
    permission_classes = [IsRechercheOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['laboratoire', 'directeur', 'statut', 'financement']
    search_fields = ['titre', 'doctorant__user__last_name', 'mots_cles']
    ordering = ['-date_debut']

    def get_queryset(self):
        return These.objects.select_related(
            'laboratoire', 'doctorant__user', 'directeur__user', 'co_directeur__user'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return TheseListSerializer
        return TheseDetailSerializer

    @action(detail=True, methods=['post'])
    def soutenir(self, request, pk=None):
        """Marque la thèse comme soutenue."""
        these = self.get_object()
        date_soutenance = request.data.get('date_soutenance')
        if not date_soutenance:
            return Response({'error': "Date de soutenance requise."}, status=400)
        these.statut = 'soutenue'
        these.date_soutenance = date_soutenance
        these.save(update_fields=['statut', 'date_soutenance'])
        return Response({'detail': "Thèse soutenue.", 'id': these.id})
