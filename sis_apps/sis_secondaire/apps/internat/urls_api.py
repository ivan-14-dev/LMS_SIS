"""URLs API for internat."""

from rest_framework.routers import DefaultRouter

from .api import (
    BatimentsInternatViewSet,
    ChambresViewSet,
    EtudesSurveilleesViewSet,
    OccupantsChambresViewSet,
)

app_name = "internat_api"

router = DefaultRouter()
router.register("batiments", BatimentsInternatViewSet, basename="batiment-internat")
router.register("chambres", ChambresViewSet, basename="chambre")
router.register("occupants-chambres", OccupantsChambresViewSet, basename="occupant-chambre")
router.register("etudes-surveillees", EtudesSurveilleesViewSet, basename="etude-surveillee")

urlpatterns = router.urls
