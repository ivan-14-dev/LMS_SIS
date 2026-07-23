"""API views for evaluations (SIS Secondaire).

Note: Complète le module notes avec des vues spécialisées
pour différents types d'évaluations.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db.models import Avg

from apps.notes.models import Note
from .serializers import EvaluationSerializer


class IsEnseignantOrScolarite(IsAuthenticated):
    """Permission: enseignant ou scolarité."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        return (
            user.is_staff or
            hasattr(user, 'enseignant_secondaire') or
            getattr(user, 'role', '') in ('scolarite', 'directeur', 'proviseur')
        )


class EvaluationsViewSet(viewsets.ModelViewSet):
    """ViewSet pour les évaluations."""
    permission_classes = [IsEnseignantOrScolarite]
    serializer_class = EvaluationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['eleve', 'matiere', 'type_evaluation', 'periode']
    ordering = ['-date']

    def get_queryset(self):
        return Note.objects.select_related(
            'eleve__user', 'matiere', 'periode'
        )

    @action(detail=False, methods=['get'])
    def par_classe(self, request):
        """Évaluations d'une classe."""
        classe_id = request.query_params.get('classe_id')
        if not classe_id:
            return Response({'error': 'classe_id requis.'}, status=400)
        
        evaluations = self.get_queryset().filter(
            eleve__classe_id=classe_id
        ).order_by('-date')[:100]
        
        serializer = self.get_serializer(evaluations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """Statistiques des évaluations."""
        classe_id = request.query_params.get('classe_id')
        matiere_id = request.query_params.get('matiere_id')
        
        queryset = self.get_queryset()
        if classe_id:
            queryset = queryset.filter(eleve__classe_id=classe_id)
        if matiere_id:
            queryset = queryset.filter(matiere_id=matiere_id)
        
        stats = queryset.aggregate(
            moyenne=Avg('note'),
        )
        stats['nb_evaluations'] = queryset.count()
        
        return Response(stats)
