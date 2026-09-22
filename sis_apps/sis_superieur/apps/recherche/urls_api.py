"""URLs API for recherche."""

from rest_framework.routers import DefaultRouter

from .api import (
    LaboratoiresViewSet,
    ProductionsScientifiquesViewSet,
    ProjetsRechercheViewSet,
    ThesesViewSet,
)

app_name = "recherche_api"

router = DefaultRouter()
router.register("laboratoires", LaboratoiresViewSet, basename="laboratoire")
router.register("projets-recherche", ProjetsRechercheViewSet, basename="projet-recherche")
router.register(
    "productions-scientifiques", ProductionsScientifiquesViewSet, basename="production-scientifique"
)
router.register("theses", ThesesViewSet, basename="these")

urlpatterns = router.urls
