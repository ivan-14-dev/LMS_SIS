"""URLs API for UE et ECUE."""

from rest_framework.routers import DefaultRouter

from .api import ECUEViewSet, PrerequisViewSet, UEViewSet

app_name = "ue_ecue_api"

router = DefaultRouter()
router.register("ues", UEViewSet, basename="ue")
router.register("ecues", ECUEViewSet, basename="ecue")
router.register("prerequis", PrerequisViewSet, basename="prerequis")

urlpatterns = router.urls
