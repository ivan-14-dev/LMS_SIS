"""URLs API for formations."""

from rest_framework.routers import DefaultRouter

from .api import FormationsViewSet, MaquettesViewSet, ParcoursViewSet

app_name = "formations_api"

router = DefaultRouter()
router.register("formations", FormationsViewSet, basename="formation")
router.register("parcours", ParcoursViewSet, basename="parcours")
router.register("maquettes", MaquettesViewSet, basename="maquette")

urlpatterns = router.urls
