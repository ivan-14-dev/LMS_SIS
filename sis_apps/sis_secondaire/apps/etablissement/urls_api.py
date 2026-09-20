"""API URLs for etablissement."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .api import (
    AnneesScolairesViewSet,
    CurrentEtablissementView,
    NiveauxViewSet,
    PeriodesViewSet,
)

app_name = "etablissement_api"

urlpatterns = [
    path("current/", CurrentEtablissementView.as_view(), name="current"),
]

router = DefaultRouter()
router.register("annees", AnneesScolairesViewSet, basename="annee-scolaire")
router.register("periodes", PeriodesViewSet, basename="periode")
router.register("niveaux", NiveauxViewSet, basename="niveau")
urlpatterns += router.urls
