"""URLs API for mobilite."""
from django.urls import path
from . import api

app_name = "mobilite_api"

urlpatterns = [
    # path("", api.MobiliteViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
