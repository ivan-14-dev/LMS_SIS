"""URLs API for portail_parent."""

from rest_framework.routers import DefaultRouter

from .api import PortailParentViewSet

app_name = "portail_parent_api"

router = DefaultRouter()
router.register("", PortailParentViewSet, basename="portail-parent")

urlpatterns = router.urls
