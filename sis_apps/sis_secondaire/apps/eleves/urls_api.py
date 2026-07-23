"""URLs API for eleves."""
from django.urls import path
from . import api

app_name = "eleves_api"

urlpatterns = [
    # path("", api.ElevesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
