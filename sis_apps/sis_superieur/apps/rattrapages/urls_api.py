"""URLs API for rattrapages."""

from rest_framework.routers import DefaultRouter

from .api import InscriptionsRattrapageViewSet

app_name = "rattrapages_api"

router = DefaultRouter()
router.register("", InscriptionsRattrapageViewSet, basename="inscription-rattrapage")

urlpatterns = router.urls
