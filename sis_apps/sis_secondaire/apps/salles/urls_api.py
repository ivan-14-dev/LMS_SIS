"""URLs API for salles."""

from rest_framework.routers import DefaultRouter

from .api import EquipementsViewSet, SallesViewSet

app_name = "salles_api"

router = DefaultRouter()
router.register("equipements", EquipementsViewSet, basename="equipement")
router.register("", SallesViewSet, basename="salle")

urlpatterns = router.urls
