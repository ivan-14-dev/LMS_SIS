"""API tests for etudiants."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apps.etudiants.api import EtudiantsViewSet, InscriptionsAdminViewSet, IsScolariteOrReadOnly
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework import status


class EtudiantsAPITestCase(SimpleTestCase):
    def test_individual_subject_routes_are_registered(self):
        list_match = resolve("/api/v1/etudiants/1/matieres-individuelles/")
        remove_match = resolve("/api/v1/etudiants/1/retirer-matiere-individuelle/")

        assert list_match.url_name == "matieres-individuelles"
        assert remove_match.url_name == "retirer-matiere-individuelle"


class IsScolariteOrReadOnlyPermissionTestCase(SimpleTestCase):
    def setUp(self):
        self.permission = IsScolariteOrReadOnly()
        self.view = SimpleNamespace()

    def test_read_only_methods_always_allowed(self):
        request = SimpleNamespace(method="GET", user=SimpleNamespace(is_authenticated=True))
        assert self.permission.has_permission(request, self.view) is True

    @patch("apps.etudiants.api.request_has_business_access", return_value=False)
    def test_write_denied_without_business_access(self, _mock_access):
        request = SimpleNamespace(method="POST", user=SimpleNamespace(is_authenticated=True))
        assert self.permission.has_permission(request, self.view) is False

    @patch("apps.etudiants.api.request_has_business_access", return_value=True)
    def test_write_allowed_with_business_access(self, _mock_access):
        request = SimpleNamespace(method="POST", user=SimpleNamespace(is_authenticated=True))
        assert self.permission.has_permission(request, self.view) is True

    def test_unauthenticated_user_is_denied(self):
        request = SimpleNamespace(method="GET", user=SimpleNamespace(is_authenticated=False))
        assert self.permission.has_permission(request, self.view) is False


class EtudiantsQuerysetTestCase(SimpleTestCase):
    """Vérifie le filtrage tenant + l'auto-service pour un étudiant connecté."""

    @patch("apps.etudiants.api.Etudiant")
    def test_queryset_is_filtered_by_tenant(self, mock_model):
        tenant = SimpleNamespace(id=1)
        user = SimpleNamespace(is_staff=True, role="scolarite")
        view = EtudiantsViewSet()
        view.request = SimpleNamespace(tenant=tenant, user=user)

        view.get_queryset()

        mock_model.objects.select_related.assert_called_once_with(
            "user", "universite", "annee_universitaire_actuelle"
        )
        mock_model.objects.select_related.return_value.filter.assert_called_once_with(universite=tenant)

    @patch("apps.etudiants.api.Etudiant")
    def test_student_self_service_only_sees_own_profile(self, mock_model):
        tenant = SimpleNamespace(id=1)
        user = SimpleNamespace(is_staff=False, role="etudiant", etudiant_profile=object())
        view = EtudiantsViewSet()
        view.request = SimpleNamespace(tenant=tenant, user=user)

        view.get_queryset()

        tenant_filtered_qs = mock_model.objects.select_related.return_value.filter.return_value
        tenant_filtered_qs.filter.assert_called_once_with(user=user)


class EtudiantsActionsTestCase(SimpleTestCase):
    def _view_with_etudiant(self, etudiant):
        view = EtudiantsViewSet()
        view.get_object = MagicMock(return_value=etudiant)
        return view

    def test_changer_statut_rejects_invalid_value(self):
        etudiant = SimpleNamespace(statut="inscrit", save=MagicMock())
        view = self._view_with_etudiant(etudiant)
        request = SimpleNamespace(data={"statut": "not_a_real_status"})

        response = view.changer_statut(request, pk=1)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        etudiant.save.assert_not_called()

    def test_changer_statut_updates_status(self):
        etudiant = SimpleNamespace(id=1, statut="inscrit", save=MagicMock())
        view = self._view_with_etudiant(etudiant)
        request = SimpleNamespace(data={"statut": "suspendu"})

        response = view.changer_statut(request, pk=1)

        assert response.status_code == 200
        assert etudiant.statut == "suspendu"
        assert response.data["ancien_statut"] == "inscrit"
        assert response.data["nouveau_statut"] == "suspendu"
        etudiant.save.assert_called_once_with(update_fields=["statut", "updated_at"])

    @patch("apps.etudiants.api.AffectationECUEIndividuelle")
    def test_retirer_matiere_individuelle_returns_404_when_not_found(self, mock_model):
        mock_model.objects.filter.return_value.first.return_value = None
        etudiant = SimpleNamespace(id=1)
        view = self._view_with_etudiant(etudiant)
        request = SimpleNamespace(data={"affectation_id": 42})

        response = view.retirer_matiere_individuelle(request, pk=1)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.etudiants.api.AffectationECUEIndividuelle")
    def test_retirer_matiere_individuelle_deletes_found_affectation(self, mock_model):
        affectation = MagicMock()
        mock_model.objects.filter.return_value.first.return_value = affectation
        etudiant = SimpleNamespace(id=1)
        view = self._view_with_etudiant(etudiant)
        request = SimpleNamespace(data={"affectation_id": 42})

        response = view.retirer_matiere_individuelle(request, pk=1)

        affectation.delete.assert_called_once()
        assert response.status_code == status.HTTP_204_NO_CONTENT


class InscriptionsAdminWorkflowTestCase(SimpleTestCase):
    """Vérifie la machine à états provisoire -> validee / refusee."""

    def _view_with_inscription(self, inscription):
        view = InscriptionsAdminViewSet()
        view.get_object = MagicMock(return_value=inscription)
        return view

    def _inscription(self, statut):
        return SimpleNamespace(
            statut=statut,
            id=1,
            etudiant=SimpleNamespace(user=None),
            etudiant_id=7,
            formation_id=1,
            annee_universitaire_id=1,
            motif_refus="",
            save=MagicMock(),
        )

    @patch("apps.etudiants.api.record_workflow_event")
    def test_valider_rejects_non_provisoire_inscription(self, _mock_event):
        inscription = self._inscription(statut="validee")
        view = self._view_with_inscription(inscription)
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))

        response = view.valider(request, pk=1)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        inscription.save.assert_not_called()

    @patch("apps.etudiants.api.record_workflow_event")
    def test_valider_transitions_provisoire_to_validee(self, mock_event):
        inscription = self._inscription(statut="provisoire")
        view = self._view_with_inscription(inscription)
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))

        response = view.valider(request, pk=1)

        assert response.status_code == 200
        assert inscription.statut == "validee"
        inscription.save.assert_called_once_with(update_fields=["statut", "updated_at"])
        mock_event.assert_called_once()

    @patch("apps.etudiants.api.record_workflow_event")
    def test_refuser_requires_motif(self, _mock_event):
        inscription = self._inscription(statut="provisoire")
        view = self._view_with_inscription(inscription)
        request = SimpleNamespace(data={}, user=SimpleNamespace(is_authenticated=True))

        response = view.refuser(request, pk=1)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        inscription.save.assert_not_called()

    @patch("apps.etudiants.api.record_workflow_event")
    def test_refuser_transitions_to_refusee_with_motif(self, mock_event):
        inscription = self._inscription(statut="provisoire")
        view = self._view_with_inscription(inscription)
        request = SimpleNamespace(data={"motif": "Dossier incomplet"}, user=SimpleNamespace(is_authenticated=True))

        response = view.refuser(request, pk=1)

        assert response.status_code == 200
        assert inscription.statut == "refusee"
        assert inscription.motif_refus == "Dossier incomplet"
        inscription.save.assert_called_once_with(update_fields=["statut", "motif_refus", "updated_at"])
        mock_event.assert_called_once()
