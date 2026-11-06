"""API views for salles (ViewSets DRF) - SIS Secondaire."""

from django.db import transaction
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from sis_common.authorization import is_current_tenant_user
from sis_common.workflow_tracking import record_workflow_event

from .models import Equipement, IndisponibiliteSalle, Salle
from .serializers import (
    EquipementSerializer,
    IndisponibiliteSalleSerializer,
    SalleDetailSerializer,
    SalleListSerializer,
)
from .services import periode_recoupe_creneau


class IsAdminOrReadOnly(IsAuthenticated):
    """Lecture pour le tenant, écriture réservée à ses administrateurs."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view) or not is_current_tenant_user(request):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.is_staff


class SallesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour salles."""

    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["etablissement", "type", "batiment", "accessible_pm"]
    search_fields = ["code", "nom", "batiment"]
    ordering_fields = ["nom", "batiment", "capacite"]
    ordering = ["batiment", "nom"]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Salle.objects.none()
        return Salle.objects.filter(etablissement=tenant).select_related("etablissement")

    def get_serializer_class(self):
        if self.action == "list":
            return SalleListSerializer
        return SalleDetailSerializer

    @action(detail=False, methods=["get"])
    def par_type(self, request):
        """Statistiques par type de salle."""
        stats = self.get_queryset().values("type").annotate(count=Count("id"))
        return Response({s["type"]: s["count"] for s in stats})

    @action(detail=False, methods=["get"])
    def par_batiment(self, request):
        """Statistiques par bâtiment."""
        stats = self.get_queryset().values("batiment").annotate(count=Count("id"))
        return Response({s["batiment"] or "Non spécifié": s["count"] for s in stats})

    @action(detail=True, methods=["get"])
    def emploi_du_temps(self, request, pk=None):
        """Retourne l'emploi du temps de la salle."""
        salle = self.get_object()
        from apps.emplois_du_temps.models import Creneau
        from apps.emplois_du_temps.serializers import CreneauListSerializer

        creneaux = (
            Creneau.objects.filter(salle=salle, actif=True)
            .select_related("classe", "matiere", "enseignant__user")
            .order_by("jour", "heure_debut")
        )
        serializer = CreneauListSerializer(creneaux, many=True)
        return Response(serializer.data)


class EquipementsViewSet(viewsets.ModelViewSet):
    """Registre des équipements, affectations et désactivation réversible."""

    serializer_class = EquipementSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["salle", "actif"]
    search_fields = ["identifiant", "nom"]
    ordering_fields = ["identifiant", "nom"]
    ordering = ["identifiant"]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Equipement.objects.none()
        queryset = Equipement.objects.filter(etablissement=tenant).select_related("salle")
        if self.action in ("update", "partial_update"):
            queryset = queryset.select_for_update(of=("self",))
        return queryset

    @staticmethod
    def _assignment_state(equipement):
        salle = equipement.salle
        return {
            "actif": equipement.actif,
            "salle_id": equipement.salle_id,
            "salle_code": salle.code if salle else None,
            "salle_nom": salle.nom if salle else None,
        }

    @transaction.atomic
    def perform_create(self, serializer):
        equipement = serializer.save()
        record_workflow_event(
            self.request,
            equipement,
            "creation",
            "Équipement enregistré",
            metadata={"avant": None, "apres": self._assignment_state(equipement)},
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        avant = self._assignment_state(serializer.instance)
        equipement = serializer.save()
        apres = self._assignment_state(equipement)
        if avant == apres:
            return
        if avant["actif"] != apres["actif"]:
            action_name = "reactivation" if apres["actif"] else "desactivation"
            title = "Équipement réactivé" if apres["actif"] else "Équipement désactivé"
        else:
            action_name = "affectation"
            title = "Affectation de l'équipement modifiée"
        record_workflow_event(
            self.request,
            equipement,
            action_name,
            title,
            metadata={"avant": avant, "apres": apres},
        )


class IndisponibilitesSalleViewSet(viewsets.ModelViewSet):
    """Plages de jours entiers où la réservation d'une salle est interdite."""

    serializer_class = IndisponibiliteSalleSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["salle"]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return IndisponibiliteSalle.objects.none()
        return IndisponibiliteSalle.objects.filter(
            salle__etablissement=tenant
        ).select_related("salle")

    def _save_if_room_is_free(self, serializer):
        attrs = serializer.validated_data
        salle = attrs.get("salle", getattr(serializer.instance, "salle", None))
        Salle.objects.select_for_update().get(
            pk=salle.pk, etablissement=self.request.tenant
        )
        debut = attrs.get("date_debut", getattr(serializer.instance, "date_debut", None))
        fin = attrs.get("date_fin", getattr(serializer.instance, "date_fin", None))
        if periode_recoupe_creneau(salle, debut, fin):
            raise ValidationError(
                {"date_debut": "Un créneau actif occupe déjà la salle pendant cette période."}
            )
        serializer.save()

    @transaction.atomic
    def perform_create(self, serializer):
        self._save_if_room_is_free(serializer)

    @transaction.atomic
    def perform_update(self, serializer):
        self._save_if_room_is_free(serializer)
