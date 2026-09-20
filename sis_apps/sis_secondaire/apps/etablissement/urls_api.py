"""API URLs for etablissement."""

from django.urls import path

from .api import CurrentEtablissementView

app_name = "etablissement_api"

urlpatterns = [
    path("current/", CurrentEtablissementView.as_view(), name="current"),
]
