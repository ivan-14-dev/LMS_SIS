"""API views for emplois_du_temps (ViewSets DRF) - SIS Secondaire."""

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import request_has_business_access

from .models import Contrainte, Creneau
from .serializers import ContrainteSerializer, CreneauDetailSerializer, CreneauListSerializer


class IsVieScolariteOrReadOnly(IsAuthenticated):
    """Permission: vie scolaire pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "emplois_du_temps.change_creneau",
            ("vie_scolaire", "cpe", "directeur", "proviseur", "principal"),
            tenant_group_codes=("schedule_manager_secondary",),
        )


class CreneauxViewSet(viewsets.ModelViewSet):
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
        qs = Creneau.objects.select_related(
            "classe", "matiere", "enseignant__user", "salle"
        )
        user = self.request.user
        # Un enseignant ne voit que ses créneaux par défaut (sauf liste complète)
        if hasattr(user, "personnel_profile") and not self.request.query_params.get(
            "all"
        ):
            if not user.is_staff and getattr(user, "role", "") == "enseignant":
                qs = qs.filter(enseignant=user.personnel_profile)
        # Un élève ne voit que l'EDT de sa classe
        if hasattr(user, "eleve_profile"):
            if not user.is_staff and getattr(user, "role", "") == "eleve":
                qs = qs.filter(classe=user.eleve_profile.classe)
        return qs.filter(actif=True)

    def get_serializer_class(self):
        if self.action == "list":
            return CreneauListSerializer
        return CreneauDetailSerializer

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
            classe = Classe.objects.get(pk=classe_id)
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
                return Response(
                    {"error": "Paramètre enseignant_id requis."}, status=400
                )

        semaine = request.query_params.get("semaine", 0)
        creneaux = (
            Creneau.objects.filter(enseignant_id=enseignant_id, actif=True)
            .filter(Q(semaine=0) | Q(semaine=semaine))
            .select_related("classe", "matiere", "enseignant__user", "salle")
            .order_by("jour", "heure_debut")
        )

        from apps.enseignants.models import Personnel

        try:
            enseignant = Personnel.objects.select_related("user").get(pk=enseignant_id)
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
            Creneau.objects.filter(salle_id=salle_id, actif=True)
            .filter(Q(semaine=0) | Q(semaine=semaine))
            .select_related("classe", "matiere", "enseignant__user", "salle")
            .order_by("jour", "heure_debut")
        )

        from apps.salles.models import Salle

        try:
            salle = Salle.objects.get(pk=salle_id)
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

        creneaux = Creneau.objects.filter(actif=True).select_related(
            "classe", "enseignant", "salle"
        )

        conflits = []
        # Grouper par (jour, heure_debut, heure_fin)
        slots = defaultdict(list)
        for c in creneaux:
            key = (c.jour, str(c.heure_debut), str(c.heure_fin))
            slots[key].append(c)

        for (jour, debut, _fin), crens in slots.items():
            # Vérifier conflits enseignant
            enseignants = defaultdict(list)
            for c in crens:
                if c.enseignant_id:
                    enseignants[c.enseignant_id].append(c)
            for _ens_id, ens_crens in enseignants.items():
                if len(ens_crens) > 1:
                    conflits.append(
                        {
                            "type": "enseignant_double",
                            "jour": jour,
                            "heure": debut,
                            "creneaux": [c.id for c in ens_crens],
                        }
                    )

            # Vérifier conflits salle
            salles = defaultdict(list)
            for c in crens:
                if c.salle_id:
                    salles[c.salle_id].append(c)
            for _salle_id, salle_crens in salles.items():
                if len(salle_crens) > 1:
                    conflits.append(
                        {
                            "type": "salle_double",
                            "jour": jour,
                            "heure": debut,
                            "creneaux": [c.id for c in salle_crens],
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
