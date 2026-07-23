"""API views for discipline (ViewSets DRF) - SIS Secondaire."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Q
from django.utils import timezone

from .models import Incident, Sanction, ConseilDiscipline
from .serializers import (
    IncidentListSerializer,
    IncidentDetailSerializer,
    SanctionSerializer,
    ConseilDisciplineListSerializer,
    ConseilDisciplineDetailSerializer,
)


class IsVieScolariteOrReadOnly(IsAuthenticated):
    """Permission: vie scolaire pour écriture."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        # Les parents/élèves n'ont pas accès
        user = request.user
        role = getattr(user, 'role', '')
        if role in ('eleve', 'parent', 'tuteur'):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return user.is_staff or role in (
            'vie_scolaire', 'cpe', 'directeur', 'proviseur', 'principal', 'enseignant'
        )


class IncidentsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour incidents."""
    permission_classes = [IsVieScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['eleve', 'type', 'gravite', 'statut', 'rapporteur']
    search_fields = ['description', 'eleve__user__last_name', 'eleve__matricule']
    ordering_fields = ['date_incident', 'gravite']
    ordering = ['-date_incident']

    def get_queryset(self):
        return Incident.objects.select_related(
            'eleve__user', 'eleve__classe', 'rapporteur__user'
        ).prefetch_related('temoins__user')

    def get_serializer_class(self):
        if self.action == 'list':
            return IncidentListSerializer
        return IncidentDetailSerializer

    def perform_create(self, serializer):
        # L'enseignant connecté est le rapporteur par défaut
        rapporteur = None
        if hasattr(self.request.user, 'personnel_profile'):
            rapporteur = self.request.user.personnel_profile
        serializer.save(rapporteur=rapporteur)

    @action(detail=True, methods=['get'])
    def sanctions(self, request, pk=None):
        """Liste les sanctions liées à l'incident."""
        incident = self.get_object()
        sanctions = incident.sanctions.all().order_by('-date_effet')
        serializer = SanctionSerializer(sanctions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def classer(self, request, pk=None):
        """Classe un incident sans suite."""
        incident = self.get_object()
        if incident.statut not in ('ouvert', 'en_instruction'):
            return Response({'error': "L'incident est déjà traité."}, status=400)
        incident.statut = 'classe'
        incident.save(update_fields=['statut', 'updated_at'])
        return Response({'detail': "Incident classé sans suite.", 'id': incident.id})

    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """Statistiques des incidents."""
        qs = self.get_queryset()
        stats = {
            'total': qs.count(),
            'ouverts': qs.filter(statut='ouvert').count(),
            'en_instruction': qs.filter(statut='en_instruction').count(),
            'sanctionnes': qs.filter(statut='sanctionne').count(),
            'classes': qs.filter(statut='classe').count(),
        }
        # Par type
        by_type = qs.values('type').annotate(count=Count('id'))
        stats['par_type'] = {t['type']: t['count'] for t in by_type}
        # Par gravité
        by_gravite = qs.values('gravite').annotate(count=Count('id'))
        stats['par_gravite'] = {g['gravite']: g['count'] for g in by_gravite}
        return Response(stats)


class SanctionsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour sanctions."""
    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = SanctionSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['incident', 'type', 'executee']
    ordering = ['-date_effet']

    def get_queryset(self):
        return Sanction.objects.select_related('incident__eleve__user')

    def perform_create(self, serializer):
        sanction = serializer.save()
        # Mettre à jour le statut de l'incident
        incident = sanction.incident
        if incident.statut in ('ouvert', 'en_instruction'):
            incident.statut = 'sanctionne'
            incident.save(update_fields=['statut', 'updated_at'])

    @action(detail=True, methods=['post'])
    def notifier_parents(self, request, pk=None):
        """Notifie les parents de la sanction."""
        sanction = self.get_object()
        if sanction.notifiee_parents:
            return Response({'error': "Les parents ont déjà été notifiés."}, status=400)
        
        # TODO: Envoyer la notification par email/SMS
        sanction.notifiee_parents = True
        sanction.date_notification = timezone.now()
        sanction.save(update_fields=['notifiee_parents', 'date_notification'])
        return Response({'detail': "Parents notifiés.", 'id': sanction.id})

    @action(detail=True, methods=['post'])
    def executer(self, request, pk=None):
        """Marque la sanction comme exécutée."""
        sanction = self.get_object()
        if sanction.executee:
            return Response({'error': "La sanction est déjà exécutée."}, status=400)
        sanction.executee = True
        sanction.save(update_fields=['executee'])
        return Response({'detail': "Sanction exécutée.", 'id': sanction.id})


class ConseilsDisciplineViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour conseils de discipline."""
    permission_classes = [IsVieScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['eleve', 'statut', 'president']
    ordering = ['-date']

    def get_queryset(self):
        return ConseilDiscipline.objects.select_related(
            'eleve__user', 'eleve__classe', 'president__user', 'sanction'
        ).prefetch_related('membres__user', 'incidents')

    def get_serializer_class(self):
        if self.action == 'list':
            return ConseilDisciplineListSerializer
        return ConseilDisciplineDetailSerializer

    @action(detail=True, methods=['post'])
    def tenir(self, request, pk=None):
        """Marque le conseil comme tenu."""
        conseil = self.get_object()
        if conseil.statut != 'planifie':
            return Response({'error': "Le conseil n'est pas planifié."}, status=400)
        conseil.statut = 'tenu'
        conseil.save(update_fields=['statut'])
        return Response({'detail': "Conseil marqué comme tenu.", 'id': conseil.id})

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """Annule le conseil."""
        conseil = self.get_object()
        if conseil.statut != 'planifie':
            return Response({'error': "Le conseil ne peut pas être annulé."}, status=400)
        conseil.statut = 'annule'
        conseil.save(update_fields=['statut'])
        return Response({'detail': "Conseil annulé.", 'id': conseil.id})
