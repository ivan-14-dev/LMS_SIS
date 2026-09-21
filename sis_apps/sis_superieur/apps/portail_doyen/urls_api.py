"""URLs API for portail_doyen."""

from rest_framework.routers import DefaultRouter

from .api import PortailDoyenViewSet

app_name = "portail_doyen_api"

router = DefaultRouter()
router.register("", PortailDoyenViewSet, basename="portail-doyen")

urlpatterns = router.urls
