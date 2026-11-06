"""API views for rattrapages (ViewSets DRF) - SIS Supérieur."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import (
    is_current_tenant_user,
    request_has_business_access,
    user_has_any_role,
)

from .models import InscriptionRattrapage
from .serializers import InscriptionRattrapageSerializer


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view) or not is_current_tenant_user(request):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "rattrapages.change_inscriptionrattrapage",
            ("scolarite", "responsable_formation", "doyen"),
            tenant_group_codes=("retake_manager_superieur",),
        )


class InscriptionsRattrapageViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour inscriptions rattrapage."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = InscriptionRattrapageSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["etudiant", "ecue", "session_rattrapage", "statut"]
    ordering = ["-date_inscription"]

    def get_queryset(self):
        inscriptions = InscriptionRattrapage.objects.select_related(
            "etudiant__user", "ecue", "session_rattrapage"
        ).filter(
            etudiant__universite_id=self.request.tenant.pk,
            session_rattrapage__semestre__annee_universitaire__universite_id=self.request.tenant.pk,
        )
        if not is_current_tenant_user(self.request):
            return inscriptions.none()
        if not self.request.user.is_superuser and user_has_any_role(
            self.request.user, ("etudiant", "doctorant")
        ):
            return inscriptions.filter(etudiant__user=self.request.user)
        if request_has_business_access(
            self.request,
            "rattrapages.view_inscriptionrattrapage",
            ("scolarite", "responsable_formation", "doyen"),
            tenant_group_codes=("retake_manager_superieur",),
        ) or request_has_business_access(
            self.request,
            "rattrapages.change_inscriptionrattrapage",
            ("scolarite", "responsable_formation", "doyen"),
            tenant_group_codes=("retake_manager_superieur",),
        ):
            return inscriptions
        return inscriptions.none()

    @action(detail=False, methods=["get"])
    def en_attente(self, request):
        """Liste les inscriptions en attente de rattrapage."""
        inscriptions = self.get_queryset().filter(statut="inscrit")
        serializer = self.get_serializer(inscriptions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def enregistrer_note(self, request, pk=None):
        """Enregistre la note du rattrapage."""
        inscription = self.get_object()
        note = request.data.get("note")
        if note is None:
            return Response({"error": "Note requise."}, status=400)

        inscription.note = note
        inscription.statut = "passe"
        inscription.save(update_fields=["note", "statut"])
        return Response({"detail": "Note enregistrée.", "note": str(inscription.note)})

    @action(detail=True, methods=["post"])
    def marquer_absent(self, request, pk=None):
        """Marque l'étudiant comme absent."""
        inscription = self.get_object()
        inscription.statut = "absent"
        inscription.save(update_fields=["statut"])
        return Response({"detail": "Marqué absent.", "id": inscription.id})
