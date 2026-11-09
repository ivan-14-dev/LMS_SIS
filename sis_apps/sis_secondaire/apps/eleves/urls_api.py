"""URLs API for eleves."""

from django.urls import path

from sis_common.delegations import ActiveTenantAccess

from . import api

app_name = "eleves_api"

urlpatterns = [
    path(
        "inscriptions/",
        api.InscriptionsViewSet.as_view({"get": "list", "post": "create"}),
        name="inscriptions-list",
    ),
    path(
        "inscriptions/deposer/",
        api.InscriptionsViewSet.as_view({"post": "deposer"}, permission_classes=[ActiveTenantAccess]),
        name="inscriptions-deposer",
    ),
    path(
        "inscriptions/<int:pk>/",
        api.InscriptionsViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="inscriptions-detail",
    ),
    path(
        "inscriptions/<int:pk>/valider/",
        api.InscriptionsViewSet.as_view({"post": "valider"}),
        name="inscriptions-valider",
    ),
    path(
        "inscriptions/<int:pk>/reinscrire/",
        api.InscriptionsViewSet.as_view({"post": "reinscrire"}),
        name="inscriptions-reinscrire",
    ),
    path(
        "inscriptions/<int:pk>/refuser/",
        api.InscriptionsViewSet.as_view({"post": "refuser"}),
        name="inscriptions-refuser",
    ),
    path(
        "inscriptions/<int:pk>/annuler/",
        api.InscriptionsViewSet.as_view({"post": "annuler"}),
        name="inscriptions-annuler",
    ),
    path(
        "inscriptions/<int:pk>/suspendre/",
        api.InscriptionsViewSet.as_view({"post": "suspendre"}),
        name="inscriptions-suspendre",
    ),
    path(
        "inscriptions/<int:pk>/abandonner/",
        api.InscriptionsViewSet.as_view({"post": "abandonner"}),
        name="inscriptions-abandonner",
    ),
    path(
        "inscriptions/<int:pk>/reprendre/",
        api.InscriptionsViewSet.as_view({"post": "reprendre"}),
        name="inscriptions-reprendre",
    ),
    path(
        "inscriptions/<int:pk>/historique/",
        api.InscriptionsViewSet.as_view({"get": "historique"}),
        name="inscriptions-historique",
    ),
    path("importer/", api.ElevesViewSet.as_view({"get": "schema_import", "post": "importer"}), name="importer"),
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
