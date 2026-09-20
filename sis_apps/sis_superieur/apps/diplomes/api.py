"""API views for diplomes (ViewSets DRF) - SIS Supérieur."""

import uuid

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import has_business_permission_or_role
from sis_common.document_policies import enforce_financial_clearance, get_action_object

from .models import CessionDiplome, Diplome
from .serializers import CessionDiplomeDetailSerializer, CessionDiplomeListSerializer, DiplomeSerializer


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return has_business_permission_or_role(
            request.user,
            "diplomes.change_cessiondiplome",
            (
                "scolarite",
                "responsable_formation",
                "doyen",
                "president_universite",
            ),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=("document_signatory_superieur", "academic_registry_superieur"),
        )


class DiplomesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour types de diplômes."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = DiplomeSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["formation", "type", "niveau_grade"]
    search_fields = ["nom", "code_rncp"]
    ordering = ["niveau_grade", "nom"]

    def get_queryset(self):
        return Diplome.objects.select_related("formation").prefetch_related("cessions")

    @action(detail=True, methods=["get"])
    def cessions(self, request, pk=None):
        """Liste les cessions du diplôme."""
        diplome = self.get_object()
        cessions = diplome.cessions.select_related(
            "etudiant__user", "annee_universitaire"
        ).order_by("-date_obtention")
        serializer = CessionDiplomeListSerializer(cessions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques du diplôme."""
        diplome = self.get_object()
        cessions = diplome.cessions.all()
        stats = {
            "total_delivres": cessions.count(),
        }
        by_annee = cessions.values("annee_universitaire__libelle").annotate(
            count=Count("id")
        )
        stats["par_annee"] = {
            a["annee_universitaire__libelle"]: a["count"] for a in by_annee
        }
        by_mention = (
            cessions.exclude(mention="").values("mention").annotate(count=Count("id"))
        )
        stats["par_mention"] = {m["mention"]: m["count"] for m in by_mention}
        return Response(stats)


class CessionsDiplomesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour cessions de diplômes."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["diplome", "annee_universitaire", "etudiant"]
    search_fields = ["etudiant__user__last_name", "numero_serie"]
    ordering = ["-date_obtention"]

    def get_queryset(self):
        return CessionDiplome.objects.select_related(
            "etudiant__user", "diplome", "annee_universitaire", "signe_par"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CessionDiplomeListSerializer
        return CessionDiplomeDetailSerializer

    def perform_create(self, serializer):
        # Générer numéro de série unique
        numero_serie = f"DIP-{uuid.uuid4().hex[:8].upper()}"
        serializer.save(numero_serie=numero_serie)

    @action(detail=True, methods=["post"])
    @enforce_financial_clearance(
        candidates_getter=lambda _view, request, cession: [
            {"scope": "academic_year", "context": {"academic_year_id": cession.annee_universitaire_id}},
            {"scope": "tenant", "context": {"tenant_id": getattr(request.tenant, "id", None)}},
        ],
        subject_getter=lambda _view, _request, cession: cession.etudiant,
        academic_year_ids_getter=lambda _view, _request, cession: [cession.annee_universitaire_id],
        invoice_model_label="paiements.FactureFrais",
        invoice_subject_field="etudiant",
        invoice_year_lookup="type_frais__annee_universitaire_id",
        message="La signature du diplôme exige une situation financière régularisée.",
    )
    def signer(self, request, pk=None):
        """Signe le diplôme."""
        cession = get_action_object(self)
        if cession.date_signature:
            return Response({"error": "Déjà signé."}, status=400)

        from django.utils import timezone

        cession.signe_par = request.user
        cession.date_signature = timezone.now()
        cession.qr_verification = f"https://verif.univ.fr/{cession.numero_serie}"
        cession.save(update_fields=["signe_par", "date_signature", "qr_verification"])
        return Response({"detail": "Diplôme signé.", "id": cession.id})

    @action(detail=True, methods=["get"])
    def verifier(self, request, pk=None):
        """Vérifie l'authenticité du diplôme."""
        cession = self.get_object()
        return Response(
            {
                "valide": cession.date_signature is not None,
                "etudiant": cession.etudiant.user.get_full_name(),
                "diplome": cession.diplome.nom,
                "date_obtention": cession.date_obtention,
                "mention": cession.mention,
                "signe_le": cession.date_signature,
            }
        )
