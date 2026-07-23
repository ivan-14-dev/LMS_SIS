"""URLs API for entreprises."""
from django.urls import path
from . import api

app_name = "entreprises_api"

urlpatterns = [
    # path("", api.EntreprisesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
