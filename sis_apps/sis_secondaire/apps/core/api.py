"""API views for core."""

from apps.core.models import WorkflowNotification
from apps.core.serializers import WorkflowNotificationSerializer
from rest_framework import mixins, permissions, response, status, viewsets
from rest_framework.decorators import action


class WorkflowNotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Notifications de workflow de l'utilisateur courant."""

    serializer_class = WorkflowNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = WorkflowNotification.objects.filter(
            recipient=self.request.user
        ).select_related("event", "event__actor")
        if self.request.query_params.get("non_lues") == "1":
            queryset = queryset.filter(is_read=False)
        return queryset.order_by("-created_at")

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
