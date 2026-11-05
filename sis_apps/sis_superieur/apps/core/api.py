"""API views for core."""

from apps.core.models import WorkflowEvent, WorkflowNotification
from apps.core.serializers import WorkflowNotificationSerializer
from django.db.models import Count
from rest_framework import mixins, permissions, response, status, viewsets
from rest_framework.decorators import action

from sis_common.authorization import has_business_permission_or_role
from sis_common.notification_channels import (
    notification_matches_delivery_filters,
    summarize_notification_deliveries,
    summarize_notification_delivery_trends,
)
from sis_common.reporting import configured_report, export_queryset
from sis_common.workflow_filters import EVENT_FILTERS, PRIVATE_WORKFLOW_MODELS, filter_events, validated_event_filters

from .serializers import WorkflowEventSerializer

EVENT_REPORT_FIELDS = {
    "action": ("Action", "action"),
    "title": ("Titre", "title"),
    "app_label": ("Module", "app_label"),
    "model": ("Modèle", "model"),
    "object_repr": ("Objet", "object_repr"),
    "actor": ("Acteur", "actor__username"),
    "tenant_id": ("Tenant", "tenant_id"),
    "request_id": ("Requête", "request_id"),
    "created_at": ("Date", "created_at"),
}
EVENT_REPORT_FILTERS = EVENT_FILTERS
EVENT_REPORT_GROUPS = {
    "action": "action",
    "app_label": "app_label",
    "model": "model",
}


class IsWorkflowAuditor(permissions.IsAuthenticated):
    """Accès lecture réservé au pilotage métier et audit."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and has_business_permission_or_role(
            request.user,
            "core.view_workflowevent",
            (
                "president",
                "vice_president",
                "doyen",
                "directeur_etudes",
                "responsable_formation",
                "scolarite",
                "comptable",
            ),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=(
                "finance_manager_superieur",
                "document_signatory_superieur",
                "academic_registry_superieur",
                "exam_manager_superieur",
            ),
        )


class WorkflowEventViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Historique global des événements de workflow."""

    serializer_class = WorkflowEventSerializer
    permission_classes = [IsWorkflowAuditor]

    def get_queryset(self):
        queryset = WorkflowEvent.objects.exclude(app_label="core", model__in=PRIVATE_WORKFLOW_MODELS).select_related(
            "actor"
        )
        tenant_id = getattr(getattr(self.request, "tenant", None), "id", None)
        if tenant_id is not None:
            queryset = queryset.filter(tenant_id=tenant_id)
        return filter_events(queryset, self.request.query_params.dict()).order_by("-created_at", "-id")

    @action(detail=False, methods=["get"])
    def acteurs(self, request):
        rows = (
            self.get_queryset()
            .exclude(actor=None)
            .order_by("actor__username")
            .values("actor_id", "actor__username", "actor__first_name", "actor__last_name")
            .distinct()
        )
        return response.Response(
            [
                {
                    "id": row["actor_id"],
                    "nom": " ".join(value for value in (row["actor__first_name"], row["actor__last_name"]) if value)
                    or row["actor__username"],
                }
                for row in rows
            ]
        )

    @action(detail=False, methods=["get"])
    def bilan(self, request):
        group_by = request.query_params.get("group_by", "action")
        group_field = EVENT_REPORT_GROUPS.get(group_by)
        if not group_field:
            return response.Response(
                {"group_by": f"Valeurs acceptées: {', '.join(EVENT_REPORT_GROUPS)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows = self.get_queryset().values(group_field).annotate(nombre=Count("id")).order_by(group_field)
        return response.Response([{"groupe": row[group_field], "nombre": row["nombre"]} for row in rows])

    @action(detail=False, methods=["post"])
    def exporter(self, request):
        report = configured_report(
            request,
            request.data.get("report"),
            allowed_datasets={"workflow_events"},
        )
        return export_queryset(
            request,
            self.get_queryset(),
            report,
            EVENT_REPORT_FIELDS,
            EVENT_REPORT_FILTERS,
            validated_event_filters(request.data.get("filters", {})),
        )


class WorkflowNotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Notifications de workflow de l'utilisateur courant."""

    serializer_class = WorkflowNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _apply_delivery_filters(self, queryset):
        category = self.request.query_params.get("category", "").strip()
        if category:
            queryset = queryset.filter(category=category)
        channel = self.request.query_params.get("delivery_channel", "").strip()
        delivery_status = self.request.query_params.get("delivery_status", "").strip()
        if channel or delivery_status:
            matching_ids = [
                notification.id
                for notification in queryset
                if notification_matches_delivery_filters(notification, channel=channel, status=delivery_status)
            ]
            queryset = queryset.filter(id__in=matching_ids)
        return queryset

    def get_queryset(self):
        queryset = WorkflowNotification.objects.filter(recipient=self.request.user).select_related(
            "event", "event__actor"
        )
        if self.request.query_params.get("non_lues") == "1":
            queryset = queryset.filter(is_read=False)
        return self._apply_delivery_filters(queryset).order_by("-created_at")

    @action(detail=True, methods=["post"])
    def marquer_lue(self, request, pk=None):
        notification = self.get_object()
        notification.mark_read()
        return response.Response(
            self.get_serializer(notification).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def tout_marquer_lu(self, request):
        for notification in self.get_queryset().filter(is_read=False):
            notification.mark_read()
        return response.Response({"detail": "Notifications marquées comme lues."})

    @action(detail=False, methods=["get"])
    def bilan_livraison(self, request):
        queryset = self.get_queryset()
        return response.Response(summarize_notification_deliveries(queryset))

    @action(detail=False, methods=["get"])
    def tendances_livraison(self, request):
        queryset = self.get_queryset()
        return response.Response(summarize_notification_delivery_trends(queryset))
