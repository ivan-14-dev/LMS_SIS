"""URLs API for enseignants."""

from rest_framework.routers import DefaultRouter

from .api import AffectationsViewSet, EnseignantsViewSet

app_name = "enseignants_api"

router = DefaultRouter()
router.register("affectations", AffectationsViewSet, basename="affectation")
router.register("", EnseignantsViewSet, basename="enseignant")

urlpatterns = router.urls
