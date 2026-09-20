"""URLs API for examens."""

from rest_framework.routers import DefaultRouter

from .api import (
    ConvocationsExamenViewSet,
    EpreuvesExamenViewSet,
    ResultatsExamenViewSet,
    SessionsExamenViewSet,
)

app_name = "examens_api"

router = DefaultRouter()
router.register("sessions", SessionsExamenViewSet, basename="session-examen")
router.register("epreuves", EpreuvesExamenViewSet, basename="epreuve-examen")
router.register(
    "convocations", ConvocationsExamenViewSet, basename="convocation-examen"
)
router.register("resultats", ResultatsExamenViewSet, basename="resultat-examen")

urlpatterns = router.urls
