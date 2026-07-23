"""URLs API for portail_scolarite."""
from django.urls import path
from . import api

app_name = "portail_scolarite_api"

urlpatterns = [
    # path("", api.PortailScolariteViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
