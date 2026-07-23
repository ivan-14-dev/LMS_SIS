"""API views for emplois du temps (SIS Supérieur)."""
from datetime import timedelta
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Batiment, Salle, CreneauHoraire, CreneauCours, Reservation, ConflitHoraire
)
from .serializers import (
    BatimentListSerializer, BatimentDetailSerializer,
    SalleListSerializer, SalleDetailSerializer, SalleCreateUpdateSerializer,
    CreneauHoraireSerializer,
    CreneauCoursListSerializer, CreneauCoursDetailSerializer, CreneauCoursCreateUpdateSerializer,
    ReservationListSerializer, ReservationDetailSerializer,
    ReservationCreateSerializer, ValidationReservationSerializer,
    ConflitHoraireSerializer, EmploiDuTempsSerializer
)


class BatimentViewSet(viewsets.ModelViewSet):
    """ViewSet pour les bâtiments."""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom', 'code']

    def get_queryset(self):
        return Batiment.objects.annotate(nb_salles=Count('salles'))

    def get_serializer_class(self):
        if self.action == 'list':
            return BatimentListSerializer
        return BatimentDetailSerializer

    @action(detail=True, methods=['get'])
    def salles(self, request, pk=None):
        """Liste des salles d'un bâtiment."""
        batiment = self.get_object()
        salles = batiment.salles.all()
        serializer = SalleListSerializer(salles, many=True)
        return Response(serializer.data)


class SalleViewSet(viewsets.ModelViewSet):
    """ViewSet pour les salles."""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['batiment', 'type', 'disponible', 'accessibilite_pmr']
    search_fields = ['nom', 'code']

    def get_queryset(self):
        return Salle.objects.select_related('batiment', 'departement_gestionnaire')

    def get_serializer_class(self):
        if self.action == 'list':
            return SalleListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return SalleCreateUpdateSerializer
        return SalleDetailSerializer

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Salles disponibles à la réservation."""
        salles = self.get_queryset().filter(disponible=True)
        
        # Filtres optionnels
        capacite_min = request.query_params.get('capacite_min')
        type_salle = request.query_params.get('type')
        batiment_id = request.query_params.get('batiment')
        
        if capacite_min:
            salles = salles.filter(capacite__gte=capacite_min)
        if type_salle:
            salles = salles.filter(type=type_salle)
        if batiment_id:
            salles = salles.filter(batiment_id=batiment_id)
        
        serializer = SalleListSerializer(salles, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def planning(self, request, pk=None):
        """Planning d'une salle sur une semaine."""
        salle = self.get_object()
        date_debut = request.query_params.get('date_debut')
        
        # Créneaux réguliers
        creneaux = salle.creneaux_cours.select_related(
            'ecue', 'enseignant', 'creneau_horaire'
        )
        
        # Réservations
        reservations = salle.reservations.filter(statut='confirmee')
        if date_debut:
            from datetime import datetime
            date_obj = datetime.strptime(date_debut, '%Y-%m-%d').date()
            date_fin = date_obj + timedelta(days=7)
            reservations = reservations.filter(date__gte=date_obj, date__lt=date_fin)
        
        return Response({
            'salle': SalleListSerializer(salle).data,
            'creneaux_reguliers': CreneauCoursListSerializer(creneaux, many=True).data,
            'reservations': ReservationListSerializer(reservations, many=True).data
        })

    @action(detail=True, methods=['get'])
    def disponibilite(self, request, pk=None):
        """Vérifier la disponibilité d'une salle."""
        salle = self.get_object()
        date = request.query_params.get('date')
        heure_debut = request.query_params.get('heure_debut')
        heure_fin = request.query_params.get('heure_fin')

        if not all([date, heure_debut, heure_fin]):
            return Response(
                {'error': "date, heure_debut et heure_fin sont requis."},
                status=400
            )

        # Vérifier réservations
        conflits_reservations = Reservation.objects.filter(
            salle=salle, date=date, statut='confirmee'
        ).filter(
            heure_debut__lt=heure_fin, heure_fin__gt=heure_debut
        )

        return Response({
            'disponible': not conflits_reservations.exists(),
            'conflits': ReservationListSerializer(conflits_reservations, many=True).data
        })


