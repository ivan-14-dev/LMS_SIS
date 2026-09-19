"""URLs API for etudiants."""
from django.urls import path
from . import api

app_name = "etudiants_api"

urlpatterns = [
    path("", api.EtudiantsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
    path("<int:pk>/", api.EtudiantsViewSet.as_view({
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }), name="detail"),
    path("<int:pk>/inscriptions/", api.EtudiantsViewSet.as_view({"get": "inscriptions"}), name="inscriptions"),
    path("<int:pk>/changer-statut/", api.EtudiantsViewSet.as_view({"post": "changer_statut"}), name="changer-statut"),
    path("search/", api.EtudiantsViewSet.as_view({"get": "search"}), name="search"),
]
