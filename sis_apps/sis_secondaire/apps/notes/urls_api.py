"""URLs API for notes."""
from django.urls import path
from . import api

app_name = "notes_api"

urlpatterns = [
    # path("", api.NotesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
