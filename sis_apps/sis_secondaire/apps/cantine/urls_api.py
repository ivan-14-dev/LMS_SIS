"""URLs API for cantine."""

from rest_framework.routers import DefaultRouter

from .api import InscriptionsCantineViewSet, MenusViewSet, PresencesCantineViewSet

app_name = "cantine_api"

router = DefaultRouter()
router.register("menus", MenusViewSet, basename="menu")
router.register("inscriptions-cantine", InscriptionsCantineViewSet, basename="inscription-cantine")
router.register("presences-cantine", PresencesCantineViewSet, basename="presence-cantine")

urlpatterns = router.urls
