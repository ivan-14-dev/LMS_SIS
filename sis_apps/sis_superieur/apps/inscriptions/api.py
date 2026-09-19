"""API views for inscriptions (SIS Supérieur).

Note: Utilise InscriptionAdministrative du module etudiants.
Fournit un workflow spécialisé pour les nouvelles inscriptions.
"""

from apps.etudiants.models import InscriptionAdministrative
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import InscriptionSerializer


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

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


class InscriptionsViewSet(viewsets.ModelViewSet):
    """ViewSet pour le workflow d'inscription."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = InscriptionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["formation", "annee_universitaire", "statut", "active"]
    search_fields = ["etudiant__matricule", "etudiant__user__last_name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return InscriptionAdministrative.objects.select_related(
            "etudiant__user", "formation", "parcours", "annee_universitaire"
        )

    @action(detail=False, methods=["get"])
    def en_attente(self, request):
        """Inscriptions en attente de validation."""
        inscriptions = self.get_queryset().filter(statut="en_attente")
        serializer = self.get_serializer(inscriptions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        """Valide une inscription."""
        inscription = self.get_object()
        inscription.statut = "validee"
        inscription.active = True
        inscription.save(update_fields=["statut", "active"])
        return Response({"detail": "Inscription validée.", "id": inscription.id})

    @action(detail=True, methods=["post"])
    def rejeter(self, request, pk=None):
        """Rejette une inscription."""
        inscription = self.get_object()
        motif = request.data.get("motif", "")
        inscription.statut = "rejetee"
        inscription.save(update_fields=["statut"])
        return Response(
            {"detail": "Inscription rejetée.", "id": inscription.id, "motif": motif}
        )
