"""URLs API for bibliotheque."""

from rest_framework.routers import DefaultRouter

from .api import EmpruntsViewSet, ExemplairesViewSet, LivresViewSet

app_name = "bibliotheque_api"

router = DefaultRouter()
router.register("livres", LivresViewSet, basename="livre")
router.register("exemplaires", ExemplairesViewSet, basename="exemplaire")
router.register("emprunts", EmpruntsViewSet, basename="emprunt")

urlpatterns = router.urls
