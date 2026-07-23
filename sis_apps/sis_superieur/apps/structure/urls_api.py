"""URLs API for structure."""
from django.urls import path
from . import api

app_name = "structure_api"

urlpatterns = [
    # path("", api.StructureViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
