"""URLs API for examens."""

from rest_framework.routers import DefaultRouter

from .api import (
    AffectationsCorrectionViewSet,
    ConvocationsExamenViewSet,
    CopiesExamenViewSet,
    CorrectionsCopieViewSet,
    EpreuvesExamenViewSet,
    SessionsExamenViewSet,
)

app_name = "examens_api"

router = DefaultRouter()
router.register("sessions", SessionsExamenViewSet, basename="session-examen")
router.register("epreuves", EpreuvesExamenViewSet, basename="epreuve-examen")
router.register(
    "convocations", ConvocationsExamenViewSet, basename="convocation-examen"
)
router.register("copies", CopiesExamenViewSet, basename="copie-examen")
router.register(
    "affectations-correction",
    AffectationsCorrectionViewSet,
    basename="affectation-correction",
)
router.register("corrections", CorrectionsCopieViewSet, basename="correction-copie")

urlpatterns = router.urls
