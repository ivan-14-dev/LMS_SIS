"""URLs API for internat."""
from django.urls import path
from . import api

app_name = "internat_api"

urlpatterns = [
    # path("", api.InternatViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
