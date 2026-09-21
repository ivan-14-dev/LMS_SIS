"""API views for enseignants (ViewSets DRF) - SIS Supérieur."""

from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import has_business_permission_or_role

from .models import AffectationEnseignement, EnseignantChercheur
from .serializers import (
    AffectationEnseignementSerializer,
    EnseignantCreateSerializer,
    EnseignantDetailSerializer,
    EnseignantListSerializer,
)


class IsScolariteOrEnseignant(IsAuthenticated):
    """Permission: scolarité ou enseignant concerné."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return has_business_permission_or_role(
            request.user,
            "enseignants.change_enseignantchercheur",
            ("scolarite", "directeur_etudes", "doyen"),
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff:
            return True
        if getattr(user, "role", "") in ("scolarite", "directeur_etudes", "doyen"):
            return True
        # Un enseignant peut voir son propre profil
        if hasattr(obj, "user") and obj.user == user:
            return True
        return False


class EnseignantsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour enseignants-chercheurs."""

    permission_classes = [IsScolariteOrEnseignant]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["corps", "laboratoire"]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "specialite",
        "numero_harpe",
    ]
    ordering_fields = ["user__last_name", "corps", "h_index", "created_at"]
    ordering = ["user__last_name", "user__first_name"]

    def get_queryset(self):
        return EnseignantChercheur.objects.select_related("user", "laboratoire")

    def get_serializer_class(self):
        if self.action == "list":
            return EnseignantListSerializer
        elif self.action == "create":
            return EnseignantCreateSerializer
        return EnseignantDetailSerializer

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Retourne le profil enseignant de l'utilisateur connecté."""
        try:
            enseignant = EnseignantChercheur.objects.get(user=request.user)
            serializer = EnseignantDetailSerializer(enseignant)
            return Response(serializer.data)
        except EnseignantChercheur.DoesNotExist:
            return Response({"error": "Vous n'êtes pas enseignant."}, status=404)

    @action(detail=True, methods=["get"])
    def affectations(self, request, pk=None):
        """Liste les affectations d'enseignement."""
        enseignant = self.get_object()
        affectations = enseignant.affectations.select_related("ue", "ecue", "annee_universitaire").order_by(
            "-annee_universitaire__date_debut"
        )
        serializer = AffectationEnseignementSerializer(affectations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def heures_total(self, request, pk=None):
        """Calcule le total des heures d'enseignement."""
        enseignant = self.get_object()
        annee_id = request.query_params.get("annee")
        qs = enseignant.affectations.all()
        if annee_id:
            qs = qs.filter(annee_universitaire_id=annee_id)
        total = qs.aggregate(total=Sum("heures"))["total"] or 0
        return Response(
            {
                "enseignant_id": enseignant.id,
                "heures_service": float(enseignant.heures_service),
                "heures_affectees": float(total),
                "ecart": float(total) - float(enseignant.heures_service),
            }
        )


class AffectationsViewSet(viewsets.ModelViewSet):
    """ViewSet pour les affectations d'enseignement."""

    permission_classes = [IsScolariteOrEnseignant]
    serializer_class = AffectationEnseignementSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = [
        "enseignant",
        "ue",
        "ecue",
        "type_enseignement",
        "annee_universitaire",
    ]
    ordering = ["-annee_universitaire__date_debut"]

    def get_queryset(self):
        return AffectationEnseignement.objects.select_related("enseignant__user", "ue", "ecue", "annee_universitaire")
