"""URLs API for portail_enseignant."""

from rest_framework.routers import DefaultRouter

from .api import PortailEnseignantViewSet

app_name = "portail_enseignant_api"

router = DefaultRouter()
router.register("", PortailEnseignantViewSet, basename="portail-enseignant")

urlpatterns = router.urls
