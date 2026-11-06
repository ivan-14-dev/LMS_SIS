"""API tests for conseil_classe."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apps.conseil_classe.api import ConseilsClasseViewSet, IsDirectionOrReadOnly
from apps.classes.models import Classe
from apps.conseil_classe.models import ConseilClasse
from apps.etablissement.models import AnneeScolaire, Niveau, Periode
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
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


class ConseilWorkflowHTTPTestCase(TenantAPITestCase):
    def setUp(self):
        manager = Utilisateur.objects.create_superuser(
            "conseil-manager", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(manager)
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut="2026-09-01",
            date_fin="2027-06-30",
        )
        niveau = Niveau.objects.create(
            etablissement=self.tenant, code="6e", libelle="6ème", ordre=1
        )
        classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="6e A",
        )
        periode = Periode.objects.create(
            annee_scolaire=annee,
            type="trimestre",
            numero=1,
            date_debut="2026-09-01",
            date_fin="2026-12-20",
        )
        self.url = "/api/v1/conseils/conseils-classe/"
        self.payload = {
            "classe": classe.pk,
            "periode": periode.pk,
            "date": "2026-12-15T09:00:00Z",
            "president": manager.pk,
        }

    def test_create_cannot_start_validated(self):
        response = self.client.post(
            self.url, {**self.payload, "statut": "valide"}, format="json"
        )

        assert response.status_code == 400, response.data
        assert not ConseilClasse.objects.exists()

    def test_patch_cannot_bypass_workflow_actions(self):
        created = self.client.post(self.url, self.payload, format="json")
        assert created.status_code == 201, created.data
        url = f"{self.url}{created.data['id']}/"

        for statut in ("tenu", "valide"):
            response = self.client.patch(url, {"statut": statut}, format="json")
            assert response.status_code == 400, response.data
            assert ConseilClasse.objects.get(pk=created.data["id"]).statut == "planifie"

        assert self.client.post(f"{url}tenir/").status_code == 200
        response = self.client.patch(url, {"statut": "valide"}, format="json")
        assert response.status_code == 400, response.data
        assert ConseilClasse.objects.get(pk=created.data["id"]).statut == "tenu"

        assert self.client.post(f"{url}valider/").status_code == 200
        assert ConseilClasse.objects.get(pk=created.data["id"]).statut == "valide"

    def test_planned_conseil_can_still_be_cancelled(self):
        created = self.client.post(self.url, self.payload, format="json")
        assert created.status_code == 201, created.data

        response = self.client.patch(
            f"{self.url}{created.data['id']}/", {"statut": "annule"}, format="json"
        )

        assert response.status_code == 200, response.data
        assert ConseilClasse.objects.get(pk=created.data["id"]).statut == "annule"

    def test_validated_conseil_cannot_be_changed_or_deleted_via_detail_api(self):
        created = self.client.post(self.url, self.payload, format="json")
        assert created.status_code == 201, created.data
        url = f"{self.url}{created.data['id']}/"
        assert self.client.post(f"{url}tenir/").status_code == 200
        assert self.client.post(f"{url}valider/").status_code == 200

        for method, data in (
            (self.client.patch, {"pv": "PV modifié"}),
            (self.client.put, {**self.payload, "pv": "PV remplacé"}),
        ):
            response = method(url, data, format="json")
            assert response.status_code == 400, response.data
        response = self.client.delete(url)
        assert response.status_code == 400, response.data

        conseil = ConseilClasse.objects.get(pk=created.data["id"])
        assert conseil.statut == "valide"
        assert conseil.pv == ""

    def test_held_conseil_can_still_edit_its_minutes(self):
        created = self.client.post(self.url, self.payload, format="json")
        assert created.status_code == 201, created.data
        url = f"{self.url}{created.data['id']}/"
        assert self.client.post(f"{url}tenir/").status_code == 200

        response = self.client.patch(url, {"pv": "PV du conseil"}, format="json")

        assert response.status_code == 200, response.data
        assert ConseilClasse.objects.get(pk=created.data["id"]).pv == "PV du conseil"
