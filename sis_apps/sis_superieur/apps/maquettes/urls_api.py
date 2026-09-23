"""URLs API for maquettes."""

from rest_framework.routers import DefaultRouter

from .api import MaquettesViewSet

app_name = "maquettes_api"

router = DefaultRouter()
router.register("", MaquettesViewSet, basename="maquette")

urlpatterns = router.urls
