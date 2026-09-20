"""URLs API for notes."""

from rest_framework.routers import DefaultRouter

from .api import (
    BulletinsViewSet,
    EvaluationsViewSet,
    NotesViewSet,
    ReglesValidationViewSet,
)

app_name = "notes_api"

router = DefaultRouter()
router.register("evaluations", EvaluationsViewSet, basename="evaluation")
router.register("notes", NotesViewSet, basename="note")
router.register("bulletins", BulletinsViewSet, basename="bulletin")
router.register("regles-validation", ReglesValidationViewSet, basename="regle-validation")

urlpatterns = router.urls
