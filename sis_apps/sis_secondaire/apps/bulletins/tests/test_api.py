"""API tests for bulletins."""

from types import SimpleNamespace
from unittest.mock import patch

from apps.bulletins.api import AppreciationsMatiereViewSet, BulletinsViewSet, IsEnseignantOrScolarite
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory


class BulletinsAPITestCase(SimpleTestCase):
    def test_bulletin_routes_are_registered(self):
        list_match = resolve("/api/v1/bulletins/")
        detail_match = resolve("/api/v1/bulletins/1/")
        pdf_match = resolve("/api/v1/bulletins/1/pdf_officiel/")
        history_match = resolve("/api/v1/bulletins/1/historique/")
        appreciations_match = resolve("/api/v1/bulletins/appreciations/")

        assert list_match.url_name == "bulletin-list"
        assert detail_match.url_name == "bulletin-detail"
        assert pdf_match.url_name == "bulletin-pdf-officiel"
        assert history_match.url_name == "bulletin-historique"
        assert appreciations_match.url_name == "appreciation-matiere-list"


class IsEnseignantOrScolaritePermissionTestCase(SimpleTestCase):
    """Vérifie la permission d'écriture des appréciations par matière."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsEnseignantOrScolarite()

    def _view_stub(self):
        return SimpleNamespace()

    def test_read_only_methods_are_always_allowed_for_authenticated_users(self):
        user = SimpleNamespace(is_authenticated=True, is_staff=False, role="eleve")
        request = SimpleNamespace(method="GET", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is True

    def test_plain_student_cannot_write(self):
        user = SimpleNamespace(is_authenticated=True, is_staff=False, role="eleve")
        request = SimpleNamespace(method="POST", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is False

    def test_teacher_profile_can_write(self):
        user = SimpleNamespace(
            is_authenticated=True, is_staff=False, role="enseignant", enseignant_profile=object()
        )
        request = SimpleNamespace(method="POST", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is True

    def test_scolarite_role_can_write_without_teacher_profile(self):
        user = SimpleNamespace(is_authenticated=True, is_staff=False, role="scolarite")
        request = SimpleNamespace(method="PATCH", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is True

    def test_unauthenticated_user_is_denied(self):
        user = SimpleNamespace(is_authenticated=False, is_staff=False, role="")
        request = SimpleNamespace(method="GET", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is False


class AppreciationsMatiereActionsTestCase(SimpleTestCase):
    """Vérifie les actions personnalisées `par_eleve`/`par_classe`."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_par_eleve_requires_both_query_params(self):
        request = Request(self.factory.get("/api/v1/bulletins/appreciations/par_eleve/"))
        view = AppreciationsMatiereViewSet()
        view.request = request
        view.format_kwarg = None

        response = view.par_eleve(request)

        assert response.status_code == 400

    def test_par_classe_requires_all_three_query_params(self):
        request = Request(self.factory.get("/api/v1/bulletins/par_classe/", {"classe": "1"}))
        view = BulletinsViewSet()
        view.request = request
        view.format_kwarg = None

        response = view.par_classe(request)

        assert response.status_code == 400

    @patch("apps.bulletins.api.AppreciationMatiere")
    def test_par_classe_queries_appreciation_matiere_not_bulletin(self, mock_model):
        """Régression : `par_classe` doit filtrer sur `AppreciationMatiere`, pas sur les bulletins.

        Avant correction, l'action appelait `self.get_queryset()` -- qui, sur ce
        ViewSet, renvoie un queryset de `Bulletin` (hérité de la vue notes) -- puis
        filtrait sur `matiere_id`, un champ inexistant sur `Bulletin`. Cela levait une
        `FieldError` Django à l'exécution. Ce test vérifie que le gestionnaire
        `AppreciationMatiere.objects` est bien utilisé.
        """
        queryset = mock_model.objects.select_related.return_value
        queryset.filter.return_value.order_by.return_value = []

        request = Request(
            self.factory.get(
                "/api/v1/bulletins/par_classe/",
                {"classe": "1", "matiere": "2", "periode": "3"},
            )
        )
        view = BulletinsViewSet()
        view.request = request
        view.format_kwarg = None

        response = view.par_classe(request)

        assert response.status_code == 200
        mock_model.objects.select_related.assert_called_once_with("eleve__user", "matiere", "periode")
        queryset.filter.assert_called_once_with(eleve__classe_id="1", matiere_id="2", periode_id="3")
