"""URLs API for portail_scolarite."""

from rest_framework.routers import DefaultRouter

from .api import PortailScolariteViewSet

app_name = "portail_scolarite_api"

router = DefaultRouter()
router.register("", PortailScolariteViewSet, basename="portail-scolarite")

urlpatterns = router.urls
