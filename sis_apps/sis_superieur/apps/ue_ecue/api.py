"""API views for UE/ECUE (ViewSets DRF) - SIS Supérieur."""

from apps.core.serializers import WorkflowEventSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import has_business_permission_or_role
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

from .models import ECUE, UE, Prerequis
from .serializers import ECUESerializer, PrerequisSerializer, UEDetailSerializer, UEListSerializer


def _ue_recipients(request, ue=None):
    formation = getattr(getattr(getattr(ue, "maquette", None), "formation", None), "responsable", None)
    recipient = getattr(formation, "user", None)
    recipients = [recipient] if recipient is not None else []
    actor = getattr(request, "user", None)
    if getattr(actor, "is_authenticated", False) and actor not in recipients:
        recipients.append(actor)
    return recipients


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return has_business_permission_or_role(
            user,
            "ue_ecue.change_ue",
            ("scolarite", "directeur_etudes", "responsable_formation", "doyen"),
        )


class UEViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour UE."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["maquette", "semestre", "type"]
    search_fields = ["code", "nom", "description"]
    ordering_fields = ["code", "semestre", "credits_ects"]
    ordering = ["semestre", "code"]

    def get_queryset(self):
        return UE.objects.select_related("maquette__formation", "semestre").prefetch_related("parcours_autorises")

    def get_serializer_class(self):
        if self.action == "list":
            return UEListSerializer
        return UEDetailSerializer

    def perform_create(self, serializer):
        ue = serializer.save()
        record_workflow_event(
            self.request,
            ue,
            "creation",
            "UE créée",
            message=f"L'UE {ue.nom} a été créée.",
            recipients=_ue_recipients(self.request, ue),
            metadata={"maquette_id": ue.maquette_id, "semestre_id": ue.semestre_id},
        )

    def perform_update(self, serializer):
        ue = serializer.save()
        record_workflow_event(
            self.request,
            ue,
            "mise_a_jour",
            "UE mise à jour",
            message=f"L'UE {ue.nom} a été mise à jour.",
            recipients=_ue_recipients(self.request, ue),
            metadata={"maquette_id": ue.maquette_id, "semestre_id": ue.semestre_id},
        )

    def perform_destroy(self, instance):
        record_workflow_event(
            self.request,
            instance,
            "suppression",
            "UE supprimée",
            message=f"L'UE {instance.nom} a été supprimée.",
            recipients=_ue_recipients(self.request, instance),
            metadata={"maquette_id": instance.maquette_id, "semestre_id": instance.semestre_id},
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def ecues(self, request, pk=None):
        """Liste les ECUE de l'UE."""
        ue = self.get_object()
        ecues = ue.ecues.all().order_by("code")
        serializer = ECUESerializer(ecues, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def prerequis(self, request, pk=None):
        """Liste les prérequis de l'UE."""
        ue = self.get_object()
        prerequis = ue.prerequis_requis.select_related("ue_prereq")
        serializer = PrerequisSerializer(prerequis, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def est_prerequis_de(self, request, pk=None):
        """Liste les UE pour lesquelles cette UE est prérequis."""
        ue = self.get_object()
        prerequis = ue.est_prerequis_de.select_related("ue_cible")
        serializer = PrerequisSerializer(prerequis, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow de l'UE."""
        ue = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(ue), many=True)
        return Response(serializer.data)


class ECUEViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour ECUE."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = ECUESerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["ue", "ue__maquette", "ue__semestre"]
    search_fields = ["code", "nom", "description"]
    ordering = ["ue__code", "code"]

    def get_queryset(self):
        return ECUE.objects.select_related("ue")

    def perform_create(self, serializer):
        ecue = serializer.save()
        record_workflow_event(
            self.request,
            ecue,
            "creation",
            "ECUE créé",
            message=f"L'ECUE {ecue.nom} a été créé.",
            recipients=_ue_recipients(self.request, ecue.ue),
            metadata={"ue_id": ecue.ue_id},
        )

    def perform_update(self, serializer):
        ecue = serializer.save()
        record_workflow_event(
            self.request,
            ecue,
            "mise_a_jour",
            "ECUE mis à jour",
            message=f"L'ECUE {ecue.nom} a été mis à jour.",
            recipients=_ue_recipients(self.request, ecue.ue),
            metadata={"ue_id": ecue.ue_id},
        )

    def perform_destroy(self, instance):
        record_workflow_event(
            self.request,
            instance,
            "suppression",
            "ECUE supprimé",
            message=f"L'ECUE {instance.nom} a été supprimé.",
            recipients=_ue_recipients(self.request, instance.ue),
            metadata={"ue_id": instance.ue_id},
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def enseignants(self, request, pk=None):
        """Liste les enseignants affectés à l'ECUE."""
        ecue = self.get_object()
        from apps.enseignants.models import AffectationEnseignement
        from apps.enseignants.serializers import AffectationEnseignementSerializer

        affectations = AffectationEnseignement.objects.filter(ecue=ecue).select_related("enseignant__user")
        serializer = AffectationEnseignementSerializer(affectations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow de l'ECUE."""
        ecue = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(ecue), many=True)
        return Response(serializer.data)


class PrerequisViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour prérequis."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = PrerequisSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["ue_cible", "ue_prereq", "type"]

    def get_queryset(self):
        return Prerequis.objects.select_related("ue_cible", "ue_prereq")

    def perform_create(self, serializer):
        prerequis = serializer.save()
        record_workflow_event(
            self.request,
            prerequis,
            "creation",
            "Prérequis créé",
            message=f"Le prérequis entre {prerequis.ue_prereq} et {prerequis.ue_cible} a été créé.",
            recipients=_ue_recipients(self.request, prerequis.ue_cible),
            metadata={"ue_cible_id": prerequis.ue_cible_id, "ue_prereq_id": prerequis.ue_prereq_id},
        )

    def perform_update(self, serializer):
        prerequis = serializer.save()
        record_workflow_event(
            self.request,
            prerequis,
            "mise_a_jour",
            "Prérequis mis à jour",
            message=f"Le prérequis entre {prerequis.ue_prereq} et {prerequis.ue_cible} a été mis à jour.",
            recipients=_ue_recipients(self.request, prerequis.ue_cible),
            metadata={"ue_cible_id": prerequis.ue_cible_id, "ue_prereq_id": prerequis.ue_prereq_id},
        )

    def perform_destroy(self, instance):
        record_workflow_event(
            self.request,
            instance,
            "suppression",
            "Prérequis supprimé",
            message=f"Le prérequis entre {instance.ue_prereq} et {instance.ue_cible} a été supprimé.",
            recipients=_ue_recipients(self.request, instance.ue_cible),
            metadata={"ue_cible_id": instance.ue_cible_id, "ue_prereq_id": instance.ue_prereq_id},
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow du prérequis."""
        prerequis = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(prerequis), many=True)
        return Response(serializer.data)
