"""API URLs for etablissement."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from sis_common.learning_offerings import OfferingCatalogueView

from .api import (
    AnneesUniversitairesViewSet,
    ConfigurationHierarchyView,
    CurrentUniversiteView,
    ModulesView,
    OfferingPreviewView,
    SemestresViewSet,
    UnitsViewSet,
)

app_name = "etablissement_api"

urlpatterns = [
    path("learning-offerings/", OfferingCatalogueView.as_view(), name="learning-offerings"),
    path("current/", CurrentUniversiteView.as_view(), name="current"),
    path("current/modules/", ModulesView.as_view(), name="modules"),
    path("current/hierarchy/", ConfigurationHierarchyView.as_view(), name="configuration-hierarchy"),
    path("current/offering-preview/", OfferingPreviewView.as_view(), name="offering-preview"),
]

router = DefaultRouter()
router.register("unites", UnitsViewSet, basename="organisation-unit")
router.register("annees", AnneesUniversitairesViewSet, basename="annee-universitaire")
router.register("semestres", SemestresViewSet, basename="semestre")
urlpatterns += router.urls
