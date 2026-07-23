"""URLs API for diplomes."""
from django.urls import path
from . import api

app_name = "diplomes_api"

urlpatterns = [
    # path("", api.DiplomesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
