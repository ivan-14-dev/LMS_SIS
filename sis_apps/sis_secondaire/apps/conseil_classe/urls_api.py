"""URLs API for conseil_classe."""
from django.urls import path
from . import api

app_name = "conseil_classe_api"

urlpatterns = [
    # path("", api.ConseilClasseViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
