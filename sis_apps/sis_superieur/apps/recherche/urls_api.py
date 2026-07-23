"""URLs API for recherche."""
from django.urls import path
from . import api

app_name = "recherche_api"

urlpatterns = [
    # path("", api.RechercheViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
