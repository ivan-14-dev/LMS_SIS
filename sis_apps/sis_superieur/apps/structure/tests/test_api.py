"""API tests for structure."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apps.enseignants.models import AffectationEnseignement, EnseignantChercheur
from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.structure.api import DepartementsViewSet, EcolesDoctoralesViewSet, FacultesViewSet, IsAdminOrReadOnly
from apps.structure.models import Departement, Faculte
from apps.ue_ecue.models import UE
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class StructureAPITestCase(SimpleTestCase):
    def test_structure_history_routes_are_registered(self):
        faculte_history = resolve("/api/v1/structure/facultes/1/historique/")
        departement_history = resolve("/api/v1/structure/departements/1/historique/")
        ecole_history = resolve("/api/v1/structure/ecoles-doctorales/1/historique/")

        assert faculte_history.url_name == "faculte-historique"
        assert departement_history.url_name == "departement-historique"
        assert ecole_history.url_name == "ecole-doctorale-historique"


class IsAdminOrReadOnlyPermissionTestCase(SimpleTestCase):
    def setUp(self):
        self.permission = IsAdminOrReadOnly()
        self.view = SimpleNamespace()

    def test_read_only_methods_always_allowed(self):
        request = SimpleNamespace(method="GET", user=SimpleNamespace(is_authenticated=True))
        assert self.permission.has_permission(request, self.view) is True

    @patch("apps.structure.api.has_business_permission_or_role", return_value=False)
    def test_write_denied_without_admin_role(self, _mock_role):
        request = SimpleNamespace(method="POST", user=SimpleNamespace(is_authenticated=True))
        assert self.permission.has_permission(request, self.view) is False

    @patch("apps.structure.api.has_business_permission_or_role", return_value=True)
    def test_write_allowed_with_admin_role(self, _mock_role):
        request = SimpleNamespace(method="POST", user=SimpleNamespace(is_authenticated=True))
        assert self.permission.has_permission(request, self.view) is True

    def test_unauthenticated_user_is_denied(self):
        request = SimpleNamespace(method="GET", user=SimpleNamespace(is_authenticated=False))
        assert self.permission.has_permission(request, self.view) is False


class TenantScopedQuerysetTestCase(SimpleTestCase):
    """Vérifie que chaque ViewSet restreint son queryset à l'université du tenant courant."""

    def _view(self, viewset_class, tenant):
        view = viewset_class()
        view.request = SimpleNamespace(tenant=tenant)
        return view

    @patch("apps.structure.api.Faculte")
    def test_facultes_queryset_is_filtered_by_tenant(self, mock_model):
        tenant = SimpleNamespace(id=1)
        view = self._view(FacultesViewSet, tenant)

        view.get_queryset()

        mock_model.objects.select_related.assert_called_once_with("universite", "doyen")
        mock_model.objects.select_related.return_value.filter.assert_called_once_with(universite=tenant)

    @patch("apps.structure.api.Departement")
    def test_departements_queryset_is_filtered_by_tenant_universite(self, mock_model):
        tenant = SimpleNamespace(id=1)
        view = self._view(DepartementsViewSet, tenant)

        view.get_queryset()

        mock_model.objects.select_related.assert_called_once_with("faculte", "directeur")
        mock_model.objects.select_related.return_value.filter.assert_called_once_with(faculte__universite=tenant)

    @patch("apps.structure.api.EcoleDoctorale")
    def test_ecoles_doctorales_queryset_is_filtered_by_tenant(self, mock_model):
        tenant = SimpleNamespace(id=1)
        view = self._view(EcolesDoctoralesViewSet, tenant)

        view.get_queryset()

        mock_model.objects.select_related.assert_called_once_with("universite", "directeur")
        mock_model.objects.select_related.return_value.filter.assert_called_once_with(universite=tenant)


class FacultesActionsTestCase(SimpleTestCase):
    def test_formations_action_filters_by_faculte_departements(self):
        view = FacultesViewSet()
        faculte = MagicMock()
        view.get_object = MagicMock(return_value=faculte)

        with patch("apps.formations.models.Formation") as mock_formation, patch(
            "apps.formations.serializers.FormationListSerializer"
        ) as mock_serializer:
            mock_serializer.return_value.data = []
            response = view.formations(SimpleNamespace(), pk=1)

            mock_formation.objects.filter.assert_called_once_with(departement__faculte=faculte)
            assert response.status_code == 200

    def test_departements_action_returns_related_departements(self):
        view = FacultesViewSet()
        departements_manager = MagicMock()
        faculte = SimpleNamespace(departements=departements_manager)
        view.get_object = MagicMock(return_value=faculte)

        response = view.departements(SimpleNamespace(), pk=1)

        departements_manager.select_related.assert_called_once_with("directeur")
        assert response.status_code == 200


class DepartementEnseignantsAPITestCase(TenantAPITestCase):
    def test_enseignants_route_lists_each_teacher_once_across_multiple_affectations(self):
        user = Utilisateur.objects.create_user(
            "structure-reader", role="scolarite", etablissement=self.tenant
        )
        self.client.force_authenticate(user)
        faculte = Faculte.objects.create(universite=self.tenant, code="SCI", nom="Sciences")
        departement = Departement.objects.create(faculte=faculte, code="INFO", nom="Informatique")
        formation = Formation.objects.create(departement=departement, code="LIC", nom="Licence", type="licence")
        year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )
        semester = Semestre.objects.create(
            annee_universitaire=year, numero=1, type="impair",
            date_debut="2026-09-01", date_fin="2027-01-31",
        )
        maquette = MaquetteFormation.objects.create(formation=formation, annee_universitaire=year)
        teacher = EnseignantChercheur.objects.create(
            user=Utilisateur.objects.create_user("structure-teacher", etablissement=self.tenant),
            specialite="Informatique",
        )
        for code in ("ALG", "SYS"):
            ue = UE.objects.create(
                maquette=maquette, semestre=semester, code=code, nom=code, credits_ects=6,
            )
            AffectationEnseignement.objects.create(
                enseignant=teacher, ue=ue, annee_universitaire=year,
                type_enseignement="CM", heures=12,
            )

        response = self.client.get(f"/api/v1/structure/departements/{departement.pk}/enseignants/")

        assert response.status_code == 200, response.data
        assert [item["id"] for item in response.data] == [teacher.pk]
