"""URLs API for portail_etudiant."""

from rest_framework.routers import DefaultRouter

from .api import PortailEtudiantViewSet

app_name = "portail_etudiant_api"

router = DefaultRouter()
router.register("", PortailEtudiantViewSet, basename="portail-etudiant")

urlpatterns = router.urls
