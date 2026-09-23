"""URLs API for emplois_du_temps."""

from rest_framework.routers import DefaultRouter

from .api import (
    BatimentViewSet,
    ConflitHoraireViewSet,
    CreneauCoursViewSet,
    CreneauHoraireViewSet,
    ReservationViewSet,
    SalleViewSet,
)

app_name = "emplois_du_temps_api"

router = DefaultRouter()
router.register("batiments", BatimentViewSet, basename="batiment")
router.register("salles", SalleViewSet, basename="salle")
router.register("creneaux-horaires", CreneauHoraireViewSet, basename="creneau-horaire")
router.register("creneaux-cours", CreneauCoursViewSet, basename="creneau-cours")
router.register("reservations", ReservationViewSet, basename="reservation")
router.register("conflits-horaires", ConflitHoraireViewSet, basename="conflit-horaire")

urlpatterns = router.urls
