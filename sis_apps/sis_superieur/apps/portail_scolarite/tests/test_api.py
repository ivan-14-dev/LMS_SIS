"""API tests for portail_scolarite."""

from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant, InscriptionAdministrative
from apps.formations.models import Formation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.structure.models import Departement, Faculte
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.portail_scolarite.api import PortailScolariteViewSet


class PortailScolariteAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/tableau_bord/")

        assert match.url_name == "portail-staff-tableau-bord"

    def test_alertes_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/alertes/")

        assert match.url_name == "portail-staff-alertes"


class DossierEtudiantScopeTestCase(TenantAPITestCase):
    def test_only_scoped_inscriptions_are_included_in_accessible_dossier(self):
        agent = Utilisateur.objects.create_user(
            username="staff_scoped", role="scolarite", etablissement=self.tenant
        )
        faculty = Faculte.objects.create(universite=self.tenant, nom="Sciences", code="SCI")
        department = Departement.objects.create(faculte=faculty, nom="Math", code="MAT")
        allowed = Formation.objects.create(departement=department, nom="Math", code="M", type="licence")
        denied = Formation.objects.create(departement=department, nom="Physics", code="P", type="licence")
        year_a = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2024-2025", date_debut="2024-09-01", date_fin="2025-08-31"
        )
        year_b = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-08-31"
        )
        student_user = Utilisateur.objects.create_user(
            username="student_scoped", role="etudiant", etablissement=self.tenant
        )
        student = Etudiant.objects.create(
            user=student_user, universite=self.tenant, matricule="S-01", date_naissance="2000-01-01"
        )
        visible = InscriptionAdministrative.objects.create(
            etudiant=student, formation=allowed, annee_universitaire=year_a, date_inscription="2024-09-01"
        )
        InscriptionAdministrative.objects.create(
            etudiant=student, formation=denied, annee_universitaire=year_b, date_inscription="2025-09-01"
        )
        other_user = Utilisateur.objects.create_user(
            username="student_hidden", role="etudiant", etablissement=self.tenant
        )
        other = Etudiant.objects.create(
            user=other_user, universite=self.tenant, matricule="S-02", date_naissance="2000-01-01"
        )
        InscriptionAdministrative.objects.create(
            etudiant=other, formation=denied, annee_universitaire=year_a, date_inscription="2024-09-01"
        )
        agent.attributs_acces = {
            "permission_scopes": {"etudiants.view_etudiant": {"formations": [allowed.pk]}}
        }
        agent.save(update_fields=["attributs_acces"])

        def dossier(student_id):
            request = APIRequestFactory().get("/", {"etudiant_id": student_id})
            request.tenant = self.tenant
            force_authenticate(request, user=agent)
            return PortailScolariteViewSet.as_view({"get": "dossier_etudiant"})(request)

        response = dossier(student.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["inscriptions"]], [visible.pk])
        self.assertEqual(dossier(other.pk).status_code, 404)
