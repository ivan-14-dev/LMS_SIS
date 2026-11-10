"""API URLs for etablissement."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from sis_common.institution_workspace import InstitutionWorkspaceView
from sis_common.learning_offerings import OfferingCatalogueView

from .api import (
    AnneesScolairesViewSet,
    ConfigurationHierarchyView,
    CurrentEtablissementView,
    ModulesView,
    NiveauxViewSet,
    OfferingPreviewView,
    PeriodesViewSet,
    UnitsViewSet,
)

app_name = "etablissement_api"

urlpatterns = [
    path("current/workspace/", InstitutionWorkspaceView.as_view(), name="institution-workspace"),
    path("learning-offerings/", OfferingCatalogueView.as_view(), name="learning-offerings"),
    path("current/", CurrentEtablissementView.as_view(), name="current"),
    path("current/modules/", ModulesView.as_view(), name="modules"),
    path("current/hierarchy/", ConfigurationHierarchyView.as_view(), name="configuration-hierarchy"),
    path("current/offering-preview/", OfferingPreviewView.as_view(), name="offering-preview"),
]

router = DefaultRouter()
router.register("unites", UnitsViewSet, basename="organisation-unit")
router.register("annees", AnneesScolairesViewSet, basename="annee-scolaire")
router.register("periodes", PeriodesViewSet, basename="periode")
router.register("niveaux", NiveauxViewSet, basename="niveau")
urlpatterns += router.urls
