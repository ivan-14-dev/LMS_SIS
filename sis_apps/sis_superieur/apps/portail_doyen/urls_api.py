"""URLs API for portail_doyen."""
from django.urls import path
from . import api

app_name = "portail_doyen_api"

urlpatterns = [
    # path("", api.PortailDoyenViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
