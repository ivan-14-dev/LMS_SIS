"""API tests for conseil_classe."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apps.conseil_classe.api import ConseilsClasseViewSet, IsDirectionOrReadOnly
from django.test import SimpleTestCase
from django.urls import resolve


class ConseilClasseAPITestCase(SimpleTestCase):
    def test_conseil_routes_are_exposed(self):
        assert resolve("/api/v1/conseils/conseils-classe/").url_name == "conseil-classe-list"
        assert resolve("/api/v1/conseils/conseils-classe/1/historique/").url_name == "conseil-classe-historique"


class IsDirectionOrReadOnlyPermissionTestCase(SimpleTestCase):
    """Vérifie que seule la direction (ou un groupe tenant dédié) peut modifier un conseil."""

    def setUp(self):
        self.permission = IsDirectionOrReadOnly()
        self.view = SimpleNamespace()

    def test_read_only_methods_always_allowed(self):
        user = SimpleNamespace(is_authenticated=True)
        request = SimpleNamespace(method="GET", user=user)

        assert self.permission.has_permission(request, self.view) is True

    @patch("apps.conseil_classe.api.request_has_business_access", return_value=False)
    def test_write_denied_without_business_access(self, _mock_access):
        user = SimpleNamespace(is_authenticated=True)
        request = SimpleNamespace(method="POST", user=user)

        assert self.permission.has_permission(request, self.view) is False

    @patch("apps.conseil_classe.api.request_has_business_access", return_value=True)
    def test_write_allowed_with_business_access(self, _mock_access):
        user = SimpleNamespace(is_authenticated=True)
        request = SimpleNamespace(method="POST", user=user)

        assert self.permission.has_permission(request, self.view) is True

    def test_unauthenticated_user_is_denied(self):
        user = SimpleNamespace(is_authenticated=False)
        request = SimpleNamespace(method="GET", user=user)

        assert self.permission.has_permission(request, self.view) is False


class ConseilWorkflowActionsTestCase(SimpleTestCase):
    """Vérifie la machine à états planifié -> tenu -> validé."""

    def _view_with_conseil(self, conseil):
        view = ConseilsClasseViewSet()
        view.get_object = MagicMock(return_value=conseil)
        view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
        return view

    def _conseil(self, statut):
        return SimpleNamespace(
            statut=statut,
            id=1,
            classe="6eA",
            periode_id=1,
            classe_id=1,
            president=None,
            secretaire=None,
            save=MagicMock(),
        )

    @patch("apps.conseil_classe.api.record_workflow_event")
    def test_tenir_rejects_conseil_not_planned(self, _mock_event):
        conseil = self._conseil(statut="tenu")
        view = self._view_with_conseil(conseil)

        response = view.tenir(view.request, pk=1)

        assert response.status_code == 400
        conseil.save.assert_not_called()

    @patch("apps.conseil_classe.api.record_workflow_event")
    def test_tenir_transitions_planifie_to_tenu(self, mock_event):
        conseil = self._conseil(statut="planifie")
        view = self._view_with_conseil(conseil)

        response = view.tenir(view.request, pk=1)

        assert response.status_code == 200
        assert conseil.statut == "tenu"
        conseil.save.assert_called_once_with(update_fields=["statut"])
        mock_event.assert_called_once()

    @patch("apps.conseil_classe.api.record_workflow_event")
    def test_valider_rejects_conseil_not_held(self, _mock_event):
        conseil = self._conseil(statut="planifie")
        view = self._view_with_conseil(conseil)

        response = view.valider(view.request, pk=1)

        assert response.status_code == 400
        conseil.save.assert_not_called()

    @patch("apps.conseil_classe.api.record_workflow_event")
    def test_valider_transitions_tenu_to_valide(self, mock_event):
        conseil = self._conseil(statut="tenu")
        view = self._view_with_conseil(conseil)

        response = view.valider(view.request, pk=1)

        assert response.status_code == 200
        assert conseil.statut == "valide"
        conseil.save.assert_called_once_with(update_fields=["statut"])
        mock_event.assert_called_once()
