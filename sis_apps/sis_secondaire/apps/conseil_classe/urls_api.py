"""URLs API for conseil_classe."""

from rest_framework.routers import DefaultRouter

from .api import ConseilsClasseViewSet

app_name = "conseil_classe_api"

router = DefaultRouter()
router.register("conseils-classe", ConseilsClasseViewSet, basename="conseil-classe")

urlpatterns = router.urls
