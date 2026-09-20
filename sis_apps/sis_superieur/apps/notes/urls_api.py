"""URLs API for notes."""

from rest_framework.routers import DefaultRouter

from .api import (
    EvaluationsViewSet,
    MoyennesECUEViewSet,
    MoyennesUEViewSet,
    NotesViewSet,
    ReglesValidationViewSet,
)

app_name = "notes_api"

router = DefaultRouter()
router.register("evaluations", EvaluationsViewSet, basename="evaluation")
router.register("notes", NotesViewSet, basename="note")
router.register("moyennes-ecue", MoyennesECUEViewSet, basename="moyenne-ecue")
router.register("moyennes-ue", MoyennesUEViewSet, basename="moyenne-ue")
router.register("regles-validation", ReglesValidationViewSet, basename="regle-validation")

urlpatterns = router.urls
