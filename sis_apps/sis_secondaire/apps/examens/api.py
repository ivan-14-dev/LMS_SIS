"""API views for examens (ViewSets DRF) - SIS Secondaire."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Avg

from .models import SessionExamen, EpreuveExamen, ConvocationExamen, ResultatExamen
from .serializers import (
    SessionExamenSerializer,
    EpreuveExamenListSerializer,
    EpreuveExamenDetailSerializer,
    ConvocationExamenSerializer,
    ResultatExamenSerializer,
)


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        return user.is_staff or getattr(user, 'role', '') in (
            'scolarite', 'directeur', 'proviseur', 'principal'
        )


class SessionsExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour sessions d'examen."""
    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = SessionExamenSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['annee_scolaire', 'type']
    search_fields = ['nom']
    ordering = ['-date_debut']

    def get_queryset(self):
        return SessionExamen.objects.select_related('annee_scolaire').prefetch_related('epreuves')

    @action(detail=True, methods=['get'])
    def epreuves(self, request, pk=None):
        """Liste les épreuves de la session."""
        session = self.get_object()
        epreuves = session.epreuves.select_related('matiere').order_by('date', 'heure_debut')
        serializer = EpreuveExamenListSerializer(epreuves, many=True)
        return Response(serializer.data)


class EpreuvesExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour épreuves d'examen."""
    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['session', 'matiere', 'date']
    ordering = ['date', 'heure_debut']

    def get_queryset(self):
        return EpreuveExamen.objects.select_related(
            'session', 'matiere', 'salle_principale'
        ).prefetch_related('classes', 'surveillants')

    def get_serializer_class(self):
        if self.action == 'list':
            return EpreuveExamenListSerializer
        return EpreuveExamenDetailSerializer

    @action(detail=True, methods=['get'])
    def convocations(self, request, pk=None):
        """Liste les convocations de l'épreuve."""
        epreuve = self.get_object()
        convocations = epreuve.convocations.select_related('eleve__user').order_by('numero_place')
        serializer = ConvocationExamenSerializer(convocations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def resultats(self, request, pk=None):
        """Liste les résultats de l'épreuve."""
        epreuve = self.get_object()
        resultats = epreuve.resultats.select_related('eleve__user').order_by('-note')
        serializer = ResultatExamenSerializer(resultats, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Statistiques de l'épreuve."""
        epreuve = self.get_object()
        resultats = epreuve.resultats.all()
        stats = resultats.aggregate(moyenne=Avg('note'))
        stats['nb_inscrits'] = epreuve.convocations.count()
        stats['nb_presents'] = epreuve.convocations.filter(statut='present').count()
        stats['nb_absents'] = epreuve.convocations.filter(statut='absent').count()
        stats['nb_notes'] = resultats.exclude(note__isnull=True).count()
        return Response(stats)


class ConvocationsExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour convocations."""
    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = ConvocationExamenSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['epreuve', 'eleve', 'statut']
    ordering = ['numero_place']

    def get_queryset(self):
        return ConvocationExamen.objects.select_related('epreuve__matiere', 'eleve__user')

    @action(detail=True, methods=['post'])
    def marquer_present(self, request, pk=None):
        """Marque l'élève comme présent."""
        convocation = self.get_object()
        convocation.statut = 'present'
        convocation.save(update_fields=['statut'])
        return Response({'detail': "Marqué présent.", 'id': convocation.id})

    @action(detail=True, methods=['post'])
    def marquer_absent(self, request, pk=None):
        """Marque l'élève comme absent."""
        convocation = self.get_object()
        convocation.statut = 'absent'
        convocation.save(update_fields=['statut'])
        return Response({'detail': "Marqué absent.", 'id': convocation.id})


class ResultatsExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour résultats d'examen."""
    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = ResultatExamenSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['epreuve', 'eleve', 'admis']
    ordering = ['-note']

    def get_queryset(self):
        return ResultatExamen.objects.select_related('epreuve__matiere', 'eleve__user')
