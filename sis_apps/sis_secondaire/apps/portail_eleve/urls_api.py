"""URLs API for portail_eleve."""

from rest_framework.routers import DefaultRouter

from .api import PortailEleveViewSet

app_name = "portail_eleve_api"

router = DefaultRouter()
router.register("", PortailEleveViewSet, basename="portail-eleve")

urlpatterns = router.urls
