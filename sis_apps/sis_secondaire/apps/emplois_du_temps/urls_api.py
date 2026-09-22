"""URLs API for emplois_du_temps."""

from rest_framework.routers import DefaultRouter

from .api import ContraintesViewSet, CreneauxViewSet

app_name = "emplois_du_temps_api"

router = DefaultRouter()
router.register("creneaux", CreneauxViewSet, basename="creneau")
router.register("contraintes", ContraintesViewSet, basename="contrainte")

urlpatterns = router.urls
