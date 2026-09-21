"""API URLs for inscriptions."""

from rest_framework.routers import DefaultRouter

from .api import InscriptionsViewSet

app_name = "inscriptions_api"

router = DefaultRouter()
router.register("", InscriptionsViewSet, basename="inscription")

urlpatterns = router.urls
