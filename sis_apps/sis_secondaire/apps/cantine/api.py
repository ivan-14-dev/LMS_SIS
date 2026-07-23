"""API views for cantine (ViewSets DRF) - SIS Secondaire."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db.models import Count, Q
from django.utils import timezone

from .models import Menu, InscriptionCantine, PresenceCantine
from .serializers import (
    MenuSerializer,
    InscriptionCantineSerializer,
    PresenceCantineSerializer,
    PointageCantineSerializer,
)


class IsIntendanceOrReadOnly(IsAuthenticated):
    """Permission: intendance pour écriture."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        return user.is_staff or getattr(user, 'role', '') in (
            'intendance', 'vie_scolaire', 'directeur', 'proviseur', 'principal'
        )


class MenusViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour menus."""
    permission_classes = [IsIntendanceOrReadOnly]
    serializer_class = MenuSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['date', 'regime']
    ordering = ['date']

    def get_queryset(self):
        return Menu.objects.all()

    @action(detail=False, methods=['get'])
    def semaine(self, request):
        """Retourne les menus de la semaine."""
        from datetime import timedelta
        today = timezone.now().date()
        # Début de la semaine (lundi)
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)
        
        menus = self.get_queryset().filter(
            date__gte=start_week,
            date__lte=end_week
        ).order_by('date', 'regime')
        
        serializer = MenuSerializer(menus, many=True)
        return Response({
            'semaine_debut': start_week,
            'semaine_fin': end_week,
            'menus': serializer.data,
        })

    @action(detail=True, methods=['get'])
    def presences(self, request, pk=None):
        """Liste les présences pour ce menu."""
        menu = self.get_object()
        presences = menu.presences.select_related('eleve__user').order_by('eleve__user__last_name')
        serializer = PresenceCantineSerializer(presences, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Statistiques du menu."""
        menu = self.get_object()
        total = menu.presences.count()
        presents = menu.presences.filter(present=True).count()
        return Response({
            'menu_id': menu.id,
            'date': menu.date,
            'total_inscrits': total,
            'presents': presents,
            'absents': total - presents,
        })


class InscriptionsCantineViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour inscriptions cantine."""
    permission_classes = [IsIntendanceOrReadOnly]
    serializer_class = InscriptionCantineSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['eleve', 'forfait', 'regime', 'actif']
    ordering = ['eleve__user__last_name']

    def get_queryset(self):
        return InscriptionCantine.objects.select_related(
            'eleve__user', 'eleve__classe'
        )

    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """Statistiques des inscriptions."""
        qs = self.get_queryset().filter(actif=True)
        stats = {
            'total_inscrits': qs.count(),
        }
        by_forfait = qs.values('forfait').annotate(count=Count('id'))
        stats['par_forfait'] = {f['forfait']: f['count'] for f in by_forfait}
        by_regime = qs.values('regime').annotate(count=Count('id'))
        stats['par_regime'] = {r['regime']: r['count'] for r in by_regime}
        return Response(stats)


class PresencesCantineViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour présences cantine."""
    permission_classes = [IsIntendanceOrReadOnly]
    serializer_class = PresenceCantineSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['menu', 'eleve', 'present']
    ordering = ['-menu__date']

    def get_queryset(self):
        return PresenceCantine.objects.select_related('menu', 'eleve__user')

    @action(detail=False, methods=['post'])
    def pointage_masse(self, request):
        """Pointage en masse pour un menu."""
        menu_id = request.data.get('menu_id')
        if not menu_id:
            return Response({'error': "menu_id requis."}, status=400)
        
        try:
            menu = Menu.objects.get(pk=menu_id)
        except Menu.DoesNotExist:
            return Response({'error': "Menu non trouvé."}, status=404)
        
        pointages = request.data.get('pointages', [])
        serializer = PointageCantineSerializer(data=pointages, many=True)
        serializer.is_valid(raise_exception=True)
        
        created = 0
        updated = 0
        now = timezone.now().time()
        
        for item in serializer.validated_data:
            presence, was_created = PresenceCantine.objects.update_or_create(
                menu=menu,
                eleve_id=item['eleve_id'],
                defaults={
                    'present': item['present'],
                    'heure_pointage': now if item['present'] else None,
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1
        
        return Response({
            'menu_id': menu.id,
            'crees': created,
            'mis_a_jour': updated,
        })
