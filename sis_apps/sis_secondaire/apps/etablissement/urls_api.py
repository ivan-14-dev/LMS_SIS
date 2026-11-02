"""API URLs for etablissement."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from sis_common.learning_offerings import OfferingCatalogueView

from .api import (
    AnneesScolairesViewSet,
    CurrentEtablissementView,
    NiveauxViewSet,
    OfferingPreviewView,
    PeriodesViewSet,
)

app_name = "etablissement_api"

urlpatterns = [
    path("learning-offerings/", OfferingCatalogueView.as_view(), name="learning-offerings"),
    path("current/", CurrentEtablissementView.as_view(), name="current"),
    path("current/offering-preview/", OfferingPreviewView.as_view(), name="offering-preview"),
]

router = DefaultRouter()
router.register("annees", AnneesScolairesViewSet, basename="annee-scolaire")
router.register("periodes", PeriodesViewSet, basename="periode")
router.register("niveaux", NiveauxViewSet, basename="niveau")
urlpatterns += router.urls
