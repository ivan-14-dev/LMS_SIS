"""API tests for infirmerie."""

from apps.eleves.models import Eleve
from apps.infirmerie.models import DossierMedical
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from django_tenants.utils import schema_context


class InfirmerieAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `infirmerie` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/infirmerie/dossiers-medicaux/").url_name == "dossier-medical-list"
        assert resolve("/api/v1/infirmerie/visites-infirmerie/").url_name == "visite-infirmerie-list"
        assert resolve("/api/v1/infirmerie/stock-medicaments/").url_name == "stock-medicament-list"


class MedicalRecordTenantAccessTest(TenantAPITestCase):
    def test_foreign_nurse_cannot_read_or_change_local_medical_record(self):
        nurse = Utilisateur.objects.create_user("local-medical-nurse", role="infirmier", etablissement=self.tenant)
        student = Utilisateur.objects.create_user("local-medical-student", role="eleve", etablissement=self.tenant)
        pupil = Eleve.objects.create(
            user=student,
            etablissement=self.tenant,
            matricule="MEDICAL-TEST-1",
            date_naissance="2010-01-01",
            lieu_naissance="Test",
            sexe="F",
            date_inscription=timezone.localdate(),
        )
        dossier = DossierMedical.objects.create(eleve=pupil, observations="Donnée fictive")
        url = f"/api/v1/infirmerie/dossiers-medicaux/{dossier.pk}/"

        foreign = type(self.tenant)(schema_name="foreign_medical_access")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_nurse = Utilisateur.objects.create_user(
            "foreign-medical-nurse",
            password="Synthetic-Medical-Test-2026!",
            role="infirmier",
            etablissement=foreign,
        )
        login = self.client.post(
            "/api/v1/auth/token/",
            {"username": foreign_nurse.username, "password": "Synthetic-Medical-Test-2026!"},
            format="json",
        )
        assert login.status_code == 200, login.data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        assert self.client.get(url).status_code == 403
        assert self.client.get("/api/v1/infirmerie/dossiers-medicaux/").status_code == 403
        assert self.client.patch(url, {"observations": "Modification indue"}, format="json").status_code == 403
        dossier.refresh_from_db()
        assert dossier.observations == "Donnée fictive"

        self.client.credentials()
        self.client.force_authenticate(nurse)
        assert self.client.get(url).status_code == 200
        response = self.client.patch(url, {"observations": "Soin fictif"}, format="json")
        assert response.status_code == 200, response.data
        dossier.refresh_from_db()
        assert dossier.observations == "Soin fictif"
        visit = self.client.post(
            "/api/v1/infirmerie/visites-infirmerie/",
            {
                "eleve": pupil.pk,
                "date": timezone.now().isoformat(),
                "heure_arrivee": "09:00",
                "motif": "Visite fictive",
                "traitement_administre": "Soin fictif",
            },
            format="json",
        )
        assert visit.status_code == 201, visit.data
        assert visit.data["traitement_administre"] == "Soin fictif"
