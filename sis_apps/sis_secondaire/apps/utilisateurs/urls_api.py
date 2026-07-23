"""URLs API for utilisateurs."""
from django.urls import path
from . import api

app_name = "utilisateurs_api"

urlpatterns = [
    # path("", api.UtilisateursViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
