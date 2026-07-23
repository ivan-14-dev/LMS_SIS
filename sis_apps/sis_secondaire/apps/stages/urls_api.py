"""URLs API for stages."""
from django.urls import path
from . import api

app_name = "stages_api"

urlpatterns = [
    # path("", api.StagesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
