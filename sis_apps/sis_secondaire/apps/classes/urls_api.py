"""URLs API for classes."""
from django.urls import path
from . import api

app_name = "classes_api"

urlpatterns = [
    # path("", api.ClassesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
