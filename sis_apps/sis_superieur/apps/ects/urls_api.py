"""URLs API for ects."""
from django.urls import path
from . import api

app_name = "ects_api"

urlpatterns = [
    # path("", api.EctsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
