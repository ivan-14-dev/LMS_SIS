"""URLs API for stages."""

from rest_framework.routers import DefaultRouter

from .api import (
    ConventionsStageViewSet,
    EntreprisesStageViewSet,
    EvaluationsStageViewSet,
    SuivisStageViewSet,
)

app_name = "stages_api"

router = DefaultRouter()
router.register("entreprises-stage", EntreprisesStageViewSet, basename="entreprise-stage")
router.register("conventions-stage", ConventionsStageViewSet, basename="convention-stage")
router.register("suivis-stage", SuivisStageViewSet, basename="suivi-stage")
router.register("evaluations-stage", EvaluationsStageViewSet, basename="evaluation-stage")

urlpatterns = router.urls
