"""URLs API for enseignants."""
from django.urls import path
from . import api

app_name = "enseignants_api"

urlpatterns = [
    # path("", api.EnseignantsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
