"""URLs API for etudiants."""
from django.urls import path
from . import api

app_name = "etudiants_api"

urlpatterns = [
    # path("", api.EtudiantsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
