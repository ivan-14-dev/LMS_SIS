"""URLs API for stages."""

from rest_framework.routers import DefaultRouter

from sis_common.practical_api import practical_urlpatterns

from .api import (
    CandidaturesStageViewSet,
    ConventionsStageViewSet,
    OffresStageViewSet,
)

app_name = "stages_api"

router = DefaultRouter()
router.register("offres-stage", OffresStageViewSet, basename="offre-stage")
router.register("candidatures-stage", CandidaturesStageViewSet, basename="candidature-stage")
router.register("conventions-stage", ConventionsStageViewSet, basename="convention-stage")

urlpatterns = practical_urlpatterns + router.urls
