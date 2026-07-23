"""URLs API for portail_etudiant."""
from django.urls import path
from . import api

app_name = "portail_etudiant_api"

urlpatterns = [
    # path("", api.PortailEtudiantViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
