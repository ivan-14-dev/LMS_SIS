"""URLs API for discipline."""

from rest_framework.routers import DefaultRouter

from .api import ConseilsDisciplineViewSet, IncidentsViewSet, SanctionsViewSet

app_name = "discipline_api"

router = DefaultRouter()
router.register("incidents", IncidentsViewSet, basename="incident")
router.register("sanctions", SanctionsViewSet, basename="sanction")
router.register("conseils-discipline", ConseilsDisciplineViewSet, basename="conseil-discipline")

urlpatterns = router.urls
