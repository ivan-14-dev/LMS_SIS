"""URLs API for bulletins."""
from django.urls import path
from . import api

app_name = "bulletins_api"

urlpatterns = [
    # path("", api.BulletinsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
