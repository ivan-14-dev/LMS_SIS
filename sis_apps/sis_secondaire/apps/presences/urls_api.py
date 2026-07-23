"""URLs API for presences."""
from django.urls import path
from . import api

app_name = "presences_api"

urlpatterns = [
    # path("", api.PresencesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
