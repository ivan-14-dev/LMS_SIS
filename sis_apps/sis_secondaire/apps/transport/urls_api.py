"""URLs API for transport."""
from django.urls import path
from . import api

app_name = "transport_api"

urlpatterns = [
    # path("", api.TransportViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
