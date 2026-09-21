"""API views for conseil de classe (ViewSets DRF) - SIS Secondaire."""

from apps.core.serializers import WorkflowEventSerializer
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import request_has_business_access
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

from .models import AppreciationConseil, ConseilClasse, DecisionConseil
from .serializers import (
    AppreciationConseilSerializer,
    ConseilClasseDetailSerializer,
    ConseilClasseListSerializer,
    DecisionConseilSerializer,
)


def _conseil_notification_recipients(request, conseil):
    recipients = []
    for profile in (conseil.president, conseil.secretaire):
        user = getattr(profile, "user", None)
        if user is not None and user not in recipients:
            recipients.append(user)
    actor = getattr(request, "user", None)
    if getattr(actor, "is_authenticated", False) and actor not in recipients:
        recipients.append(actor)
    return recipients


class IsDirectionOrReadOnly(IsAuthenticated):
    """Permission: direction pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "conseil_classe.change_conseilclasse",
            ("directeur", "proviseur", "principal", "cpe", "pp"),
            tenant_group_codes=("class_council_manager_secondary",),
        )


class ConseilsClasseViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour conseils de classe."""

    permission_classes = [IsDirectionOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["classe", "periode", "statut"]
    ordering = ["-date"]

    def get_queryset(self):
        return ConseilClasse.objects.select_related(
            "classe", "periode", "president", "secretaire"
        ).prefetch_related("participants", "decisions")

    def get_serializer_class(self):
        if self.action == "list":
            return ConseilClasseListSerializer
        return ConseilClasseDetailSerializer

    def perform_create(self, serializer):
        conseil = serializer.save()
        record_workflow_event(
            self.request,
            conseil,
            "creation",
            "Conseil de classe créé",
            message=f"Le conseil de classe de {conseil.classe} a été créé.",
            recipients=_conseil_notification_recipients(self.request, conseil),
            metadata={"classe_id": conseil.classe_id, "periode_id": conseil.periode_id},
        )

    def perform_update(self, serializer):
        conseil = serializer.save()
        record_workflow_event(
            self.request,
            conseil,
            "mise_a_jour",
            "Conseil de classe mis à jour",
            message=f"Le conseil de classe de {conseil.classe} a été mis à jour.",
            recipients=_conseil_notification_recipients(self.request, conseil),
            metadata={"classe_id": conseil.classe_id, "periode_id": conseil.periode_id},
        )

    def perform_destroy(self, instance):
        record_workflow_event(
            self.request,
            instance,
            "suppression",
            "Conseil de classe supprimé",
            message=f"Le conseil de classe de {instance.classe} a été supprimé.",
            recipients=_conseil_notification_recipients(self.request, instance),
            metadata={"classe_id": instance.classe_id, "periode_id": instance.periode_id},
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def decisions(self, request, pk=None):
        """Liste les décisions du conseil."""
        conseil = self.get_object()
        decisions = conseil.decisions.select_related("eleve__user").order_by("rang")
        serializer = DecisionConseilSerializer(decisions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        """Valide le conseil de classe."""
        conseil = self.get_object()
        if conseil.statut != "tenu":
            return Response({"error": "Le conseil doit d'abord être tenu."}, status=400)
        conseil.statut = "valide"
        conseil.save(update_fields=["statut"])
        record_workflow_event(
            request,
            conseil,
            "validation",
            "Conseil validé",
            message=f"Le conseil de classe de {conseil.classe} a été validé.",
            recipients=_conseil_notification_recipients(request, conseil),
            metadata={"classe_id": conseil.classe_id, "periode_id": conseil.periode_id},
        )
        return Response({"detail": "Conseil validé.", "id": conseil.id})

    @action(detail=True, methods=["post"])
    def tenir(self, request, pk=None):
        """Marque le conseil comme tenu."""
        conseil = self.get_object()
        if conseil.statut != "planifie":
            return Response({"error": "Statut invalide."}, status=400)
        conseil.statut = "tenu"
        conseil.save(update_fields=["statut"])
        record_workflow_event(
            request,
            conseil,
            "tenue",
            "Conseil tenu",
            message=f"Le conseil de classe de {conseil.classe} a été marqué comme tenu.",
            recipients=_conseil_notification_recipients(request, conseil),
            metadata={"classe_id": conseil.classe_id, "periode_id": conseil.periode_id},
        )
        return Response({"detail": "Conseil marqué comme tenu.", "id": conseil.id})

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques du conseil."""
        conseil = self.get_object()
        decisions = conseil.decisions.all()
        stats = decisions.values("decision").annotate(count=Count("id"))
        return Response(
            {
                "nb_eleves": decisions.count(),
                "par_decision": {d["decision"]: d["count"] for d in stats},
            }
        )

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow du conseil de classe."""
        conseil = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(conseil), many=True)
        return Response(serializer.data)


class DecisionsConseilViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour décisions de conseil."""

    permission_classes = [IsDirectionOrReadOnly]
    serializer_class = DecisionConseilSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["conseil", "eleve", "decision"]
    ordering = ["rang"]

    def get_queryset(self):
        return DecisionConseil.objects.select_related("conseil", "eleve__user")


class AppreciationsConseilViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour appréciations."""

    permission_classes = [IsDirectionOrReadOnly]
    serializer_class = AppreciationConseilSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["conseil", "eleve"]

    def get_queryset(self):
        return AppreciationConseil.objects.select_related("conseil", "eleve__user")
