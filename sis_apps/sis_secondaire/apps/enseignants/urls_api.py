"""URLs API for enseignants."""

from rest_framework.routers import DefaultRouter

from .api import AffectationEnseignantViewSet, MatiereEnseigneeViewSet, PersonnelViewSet

app_name = "enseignants_api"

router = DefaultRouter()
router.register("personnel", PersonnelViewSet, basename="personnel")
router.register("matieres", MatiereEnseigneeViewSet, basename="matiere-enseignee")
router.register("affectations", AffectationEnseignantViewSet, basename="affectation")

urlpatterns = router.urls
