"""API URLs for evaluations."""

from rest_framework.routers import DefaultRouter

from .api import EvaluationsViewSet

app_name = "evaluations_api"

router = DefaultRouter()
router.register("", EvaluationsViewSet, basename="evaluation")

urlpatterns = router.urls
