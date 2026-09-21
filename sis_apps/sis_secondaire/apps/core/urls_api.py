"""API URLs for core."""

from apps.core.api import WorkflowNotificationViewSet
from rest_framework.routers import DefaultRouter

app_name = "core_api"

router = DefaultRouter()
router.register("notifications", WorkflowNotificationViewSet, basename="notifications")

urlpatterns = router.urls
