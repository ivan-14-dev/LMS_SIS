"""URLs API for bibliotheque."""

from rest_framework.routers import DefaultRouter

from .api import (
    EmpruntsViewSet,
    ExemplairesViewSet,
    LivresViewSet,
    ReservationsViewSet,
)

app_name = "bibliotheque_api"

router = DefaultRouter()
router.register("livres", LivresViewSet, basename="livre")
router.register("exemplaires", ExemplairesViewSet, basename="exemplaire")
router.register("emprunts", EmpruntsViewSet, basename="emprunt")
router.register("reservations-bibliotheque", ReservationsViewSet, basename="reservation-bibliotheque")

urlpatterns = router.urls
