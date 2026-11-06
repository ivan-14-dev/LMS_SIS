"""API tests for etudiants."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from apps.etudiants.api import EtudiantsViewSet, InscriptionsAdminViewSet, IsScolariteOrReadOnly
from apps.etudiants.models import InscriptionAdministrative
from apps.etudiants.serializers import InscriptionAdministrativeSerializer
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework import status
from rest_framework.exceptions import ValidationError

from sis_common.tests.test_grade_entry import GradeEntryFixture


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
        user = SimpleNamespace(is_staff=True, role="scolarite", has_perm=lambda _: True)
        view = EtudiantsViewSet()
        view.request = SimpleNamespace(tenant=tenant, user=user)

        view.get_queryset()

        mock_model.objects.select_related.assert_called_once_with("user", "universite", "annee_universitaire_actuelle")
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

    @patch("apps.etudiants.api.request_has_business_access", return_value=False)
    @patch("apps.etudiants.api.Etudiant")
    def test_staff_flag_without_student_view_permission_sees_only_own_record(self, mock_model, _mock_access):
        user = SimpleNamespace(is_staff=True, is_superuser=False, role="autre", has_perm=lambda _: False)
        view = EtudiantsViewSet()
        view.request = SimpleNamespace(tenant=SimpleNamespace(pk=11), user=user)

        view.get_queryset()

        tenant_filtered_qs = mock_model.objects.select_related.return_value.filter.return_value
        tenant_filtered_qs.filter.assert_called_once_with(user=user)

    @patch("apps.etudiants.api.Etudiant")
    def test_student_with_staff_flag_and_permission_cannot_list_other_students(self, mock_model):
        user = SimpleNamespace(is_staff=True, is_superuser=False, role="etudiant", has_perm=lambda _: True)
        view = EtudiantsViewSet()
        view.request = SimpleNamespace(tenant=SimpleNamespace(pk=11), user=user)

        view.get_queryset()

        tenant_filtered_qs = mock_model.objects.select_related.return_value.filter.return_value
        tenant_filtered_qs.filter.assert_called_once_with(user=user)


class EtudiantsReadAccessTestCase(GradeEntryFixture):
    def test_staff_flag_without_student_view_permission_does_not_expose_student_directory(self):
        visitor = Utilisateur.objects.create_user(
            "student-directory-visitor", role="autre", is_staff=True, etablissement=self.tenant
        )
        self.client.force_authenticate(visitor)
        url = "/api/v1/etudiants/"
        response = self.client.get(url, secure=True)
        assert response.status_code == 200, response.data
        assert response.data["count"] == 0
        assert self.client.get(f"{url}{self.learners[0].pk}/", secure=True).status_code == 404
        search = self.client.get(f"{url}search/", {"q": "Learner"}, secure=True)
        assert search.status_code == 200, search.data
        assert search.data["count"] == 0

        self.client.force_authenticate(self.learners[0].user)
        own = self.client.get(url, secure=True)
        assert own.status_code == 200, own.data
        assert own.data["count"] == 1
        assert own.data["results"][0]["id"] == self.learners[0].pk


class InscriptionValidationConsistencyTestCase(GradeEntryFixture):
    def test_validation_activates_student_status_and_current_year(self):
        student = self.learners[2]
        inscription = InscriptionAdministrative.objects.create(
            etudiant=student,
            annee_universitaire=self.year,
            formation=self.formation,
            date_inscription=self.today,
        )
        assert student.statut == "pre_inscrit"
        assert student.annee_universitaire_actuelle_id is None

        response = self.client.post(f"/api/v1/inscriptions/{inscription.pk}/valider/", {}, format="json")

        assert response.status_code == 200, response.data
        student.refresh_from_db()
        assert student.statut == "inscrit"
        assert student.annee_universitaire_actuelle_id == self.year.pk

    def test_validation_of_older_year_preserves_newer_year_and_suspension(self):
        student = self.learners[2]
        self.enroll(student)
        student.statut = "suspendu"
        student.annee_universitaire_actuelle = self.year
        student.save(update_fields=["statut", "annee_universitaire_actuelle"])
        previous_year = self.create(
            self.year_model,
            universite=self.tenant,
            libelle="previous",
            date_debut=self.year.date_debut.replace(year=self.year.date_debut.year - 1),
            date_fin=self.year.date_fin.replace(year=self.year.date_fin.year - 1),
        )
        inscription = InscriptionAdministrative.objects.create(
            etudiant=student,
            annee_universitaire=previous_year,
            formation=self.formation,
            date_inscription=previous_year.date_debut,
        )

        response = self.client.post(f"/api/v1/inscriptions/{inscription.pk}/valider/", {}, format="json")

        assert response.status_code == 200, response.data
        student.refresh_from_db()
        assert student.statut == "suspendu"
        assert student.annee_universitaire_actuelle_id == self.year.pk


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

    @patch("apps.etudiants.api.ensure_academic_open")
    @patch("apps.etudiants.api.AffectationECUEIndividuelle")
    def test_retirer_matiere_individuelle_deletes_found_affectation(self, mock_model, mock_guard):
        affectation = MagicMock()
        mock_model.objects.filter.return_value.first.return_value = affectation
        etudiant = SimpleNamespace(id=1)
        view = self._view_with_etudiant(etudiant)
        request = SimpleNamespace(data={"affectation_id": 42})

        response = view.retirer_matiere_individuelle(request, pk=1)

        mock_guard.assert_called_once_with(
            affectation, paths=("inscription_admin.annee_universitaire", "semestre_cible")
        )
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

    @patch("apps.etudiants.api.Etudiant.objects")
    @patch("apps.etudiants.api.record_workflow_event")
    def test_valider_transitions_provisoire_to_validee(self, mock_event, mock_etudiants):
        inscription = self._inscription(statut="provisoire")
        inscription.annee_universitaire = SimpleNamespace(pk=1, date_debut=date(2026, 1, 1))
        etudiant = SimpleNamespace(
            annee_universitaire_actuelle=None,
            annee_universitaire_actuelle_id=None,
            statut="pre_inscrit",
            save=MagicMock(),
        )
        mock_etudiants.select_for_update.return_value.get.return_value = etudiant
        view = self._view_with_inscription(inscription)
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))

        with patch("apps.etudiants.api.ensure_academic_open"):
            response = view.valider(request, pk=1)

        assert response.status_code == 200
        assert inscription.statut == "validee"
        inscription.save.assert_called_once_with(update_fields=["statut", "updated_at"])
        assert etudiant.statut == "inscrit"
        assert etudiant.annee_universitaire_actuelle == inscription.annee_universitaire
        etudiant.save.assert_called_once_with(
            update_fields=["annee_universitaire_actuelle", "statut", "updated_at"]
        )
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


class EnrollmentFormationTenantTestCase(SimpleTestCase):
    def setUp(self):
        self.tenant = SimpleNamespace(pk=11)
        self.student = SimpleNamespace(pk=1, universite_id=11)
        self.year = SimpleNamespace(pk=2, universite_id=11)
        self.request = SimpleNamespace(tenant=self.tenant, user=SimpleNamespace(is_superuser=True))

    def formation(self, owner, *, via):
        return SimpleNamespace(
            pk=3,
            departement=SimpleNamespace(faculte=SimpleNamespace(universite_id=owner)) if via == "departement" else None,
            ecole_doctorale=SimpleNamespace(universite_id=owner) if via == "ecole_doctorale" else None,
            organisation_unit=SimpleNamespace(etablissement_id=owner) if via == "organisation_unit" else None,
        )

    def serializer(self, **context):
        return InscriptionAdministrativeSerializer(context={"request": self.request, **context})

    def test_create_rejects_foreign_department_formation(self):
        with pytest.raises(ValidationError) as error:
            self.serializer().validate(
                {
                    "etudiant": self.student,
                    "annee_universitaire": self.year,
                    "formation": self.formation(22, via="departement"),
                }
            )
        assert "formation" in error.value.detail

    def test_create_rejects_foreign_doctoral_school_and_organisation_unit(self):
        for via in ("ecole_doctorale", "organisation_unit"):
            with self.subTest(via=via), pytest.raises(ValidationError) as error:
                self.serializer().validate(
                    {
                        "etudiant": self.student,
                        "annee_universitaire": self.year,
                        "formation": self.formation(22, via=via),
                    }
                )
            assert "formation" in error.value.detail

    def test_controlled_transfer_rejects_foreign_formation(self):
        original = self.formation(11, via="departement")
        instance = SimpleNamespace(
            statut="validee",
            etudiant=self.student,
            etudiant_id=1,
            annee_universitaire=self.year,
            annee_universitaire_id=2,
            formation=original,
            formation_id=3,
            parcours=None,
            parcours_id=None,
        )
        serializer = InscriptionAdministrativeSerializer(
            instance, context={"request": self.request, "controlled_transfer": True}
        )
        with pytest.raises(ValidationError) as error:
            serializer.validate({"formation": self.formation(22, via="departement")})
        assert "formation" in error.value.detail

    def test_create_accepts_formation_owned_by_current_university(self):
        attrs = {
            "etudiant": self.student,
            "annee_universitaire": self.year,
            "formation": self.formation(11, via="departement"),
        }
        assert self.serializer().validate(attrs) == attrs
