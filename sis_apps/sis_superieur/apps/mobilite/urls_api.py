"""URLs API for mobilite."""

from rest_framework.routers import DefaultRouter

from .api import (
    AccordsEtudesViewSet,
    CandidaturesMobiliteViewSet,
    ProgrammesMobiliteViewSet,
)

app_name = "mobilite_api"

router = DefaultRouter()
router.register("programmes-mobilite", ProgrammesMobiliteViewSet, basename="programme-mobilite")
router.register("candidatures-mobilite", CandidaturesMobiliteViewSet, basename="candidature-mobilite")
router.register("accords-etudes", AccordsEtudesViewSet, basename="accord-etudes")

urlpatterns = router.urls
