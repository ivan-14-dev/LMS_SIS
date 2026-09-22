"""URLs API for presences."""

from rest_framework.routers import DefaultRouter

from .api import AppelsViewSet, JustificatifsViewSet, PresencesViewSet

app_name = "presences_api"

router = DefaultRouter()
router.register("appels", AppelsViewSet, basename="appel")
router.register("presences", PresencesViewSet, basename="presence")
router.register("justificatifs", JustificatifsViewSet, basename="justificatif")

urlpatterns = router.urls
