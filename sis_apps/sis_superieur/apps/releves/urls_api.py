"""URLs API for releves."""

from rest_framework.routers import DefaultRouter

from .api import AttestationsViewSet, RelevesNotesViewSet, TranscriptsViewSet

app_name = "releves_api"

router = DefaultRouter()
router.register("transcripts", TranscriptsViewSet, basename="transcript")
router.register("attestations", AttestationsViewSet, basename="attestation")
router.register("", RelevesNotesViewSet, basename="releve")

urlpatterns = router.urls
