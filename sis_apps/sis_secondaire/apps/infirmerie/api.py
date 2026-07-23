"""API views for infirmerie (ViewSets DRF) - SIS Secondaire."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Q, F
from django.utils import timezone

from .models import DossierMedical, VisiteInfirmerie, StockMedicament
from .serializers import (
    DossierMedicalSerializer,
    VisiteInfirmerieListSerializer,
    VisiteInfirmerieDetailSerializer,
    StockMedicamentSerializer,
)


class IsInfirmierOrReadRestricted(IsAuthenticated):
    """Permission: accès restreint pour l'infirmerie."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        # Seuls les infirmiers et la direction ont accès
        return user.is_staff or getattr(user, 'role', '') in (
            'infirmier', 'medecin', 'directeur', 'proviseur', 'principal'
        )


class DossiersMedicauxViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour dossiers médicaux (accès restreint)."""
    permission_classes = [IsInfirmierOrReadRestricted]
    serializer_class = DossierMedicalSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['eleve']
    search_fields = ['eleve__user__last_name', 'eleve__matricule']

    def get_queryset(self):
        return DossierMedical.objects.select_related(
            'eleve__user', 'eleve__classe'
        )

    @action(detail=True, methods=['get'])
    def visites(self, request, pk=None):
        """Liste les visites de l'élève."""
        dossier = self.get_object()
        visites = dossier.eleve.visites_infirmerie.all().order_by('-date')
        serializer = VisiteInfirmerieListSerializer(visites, many=True)
        return Response(serializer.data)


class VisitesInfirmerieViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour visites infirmerie."""
    permission_classes = [IsInfirmierOrReadRestricted]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['eleve', 'orientation', 'infirmier']
    search_fields = ['motif', 'eleve__user__last_name', 'eleve__matricule']
    ordering_fields = ['date', 'heure_arrivee']
    ordering = ['-date', '-heure_arrivee']

    def get_queryset(self):
        return VisiteInfirmerie.objects.select_related(
            'eleve__user', 'eleve__classe', 'infirmier'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return VisiteInfirmerieListSerializer
        return VisiteInfirmerieDetailSerializer

    def perform_create(self, serializer):
        # L'infirmier connecté est l'infirmier par défaut
        serializer.save(infirmier=self.request.user)

    @action(detail=True, methods=['post'])
    def prevenir_parents(self, request, pk=None):
        """Notifie que les parents ont été prévenus."""
        visite = self.get_object()
        if visite.parents_prevenus:
            return Response({'error': "Les parents ont déjà été prévenus."}, status=400)
        visite.parents_prevenus = True
        visite.save(update_fields=['parents_prevenus'])
        return Response({'detail': "Parents prévenus.", 'id': visite.id})

    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """Statistiques des visites."""
        qs = self.get_queryset()
        today = timezone.now().date()
        stats = {
            'total': qs.count(),
            'aujourdhui': qs.filter(date__date=today).count(),
        }
        by_orientation = qs.values('orientation').annotate(count=Count('id'))
        stats['par_orientation'] = {o['orientation']: o['count'] for o in by_orientation}
        return Response(stats)


class StockMedicamentsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour stock médicaments."""
    permission_classes = [IsInfirmierOrReadRestricted]
    serializer_class = StockMedicamentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['nom', 'description']
    ordering = ['nom']

    def get_queryset(self):
        return StockMedicament.objects.all()

    @action(detail=False, methods=['get'])
    def en_alerte(self, request):
        """Liste les médicaments en alerte stock."""
        qs = self.get_queryset().filter(quantite__lte=F('seuil_alerte'))
        serializer = StockMedicamentSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def perimes(self, request):
        """Liste les médicaments périmés."""
        today = timezone.now().date()
        qs = self.get_queryset().filter(date_peremption__lt=today)
        serializer = StockMedicamentSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def ajuster_stock(self, request, pk=None):
        """Ajuste le stock d'un médicament."""
        medicament = self.get_object()
        delta = request.data.get('delta', 0)
        try:
            delta = int(delta)
        except ValueError:
            return Response({'error': "Delta doit être un entier."}, status=400)
        
        medicament.quantite = max(0, medicament.quantite + delta)
        medicament.save(update_fields=['quantite', 'updated_at'])
        return Response({
            'id': medicament.id,
            'nouvelle_quantite': medicament.quantite,
        })
