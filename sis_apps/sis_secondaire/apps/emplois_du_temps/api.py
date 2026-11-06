"""API views for emplois_du_temps (ViewSets DRF) - SIS Secondaire."""

from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import is_current_tenant_user, request_has_business_access
from sis_common.hierarchy_attachments import PreserveOrganizationAttachmentsMixin

from apps.salles.models import Salle
from apps.salles.services import salle_indisponible_pour_creneau

from .models import Contrainte, Creneau
from .serializers import ContrainteSerializer, CreneauDetailSerializer, CreneauListSerializer


class IsVieScolariteOrReadOnly(IsAuthenticated):
    """Lecture pour le tenant, écriture réservée à la vie scolaire."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view) or not is_current_tenant_user(request):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "emplois_du_temps.change_creneau",
            ("vie_scolaire", "cpe", "directeur", "proviseur", "principal"),
            tenant_group_codes=("schedule_manager_secondary",),
        )


class CreneauxViewSet(PreserveOrganizationAttachmentsMixin, viewsets.ModelViewSet):
    """ViewSet CRUD pour créneaux."""

    permission_classes = [IsVieScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = [
        "classe",
        "matiere",
        "enseignant",
        "salle",
        "jour",
        "type",
        "actif",
    ]
    ordering_fields = ["jour", "heure_debut"]
    ordering = ["jour", "heure_debut"]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Creneau.objects.none()
        qs = Creneau.objects.filter(classe__etablissement=tenant).select_related(
            "classe", "matiere", "enseignant__user", "salle"
        )
        user = self.request.user
        # Un enseignant ne voit que ses créneaux par défaut (sauf liste complète)
        if not user.is_staff and getattr(user, "role", "") == "enseignant":
            qs = qs.filter(enseignant__user=user)
        # Un élève ne voit que l'EDT de sa classe
        if not user.is_staff and getattr(user, "role", "") == "eleve":
            profile = getattr(user, "eleve_profile", None)
            qs = qs.filter(classe_id=profile.classe_actuelle_id) if profile else qs.none()
        return qs.filter(actif=True)

    def get_serializer_class(self):
        if self.action == "list":
            return CreneauListSerializer
        return CreneauDetailSerializer

    def _save_if_room_is_available(self, serializer):
        attrs = serializer.validated_data
        creneau = Creneau()
        for field in ("classe", "salle", "jour", "date_specifique", "actif"):
            if field in attrs:
                setattr(creneau, field, attrs[field])
            elif serializer.instance is not None:
                setattr(creneau, field, getattr(serializer.instance, field))
        if creneau.salle_id and creneau.actif:
            Salle.objects.select_for_update().get(
                pk=creneau.salle_id, etablissement=self.request.tenant
            )
            if salle_indisponible_pour_creneau(creneau):
                raise ValidationError(
                    {"salle": "La salle est indisponible pendant ce créneau."}
                )
        serializer.save()

    @transaction.atomic
    def perform_create(self, serializer):
        self._save_if_room_is_available(serializer)

    @transaction.atomic
    def perform_update(self, serializer):
        self._save_if_room_is_available(serializer)

    @action(detail=False, methods=["get"])
    def par_classe(self, request):
        """Retourne l'EDT complet d'une classe."""
        classe_id = request.query_params.get("classe_id")
        if not classe_id:
            return Response({"error": "Paramètre classe_id requis."}, status=400)

        semaine = request.query_params.get("semaine", 0)
        creneaux = (
            self.get_queryset()
            .filter(classe_id=classe_id, actif=True)
            .filter(Q(semaine=0) | Q(semaine=semaine))
            .order_by("jour", "heure_debut")
        )

        from apps.classes.models import Classe

        try:
            classe = Classe.objects.get(pk=classe_id, etablissement=request.tenant)
        except Classe.DoesNotExist:
            return Response({"error": "Classe non trouvée."}, status=404)

        serializer = CreneauListSerializer(creneaux, many=True)
        return Response(
            {
                "classe_id": classe.id,
                "classe_nom": str(classe),
                "semaine": semaine,
                "creneaux": serializer.data,
            }
        )

    @action(detail=False, methods=["get"])
    def par_enseignant(self, request):
        """Retourne l'EDT complet d'un enseignant."""
        enseignant_id = request.query_params.get("enseignant_id")
        if not enseignant_id:
            # Utiliser l'enseignant connecté
            if hasattr(request.user, "personnel_profile"):
                enseignant_id = request.user.personnel_profile.id
            else:
                return Response({"error": "Paramètre enseignant_id requis."}, status=400)

        semaine = request.query_params.get("semaine", 0)
        creneaux = (
            self.get_queryset()
            .filter(enseignant_id=enseignant_id, actif=True)
            .filter(Q(semaine=0) | Q(semaine=semaine))
            .select_related("classe", "matiere", "enseignant__user", "salle")
            .order_by("jour", "heure_debut")
        )

        from apps.enseignants.models import Personnel

        try:
            enseignant = Personnel.objects.select_related("user").get(
                pk=enseignant_id, user__etablissement=request.tenant
            )
            nom = enseignant.user.get_full_name()
        except Personnel.DoesNotExist:
            return Response({"error": "Enseignant non trouvé."}, status=404)

        serializer = CreneauListSerializer(creneaux, many=True)
        return Response(
            {
                "enseignant_id": enseignant_id,
                "enseignant_nom": nom,
                "semaine": semaine,
                "creneaux": serializer.data,
            }
        )

    @action(detail=False, methods=["get"])
    def par_salle(self, request):
        """Retourne l'occupation d'une salle."""
        salle_id = request.query_params.get("salle_id")
        if not salle_id:
            return Response({"error": "Paramètre salle_id requis."}, status=400)

        semaine = request.query_params.get("semaine", 0)
        creneaux = (
            self.get_queryset()
            .filter(salle_id=salle_id, actif=True)
            .filter(Q(semaine=0) | Q(semaine=semaine))
            .select_related("classe", "matiere", "enseignant__user", "salle")
            .order_by("jour", "heure_debut")
        )

        try:
            salle = Salle.objects.get(pk=salle_id, etablissement=request.tenant)
        except Salle.DoesNotExist:
            return Response({"error": "Salle non trouvée."}, status=404)

        serializer = CreneauListSerializer(creneaux, many=True)
        return Response(
            {
                "salle_id": salle.id,
                "salle_nom": salle.nom,
                "semaine": semaine,
                "creneaux": serializer.data,
            }
        )

    @action(detail=False, methods=["get"])
    def conflits(self, request):
        """Détecte les conflits d'EDT."""
        from collections import defaultdict

        creneaux = self.get_queryset().filter(actif=True).select_related("classe", "enseignant", "salle")

        conflits = []
        slots = defaultdict(list)
        for c in creneaux:
            year_id = c.classe.annee_scolaire_id
            if c.enseignant_id:
                slots[("enseignant_double", c.jour, year_id, c.enseignant_id)].append(c)
            if c.salle_id:
                slots[("salle_double", c.jour, year_id, c.salle_id)].append(c)

        for (type_conflit, jour, _year_id, _resource_id), crens in slots.items():
            crens.sort(key=lambda c: c.heure_debut)
            for index, first in enumerate(crens):
                for second in crens[index + 1 :]:
                    if second.heure_debut >= first.heure_fin:
                        break
                    if first.heure_debut >= second.heure_fin:
                        continue
                    if first.semaine and second.semaine and first.semaine != second.semaine:
                        continue
                    if (
                        first.date_specifique
                        and second.date_specifique
                        and first.date_specifique != second.date_specifique
                    ):
                        continue
                    conflits.append(
                        {
                            "type": type_conflit,
                            "jour": jour,
                            "heure": str(second.heure_debut),
                            "creneaux": [first.id, second.id],
                        }
                    )

        return Response({"conflits": conflits, "total": len(conflits)})


class ContraintesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour contraintes."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = ContrainteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["type", "enseignant", "salle", "classe", "jour"]
    ordering = ["-priorite", "type"]

    def get_queryset(self):
        return Contrainte.objects.select_related("enseignant__user", "salle", "classe")
