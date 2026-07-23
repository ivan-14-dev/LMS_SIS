"""URLs API for clubs."""
from django.urls import path
from . import api

app_name = "clubs_api"

urlpatterns = [
    # path("", api.ClubsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
