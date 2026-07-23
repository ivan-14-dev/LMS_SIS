"""URLs API for bibliotheque."""
from django.urls import path
from . import api

app_name = "bibliotheque_api"

urlpatterns = [
    # path("", api.BibliothequeViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
