"""URLs API for jurys."""
from django.urls import path
from . import api

app_name = "jurys_api"

urlpatterns = [
    # path("", api.JurysViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
