"""API views for examens (ViewSets DRF) - SIS Supérieur."""

from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ConvocationExamen, EpreuveExamen, SessionExamen
from .serializers import (
    ConvocationExamenSerializer,
    EpreuveExamenDetailSerializer,
    EpreuveExamenListSerializer,
    SessionExamenSerializer,
)


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "scolarite",
            "directeur_etudes",
            "doyen",
        )


class IsExamManager(IsAuthenticated):
    """Réserve les données nominatives aux équipes chargées des examens."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.is_staff or getattr(request.user, "role", "") in (
            "scolarite",
            "directeur_etudes",
            "doyen",
        )


class SessionsExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour sessions d'examens."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = SessionExamenSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["semestre", "numero", "type", "cloturee"]
    ordering_fields = ["date_debut", "numero"]
    ordering = ["-date_debut"]

    def get_queryset(self):
        return SessionExamen.objects.select_related("semestre").annotate(
            nb_epreuves_count=Count("epreuves")
        )

    @action(detail=True, methods=["get"])
    def epreuves(self, request, pk=None):
        """Liste les épreuves de la session."""
        session = self.get_object()
        epreuves = session.epreuves.select_related("ecue").order_by(
            "date", "heure_debut"
        )
        serializer = EpreuveExamenListSerializer(epreuves, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        """Clôture la session."""
        session = self.get_object()
        if session.cloturee:
            return Response({"error": "Session déjà clôturée."}, status=400)
        session.cloturee = True
        session.save(update_fields=["cloturee"])
        return Response({"detail": "Session clôturée.", "id": session.id})

    @action(detail=True, methods=["get"], permission_classes=[IsExamManager])
    def statistiques(self, request, pk=None):
        """Statistiques de la session."""
        session = self.get_object()
        epreuves = session.epreuves.annotate(
            total_convoques=Count("convocations"),
            presents=Count("convocations", filter=Q(convocations__statut="present")),
            absents=Count("convocations", filter=Q(convocations__statut="absent")),
        )
        totals = {
            "convoques": sum(e.total_convoques for e in epreuves),
            "presents": sum(e.presents for e in epreuves),
            "absents": sum(e.absents for e in epreuves),
        }
        return Response(
            {
                "session_id": session.id,
                "nb_epreuves": epreuves.count(),
                **totals,
                "taux_presence": (
                    round(totals["presents"] / totals["convoques"] * 100, 2)
                    if totals["convoques"]
                    else 0
                ),
            }
        )


class EpreuvesExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour épreuves d'examens."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["session", "ecue", "date"]
    ordering_fields = ["date", "heure_debut"]
    ordering = ["date", "heure_debut"]

    def get_queryset(self):
        return (
            EpreuveExamen.objects.select_related("session", "ecue")
            .prefetch_related("surveillants")
            .annotate(
                nb_convoques_count=Count("convocations"),
                nb_presents_count=Count(
                    "convocations",
                    filter=Q(convocations__statut="present"),
                ),
            )
        )

    def get_serializer_class(self):
        if self.action == "list":
            return EpreuveExamenListSerializer
        return EpreuveExamenDetailSerializer

    @action(detail=True, methods=["get"], permission_classes=[IsExamManager])
    def convocations(self, request, pk=None):
        """Liste les convocations de l'épreuve."""
        epreuve = self.get_object()
        convocations = epreuve.convocations.select_related("etudiant__user").order_by(
            "numero_place"
        )
        serializer = ConvocationExamenSerializer(convocations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def generer_convocations(self, request, pk=None):
        """Génère les convocations automatiquement."""
        epreuve = self.get_object()
        # Récupérer les étudiants inscrits à l'ECUE
        from apps.etudiants.models import InscriptionPedagogique

        inscrits = list(
            InscriptionPedagogique.objects.filter(ecue=epreuve.ecue)
            .values_list("etudiant_id", flat=True)
            .distinct()
        )
        deja_convoques = set(
            epreuve.convocations.filter(etudiant_id__in=inscrits).values_list(
                "etudiant_id", flat=True
            )
        )
        nouvelles_convocations = [
            ConvocationExamen(
                epreuve=epreuve,
                etudiant_id=etudiant_id,
                numero_place=str(numero),
            )
            for numero, etudiant_id in enumerate(inscrits, 1)
            if etudiant_id not in deja_convoques
        ]
        ConvocationExamen.objects.bulk_create(
            nouvelles_convocations,
            batch_size=1000,
            ignore_conflicts=True,
        )

        return Response(
            {
                "epreuve_id": epreuve.id,
                "convocations_creees": len(nouvelles_convocations),
                "total_convoques": epreuve.convocations.count(),
            }
        )

    @action(detail=True, methods=["get"], permission_classes=[IsExamManager])
    def emargement(self, request, pk=None):
        """Export la liste d'émargement."""
        epreuve = self.get_object()
        convocations = epreuve.convocations.select_related("etudiant__user").order_by(
            "numero_place"
        )
        data = [
            {
                "place": c.numero_place,
                "matricule": c.etudiant.matricule,
                "nom": c.etudiant.user.last_name.upper(),
                "prenom": c.etudiant.user.first_name,
                "salle": c.salle,
                "signature": "",
            }
            for c in convocations
        ]
        return Response(
            {
                "epreuve": str(epreuve),
                "date": epreuve.date,
                "heure": epreuve.heure_debut,
                "lieu": epreuve.lieu,
                "etudiants": data,
            }
        )


class ConvocationsExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour convocations."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = ConvocationExamenSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["epreuve", "etudiant", "statut"]
    ordering = ["numero_place"]

    def get_queryset(self):
        qs = ConvocationExamen.objects.select_related("epreuve__ecue", "etudiant__user")
        user = self.request.user
        if user.is_staff or getattr(user, "role", "") in (
            "scolarite",
            "directeur_etudes",
            "doyen",
        ):
            return qs
        if getattr(user, "role", "") in ("etudiant", "doctorant"):
            return qs.filter(etudiant__user=user)
        return qs.none()

    @action(detail=True, methods=["post"])
    def pointer(self, request, pk=None):
        """Pointe la présence d'un étudiant."""
        convocation = self.get_object()
        new_statut = request.data.get("statut", "present")
        if new_statut not in ["present", "absent", "dispense"]:
            return Response({"error": "Statut invalide."}, status=400)
        convocation.statut = new_statut
        convocation.save(update_fields=["statut"])
        return Response(
            {"detail": f"Convocation mise à jour: {new_statut}", "id": convocation.id}
        )
