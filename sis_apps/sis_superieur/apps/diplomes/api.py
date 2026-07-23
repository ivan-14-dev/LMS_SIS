"""API views for diplomes (ViewSets DRF) - SIS Supérieur."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count
import uuid

from .models import Diplome, CessionDiplome
from .serializers import (
    DiplomeSerializer,
    CessionDiplomeListSerializer,
    CessionDiplomeDetailSerializer,
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
            'scolarite', 'responsable_formation', 'doyen', 'president_universite'
        )


class DiplomesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour types de diplômes."""
    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = DiplomeSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['formation', 'type', 'niveau_grade']
    search_fields = ['nom', 'code_rncp']
    ordering = ['niveau_grade', 'nom']

    def get_queryset(self):
        return Diplome.objects.select_related('formation').prefetch_related('cessions')

    @action(detail=True, methods=['get'])
    def cessions(self, request, pk=None):
        """Liste les cessions du diplôme."""
        diplome = self.get_object()
        cessions = diplome.cessions.select_related(
            'etudiant__user', 'annee_universitaire'
        ).order_by('-date_obtention')
        serializer = CessionDiplomeListSerializer(cessions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Statistiques du diplôme."""
        diplome = self.get_object()
        cessions = diplome.cessions.all()
        stats = {
            'total_delivres': cessions.count(),
        }
        by_annee = cessions.values('annee_universitaire__libelle').annotate(
            count=Count('id')
        )
        stats['par_annee'] = {a['annee_universitaire__libelle']: a['count'] for a in by_annee}
        by_mention = cessions.exclude(mention='').values('mention').annotate(
            count=Count('id')
        )
        stats['par_mention'] = {m['mention']: m['count'] for m in by_mention}
        return Response(stats)


class CessionsDiplomesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour cessions de diplômes."""
    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['diplome', 'annee_universitaire', 'etudiant']
    search_fields = ['etudiant__user__last_name', 'numero_serie']
    ordering = ['-date_obtention']

    def get_queryset(self):
        return CessionDiplome.objects.select_related(
            'etudiant__user', 'diplome', 'annee_universitaire', 'signe_par'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return CessionDiplomeListSerializer
        return CessionDiplomeDetailSerializer

    def perform_create(self, serializer):
        # Générer numéro de série unique
        numero_serie = f"DIP-{uuid.uuid4().hex[:8].upper()}"
        serializer.save(numero_serie=numero_serie)

    @action(detail=True, methods=['post'])
    def signer(self, request, pk=None):
        """Signe le diplôme."""
        cession = self.get_object()
        if cession.date_signature:
            return Response({'error': "Déjà signé."}, status=400)
        
        from django.utils import timezone
        cession.signe_par = request.user
        cession.date_signature = timezone.now()
        cession.qr_verification = f"https://verif.univ.fr/{cession.numero_serie}"
        cession.save(update_fields=['signe_par', 'date_signature', 'qr_verification'])
        return Response({'detail': "Diplôme signé.", 'id': cession.id})

    @action(detail=True, methods=['get'])
    def verifier(self, request, pk=None):
        """Vérifie l'authenticité du diplôme."""
        cession = self.get_object()
        return Response({
            'valide': cession.date_signature is not None,
            'etudiant': cession.etudiant.user.get_full_name(),
            'diplome': cession.diplome.nom,
            'date_obtention': cession.date_obtention,
            'mention': cession.mention,
            'signe_le': cession.date_signature,
        })
