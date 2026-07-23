"""API views for notes (ViewSets DRF) - SIS Supérieur."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import Evaluation, Note, MoyenneECUE, MoyenneUE
from .serializers import (
    EvaluationListSerializer,
    EvaluationDetailSerializer,
    NoteSerializer,
    NoteSaisieSerializer,
    MoyenneECUESerializer,
    MoyenneUESerializer,
)


class IsEnseignantOrScolarite(IsAuthenticated):
    """Permission: enseignant ou scolarité."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        return user.is_staff or getattr(user, 'role', '') in (
            'enseignant', 'scolarite', 'directeur_etudes'
        )


class EvaluationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour évaluations."""
    permission_classes = [IsEnseignantOrScolarite]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['ecue', 'semestre', 'modalite', 'enseignant', 'anonyme']
    search_fields = ['titre', 'description']
    ordering_fields = ['date', 'titre', 'created_at']
    ordering = ['-date']

    def get_queryset(self):
        return Evaluation.objects.select_related('ecue', 'semestre', 'enseignant')

    def get_serializer_class(self):
        if self.action == 'list':
            return EvaluationListSerializer
        return EvaluationDetailSerializer

    @action(detail=True, methods=['get'])
    def notes(self, request, pk=None):
        """Liste les notes d'une évaluation."""
        evaluation = self.get_object()
        notes = evaluation.notes.select_related('etudiant__user').order_by('etudiant__user__last_name')
        serializer = NoteSerializer(notes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def saisir_notes(self, request, pk=None):
        """Saisie en masse des notes."""
        evaluation = self.get_object()
        serializer = NoteSaisieSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        
        created = 0
        updated = 0
        for item in serializer.validated_data:
            note, was_created = Note.objects.update_or_create(
                evaluation=evaluation,
                etudiant_id=item['etudiant_id'],
                defaults={
                    'valeur': item['valeur'],
                    'statut': item.get('statut', 'presente'),
                    'appreciation': item.get('appreciation', ''),
                    'saisi_par': request.user,
                    'modifie_le': timezone.now() if not was_created else None,
                    'modifie_par': request.user if not was_created else None,
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1
        
        return Response({
            'evaluation_id': evaluation.id,
            'notes_creees': created,
            'notes_modifiees': updated,
        })

    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Statistiques de l'évaluation."""
        evaluation = self.get_object()
        notes = evaluation.notes.filter(valeur__isnull=False)
        stats = notes.aggregate(
            moyenne=Avg('valeur'),
            nb_notes=Count('id'),
        )
        absents = evaluation.notes.filter(statut='absente').count()
        return Response({
            'evaluation_id': evaluation.id,
            'moyenne': float(stats['moyenne']) if stats['moyenne'] else None,
            'nb_notes': stats['nb_notes'],
            'nb_absents': absents,
            'bareme': float(evaluation.bareme),
        })


class NotesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour notes."""
    permission_classes = [IsEnseignantOrScolarite]
    serializer_class = NoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['evaluation', 'etudiant', 'statut']
    ordering = ['etudiant__user__last_name']

    def get_queryset(self):
        qs = Note.objects.select_related('evaluation', 'etudiant__user')
        # Un étudiant ne voit que ses propres notes
        user = self.request.user
        if hasattr(user, 'etudiant_profile'):
            if not user.is_staff and getattr(user, 'role', '') == 'etudiant':
                qs = qs.filter(etudiant__user=user)
        return qs


class MoyennesECUEViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet lecture seule pour moyennes ECUE."""
    permission_classes = [IsAuthenticated]
    serializer_class = MoyenneECUESerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['etudiant', 'ecue', 'semestre', 'valide']

    def get_queryset(self):
        qs = MoyenneECUE.objects.select_related('etudiant__user', 'ecue', 'semestre')
        user = self.request.user
        if hasattr(user, 'etudiant_profile'):
            if not user.is_staff and getattr(user, 'role', '') == 'etudiant':
                qs = qs.filter(etudiant__user=user)
        return qs


class MoyennesUEViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet lecture seule pour moyennes UE."""
    permission_classes = [IsAuthenticated]
    serializer_class = MoyenneUESerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['etudiant', 'ue', 'semestre', 'capitalisee']

    def get_queryset(self):
        qs = MoyenneUE.objects.select_related('etudiant__user', 'ue', 'semestre')
        user = self.request.user
        if hasattr(user, 'etudiant_profile'):
            if not user.is_staff and getattr(user, 'role', '') == 'etudiant':
                qs = qs.filter(etudiant__user=user)
        return qs
