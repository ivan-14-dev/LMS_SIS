"""URLs API for eleves."""
from django.urls import path
from . import api

app_name = "eleves_api"

urlpatterns = [
    path("", api.ElevesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
    path("<int:pk>/", api.ElevesViewSet.as_view({
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }), name="detail"),
    path("<int:pk>/inscriptions/", api.ElevesViewSet.as_view({"get": "inscriptions"}), name="inscriptions"),
    path("<int:pk>/tuteurs/", api.ElevesViewSet.as_view({"get": "tuteurs"}), name="tuteurs"),
    path("<int:pk>/changer-classe/", api.ElevesViewSet.as_view({"post": "changer_classe"}), name="changer-classe"),
    path("search/", api.ElevesViewSet.as_view({"get": "search"}), name="search"),
]
