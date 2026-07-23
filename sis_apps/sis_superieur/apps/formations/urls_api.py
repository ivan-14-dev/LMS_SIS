"""URLs API for formations."""
from django.urls import path
from . import api

app_name = "formations_api"

urlpatterns = [
    # path("", api.FormationsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
