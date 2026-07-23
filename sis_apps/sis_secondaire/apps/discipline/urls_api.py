"""URLs API for discipline."""
from django.urls import path
from . import api

app_name = "discipline_api"

urlpatterns = [
    # path("", api.DisciplineViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
