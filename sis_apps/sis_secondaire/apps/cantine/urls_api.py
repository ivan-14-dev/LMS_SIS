"""URLs API for cantine."""
from django.urls import path
from . import api

app_name = "cantine_api"

urlpatterns = [
    # path("", api.CantineViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
