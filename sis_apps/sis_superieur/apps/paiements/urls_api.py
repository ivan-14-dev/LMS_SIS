"""URLs API for paiements."""

from rest_framework.routers import DefaultRouter

from .api import FacturesViewSet, PaiementsViewSet, TypesFraisViewSet

app_name = "paiements_api"

router = DefaultRouter()
router.register("rubriques", TypesFraisViewSet, basename="rubrique-paiement")
router.register("factures", FacturesViewSet, basename="facture")
router.register("transactions", PaiementsViewSet, basename="paiement")

urlpatterns = router.urls
