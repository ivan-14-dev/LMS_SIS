"""URLs API for ue_ecue."""
from django.urls import path
from . import api

app_name = "ue_ecue_api"

urlpatterns = [
    # path("", api.UeEcueViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
