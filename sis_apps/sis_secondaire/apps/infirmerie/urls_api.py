"""URLs API for infirmerie."""

from rest_framework.routers import DefaultRouter

from .api import DossiersMedicauxViewSet, StockMedicamentsViewSet, VisitesInfirmerieViewSet

app_name = "infirmerie_api"

router = DefaultRouter()
router.register("dossiers-medicaux", DossiersMedicauxViewSet, basename="dossier-medical")
router.register("visites-infirmerie", VisitesInfirmerieViewSet, basename="visite-infirmerie")
router.register("stock-medicaments", StockMedicamentsViewSet, basename="stock-medicament")

urlpatterns = router.urls
