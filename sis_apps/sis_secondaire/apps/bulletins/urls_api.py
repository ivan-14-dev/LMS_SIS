"""URLs API for bulletins."""

from rest_framework.routers import DefaultRouter

from .api import AppreciationsMatiereViewSet, BulletinsViewSet

app_name = "bulletins_api"

router = DefaultRouter()
router.register("appreciations", AppreciationsMatiereViewSet, basename="appreciation-matiere")
router.register("", BulletinsViewSet, basename="bulletin")

urlpatterns = router.urls
