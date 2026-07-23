"""URLs API for paiements."""
from django.urls import path
from . import api

app_name = "paiements_api"

urlpatterns = [
    # path("", api.PaiementsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
