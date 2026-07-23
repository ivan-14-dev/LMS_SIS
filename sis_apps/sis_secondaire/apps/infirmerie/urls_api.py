"""URLs API for infirmerie."""
from django.urls import path
from . import api

app_name = "infirmerie_api"

urlpatterns = [
    # path("", api.InfirmerieViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
