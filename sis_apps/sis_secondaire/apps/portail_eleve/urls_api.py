"""URLs API for portail_eleve."""
from django.urls import path
from . import api

app_name = "portail_eleve_api"

urlpatterns = [
    # path("", api.PortailEleveViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
