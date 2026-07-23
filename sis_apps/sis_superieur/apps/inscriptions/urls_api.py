"""URLs API for inscriptions."""
from django.urls import path
from . import api

app_name = "inscriptions_api"

urlpatterns = [
    # path("", api.InscriptionsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
