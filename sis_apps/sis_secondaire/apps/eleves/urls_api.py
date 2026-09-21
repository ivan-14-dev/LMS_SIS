"""URLs API for eleves."""

from django.urls import path

from . import api

app_name = "eleves_api"

urlpatterns = [
    path("", api.ElevesViewSet.as_view({"get": "list", "post": "create"}), name="list"),
    path(
        "<int:pk>/",
        api.ElevesViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="detail",
    ),
    path(
        "<int:pk>/inscriptions/",
        api.ElevesViewSet.as_view({"get": "inscriptions"}),
        name="inscriptions",
    ),
    path(
        "<int:pk>/tuteurs/",
        api.ElevesViewSet.as_view({"get": "tuteurs"}),
        name="tuteurs",
    ),
    path(
        "<int:pk>/changer-classe/",
        api.ElevesViewSet.as_view({"post": "changer_classe"}),
        name="changer-classe",
    ),
    path(
        "<int:pk>/matieres-individuelles/",
        api.ElevesViewSet.as_view({"get": "matieres_individuelles", "post": "matieres_individuelles"}),
        name="matieres-individuelles",
    ),
    path(
        "<int:pk>/retirer-matiere-individuelle/",
        api.ElevesViewSet.as_view({"post": "retirer_matiere_individuelle"}),
        name="retirer-matiere-individuelle",
    ),
    path("search/", api.ElevesViewSet.as_view({"get": "search"}), name="search"),
]
