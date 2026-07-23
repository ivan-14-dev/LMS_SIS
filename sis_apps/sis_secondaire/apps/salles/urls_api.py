"""URLs API for salles."""
from django.urls import path
from . import api

app_name = "salles_api"

urlpatterns = [
    # path("", api.SallesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
