"""URLs API for bourses."""

from rest_framework.routers import DefaultRouter

from .api import (
    AttributionBourseViewSet,
    DemandeBourseViewSet,
    TypeBourseViewSet,
    VersementBourseViewSet,
)

app_name = "bourses_api"

router = DefaultRouter()
router.register("types-bourses", TypeBourseViewSet, basename="type-bourse")
router.register("demandes-bourses", DemandeBourseViewSet, basename="demande-bourse")
router.register("attributions-bourses", AttributionBourseViewSet, basename="attribution-bourse")
router.register("versements-bourses", VersementBourseViewSet, basename="versement-bourse")

urlpatterns = router.urls
