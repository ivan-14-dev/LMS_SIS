"""URLs API for releves."""
from django.urls import path
from . import api

app_name = "releves_api"

urlpatterns = [
    # path("", api.RelevesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
