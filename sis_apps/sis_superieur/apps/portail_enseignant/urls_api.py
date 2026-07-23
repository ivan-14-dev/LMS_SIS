"""URLs API for portail_enseignant."""
from django.urls import path
from . import api

app_name = "portail_enseignant_api"

urlpatterns = [
    # path("", api.PortailEnseignantViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
