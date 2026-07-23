"""URLs API for memoires."""
from django.urls import path
from . import api

app_name = "memoires_api"

urlpatterns = [
    # path("", api.MemoiresViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
