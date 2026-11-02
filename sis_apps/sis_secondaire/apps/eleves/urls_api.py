"""URLs API for eleves."""

from django.urls import path

from . import api

app_name = "eleves_api"

urlpatterns = [
    path(
        "inscriptions/",
        api.InscriptionsViewSet.as_view({"get": "list", "post": "create"}),
        name="inscriptions-list",
    ),
    path(
        "inscriptions/<int:pk>/",
        api.InscriptionsViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="inscriptions-detail",
    ),
    path(
        "inscriptions/<int:pk>/valider/",
        api.InscriptionsViewSet.as_view({"post": "valider"}),
        name="inscriptions-valider",
    ),
    path("importer/", api.ElevesViewSet.as_view({"post": "importer"}), name="importer"),
    path(
        "modele-import/",
        api.ElevesViewSet.as_view({"get": "modele_import"}),
        name="modele-import",
    ),
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
