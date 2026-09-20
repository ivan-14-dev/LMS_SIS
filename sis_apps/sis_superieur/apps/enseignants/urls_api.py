"""URLs API for enseignants."""

from rest_framework.routers import DefaultRouter

from .api import AffectationsViewSet, EnseignantsViewSet

app_name = "enseignants_api"

router = DefaultRouter()
router.register("enseignants", EnseignantsViewSet, basename="enseignant")
router.register("affectations", AffectationsViewSet, basename="affectation")

urlpatterns = router.urls
