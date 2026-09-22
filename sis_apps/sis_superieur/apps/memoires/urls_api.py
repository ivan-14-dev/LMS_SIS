"""URLs API for memoires."""

from rest_framework.routers import DefaultRouter

from .api import JurysMemoireViewSet, MemoiresViewSet, SujetsMemoireViewSet

app_name = "memoires_api"

router = DefaultRouter()
router.register("sujets-memoire", SujetsMemoireViewSet, basename="sujet-memoire")
router.register("jurys-memoire", JurysMemoireViewSet, basename="jury-memoire")
router.register("", MemoiresViewSet, basename="memoire")

urlpatterns = router.urls