class CreneauHoraireViewSet(viewsets.ModelViewSet):
    """ViewSet pour les créneaux horaires types."""
    permission_classes = [IsAuthenticated]
    queryset = CreneauHoraire.objects.all()
    serializer_class = CreneauHoraireSerializer


class CreneauCoursViewSet(viewsets.ModelViewSet):
    """ViewSet pour les créneaux de cours."""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['semestre', 'formation', 'ecue', 'enseignant', 'salle', 'jour', 'type_cours']
    search_fields = ['ecue__nom', 'ecue__code']

    def get_queryset(self):
        return CreneauCours.objects.select_related(
            'semestre', 'formation', 'ecue', 'enseignant', 'salle', 'creneau_horaire'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return CreneauCoursListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return CreneauCoursCreateUpdateSerializer
        return CreneauCoursDetailSerializer

    @action(detail=False, methods=['get'])
    def par_formation(self, request):
        """Emploi du temps d'une formation."""
        formation_id = request.query_params.get('formation_id')
        semestre_id = request.query_params.get('semestre_id')
        groupe = request.query_params.get('groupe', '')

        if not formation_id or not semestre_id:
            return Response(
                {'error': "formation_id et semestre_id sont requis."},
                status=400
            )

        creneaux = self.get_queryset().filter(
            formation_id=formation_id, semestre_id=semestre_id
        )
        if groupe:
            creneaux = creneaux.filter(Q(groupe=groupe) | Q(groupe=''))

        # Organiser par jour
        emploi = {i: [] for i in range(7)}
        for creneau in creneaux:
            emploi[creneau.jour].append(CreneauCoursListSerializer(creneau).data)

        return Response({
            'formation_id': formation_id,
            'semestre_id': semestre_id,
            'groupe': groupe,
            'emploi_du_temps': emploi
        })

    @action(detail=False, methods=['get'])
    def par_enseignant(self, request):
        """Emploi du temps d'un enseignant."""
        enseignant_id = request.query_params.get('enseignant_id')
        semestre_id = request.query_params.get('semestre_id')

        if not enseignant_id:
            return Response({'error': "enseignant_id est requis."}, status=400)

        creneaux = self.get_queryset().filter(enseignant_id=enseignant_id)
        if semestre_id:
            creneaux = creneaux.filter(semestre_id=semestre_id)

        emploi = {i: [] for i in range(7)}
        for creneau in creneaux:
            emploi[creneau.jour].append(CreneauCoursListSerializer(creneau).data)

        return Response({
            'enseignant_id': enseignant_id,
            'emploi_du_temps': emploi
        })

    @action(detail=False, methods=['get'])
    def par_salle(self, request):
        """Emploi du temps d'une salle."""
        salle_id = request.query_params.get('salle_id')
        semestre_id = request.query_params.get('semestre_id')

        if not salle_id:
            return Response({'error': "salle_id est requis."}, status=400)

        creneaux = self.get_queryset().filter(salle_id=salle_id)
        if semestre_id:
            creneaux = creneaux.filter(semestre_id=semestre_id)

        emploi = {i: [] for i in range(7)}
        for creneau in creneaux:
            emploi[creneau.jour].append(CreneauCoursListSerializer(creneau).data)

        return Response({
            'salle_id': salle_id,
            'emploi_du_temps': emploi
        })

    @action(detail=False, methods=['post'])
    def detecter_conflits(self, request):
        """Détecter les conflits d'horaires."""
        semestre_id = request.data.get('semestre_id')
        if not semestre_id:
            return Response({'error': "semestre_id est requis."}, status=400)

        creneaux = CreneauCours.objects.filter(semestre_id=semestre_id)
        conflits = []

        # Grouper par jour et créneau horaire
        for creneau in creneaux:
            # Conflit de salle
            conflits_salle = creneaux.filter(
                salle=creneau.salle,
                jour=creneau.jour,
                creneau_horaire=creneau.creneau_horaire
            ).exclude(pk=creneau.pk)

            for c in conflits_salle:
                conflit, _ = ConflitHoraire.objects.get_or_create(
                    type_conflit='salle',
                    creneau_1=creneau,
                    creneau_2=c,
                    defaults={'description': f"Salle {creneau.salle} occupée"}
                )
                conflits.append(conflit)

            # Conflit d'enseignant
            if creneau.enseignant:
                conflits_ens = creneaux.filter(
                    enseignant=creneau.enseignant,
                    jour=creneau.jour,
                    creneau_horaire=creneau.creneau_horaire
                ).exclude(pk=creneau.pk)

                for c in conflits_ens:
                    conflit, _ = ConflitHoraire.objects.get_or_create(
                        type_conflit='enseignant',
                        creneau_1=creneau,
                        creneau_2=c,
                        defaults={'description': f"Enseignant {creneau.enseignant} occupé"}
                    )
                    conflits.append(conflit)

        return Response({
            'nb_conflits': len(conflits),
            'conflits': ConflitHoraireSerializer(conflits, many=True).data
        })


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet pour les réservations de salles."""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['salle', 'statut', 'motif', 'demandeur']
    ordering_fields = ['date', 'created_at']
    ordering = ['date', 'heure_debut']

    def get_queryset(self):
        return Reservation.objects.select_related('salle', 'demandeur', 'valide_par')

    def get_serializer_class(self):
        if self.action == 'list':
            return ReservationListSerializer
        if self.action == 'create':
            return ReservationCreateSerializer
        return ReservationDetailSerializer

    def perform_create(self, serializer):
        serializer.save(demandeur=self.request.user.utilisateur)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valider ou refuser une réservation."""
        reservation = self.get_object()
        if reservation.statut != 'en_attente':
            return Response(
                {'error': "Seules les réservations en attente peuvent être validées."},
                status=400
            )

        serializer = ValidationReservationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        if data['action'] == 'confirmer':
            reservation.statut = 'confirmee'
        else:
            reservation.statut = 'refusee'
            reservation.motif_refus = data.get('motif_refus', '')

        reservation.valide_par = request.user.utilisateur
        reservation.date_validation = timezone.now()
        reservation.save()

        return Response(ReservationDetailSerializer(reservation).data)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """Annuler une réservation."""
        reservation = self.get_object()
        if reservation.statut == 'annulee':
            return Response({'error': "Déjà annulée."}, status=400)

        reservation.statut = 'annulee'
        reservation.save()
        return Response({'status': 'Réservation annulée.'})

    @action(detail=False, methods=['get'])
    def mes_reservations(self, request):
        """Réservations de l'utilisateur connecté."""
        reservations = self.get_queryset().filter(
            demandeur=request.user.utilisateur
        )
        serializer = ReservationListSerializer(reservations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def a_valider(self, request):
        """Réservations en attente de validation."""
        reservations = self.get_queryset().filter(statut='en_attente')
        serializer = ReservationListSerializer(reservations, many=True)
        return Response(serializer.data)


class ConflitHoraireViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les conflits horaires (lecture seule)."""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['type_conflit', 'resolu']
    serializer_class = ConflitHoraireSerializer

    def get_queryset(self):
        return ConflitHoraire.objects.select_related('creneau_1', 'creneau_2')

    @action(detail=True, methods=['post'])
    def marquer_resolu(self, request, pk=None):
        """Marquer un conflit comme résolu."""
        conflit = self.get_object()
        conflit.resolu = True
        conflit.date_resolution = timezone.now()
        conflit.save()
        return Response({'status': 'Conflit marqué comme résolu.'})
