"""API URLs for etablissement."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .api import (
    AnneesUniversitairesViewSet,
    CurrentUniversiteView,
    SemestresViewSet,
)

app_name = "etablissement_api"

urlpatterns = [
    path("current/", CurrentUniversiteView.as_view(), name="current"),
]

router = DefaultRouter()
router.register("annees", AnneesUniversitairesViewSet, basename="annee-universitaire")
router.register("semestres", SemestresViewSet, basename="semestre")
urlpatterns += router.urls
