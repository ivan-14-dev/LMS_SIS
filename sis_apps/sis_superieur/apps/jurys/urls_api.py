"""URLs API for jurys."""

from rest_framework.routers import DefaultRouter

from .api import (
    DecisionsGlobalesViewSet,
    DecisionsJuryViewSet,
    DeliberationsViewSet,
    JurysViewSet,
)

app_name = "jurys_api"

router = DefaultRouter()
router.register("jurys", JurysViewSet, basename="jury")
router.register("deliberations", DeliberationsViewSet, basename="deliberation")
router.register("decisions-jury", DecisionsJuryViewSet, basename="decision-jury")
router.register("decisions-globales", DecisionsGlobalesViewSet, basename="decision-globale")

urlpatterns = router.urls
