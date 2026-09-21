"""API URLs for core."""

from apps.core.api import WorkflowEventViewSet, WorkflowNotificationViewSet
from rest_framework.routers import DefaultRouter

app_name = "core_api"

router = DefaultRouter()
router.register("workflow-events", WorkflowEventViewSet, basename="workflow-event")
router.register("notifications", WorkflowNotificationViewSet, basename="notifications")

urlpatterns = router.urls
