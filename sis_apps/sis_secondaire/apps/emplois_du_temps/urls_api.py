"""URLs API for emplois_du_temps."""
from django.urls import path
from . import api

app_name = "emplois_du_temps_api"

urlpatterns = [
    # path("", api.EmploisDuTempsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
