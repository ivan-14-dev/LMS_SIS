"""URLs API for rattrapages."""
from django.urls import path
from . import api

app_name = "rattrapages_api"

urlpatterns = [
    # path("", api.RattrapagesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
