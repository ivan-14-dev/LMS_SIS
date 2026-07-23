"""URLs API for maquettes."""
from django.urls import path
from . import api

app_name = "maquettes_api"

urlpatterns = [
    # path("", api.MaquettesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
