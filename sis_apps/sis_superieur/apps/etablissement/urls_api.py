"""API URLs for etablissement."""

from django.urls import path

from .api import CurrentUniversiteView

app_name = "etablissement_api"

urlpatterns = [
    path("current/", CurrentUniversiteView.as_view(), name="current"),
]
