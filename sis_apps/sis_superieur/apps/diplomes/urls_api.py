"""URLs API for diplomes."""

from rest_framework.routers import DefaultRouter

from .api import AlumniConsentViewSet, CessionsDiplomesViewSet, DiplomesViewSet

app_name = "diplomes_api"

router = DefaultRouter()
router.register("catalogue", DiplomesViewSet, basename="diplome-catalogue")
router.register("alumni", AlumniConsentViewSet, basename="diplome-alumni")
router.register("", CessionsDiplomesViewSet, basename="diplome")

urlpatterns = router.urls
