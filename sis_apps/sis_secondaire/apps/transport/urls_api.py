"""URLs API for transport."""

from rest_framework.routers import DefaultRouter

from .api import (
    ArretsViewSet,
    InscriptionsTransportViewSet,
    LignesTransportViewSet,
    VehiculesViewSet,
)

app_name = "transport_api"

router = DefaultRouter()
router.register("lignes-transport", LignesTransportViewSet, basename="ligne-transport")
router.register("arrets", ArretsViewSet, basename="arret")
router.register("vehicules", VehiculesViewSet, basename="vehicule")
router.register("inscriptions-transport", InscriptionsTransportViewSet, basename="inscription-transport")

urlpatterns = router.urls
