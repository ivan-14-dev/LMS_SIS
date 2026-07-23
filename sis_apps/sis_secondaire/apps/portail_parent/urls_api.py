"""URLs API for portail_parent."""
from django.urls import path
from . import api

app_name = "portail_parent_api"

urlpatterns = [
    # path("", api.PortailParentViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
