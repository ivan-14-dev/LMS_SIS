"""URLs API for ects."""

from rest_framework.routers import DefaultRouter

from .api import BilansECTSViewSet

app_name = "ects_api"

router = DefaultRouter()
router.register("bilans-ects", BilansECTSViewSet, basename="bilan-ects")

urlpatterns = router.urls
