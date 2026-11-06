"""API tests for infirmerie."""

from apps.eleves.models import Eleve
from apps.infirmerie.models import DossierMedical, VisiteInfirmerie
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
    def test_local_nurse_cannot_read_foreign_pupil_records_in_tenant_schema(self):
        nurse = Utilisateur.objects.create_user("nurse-medical-boundary", role="infirmier", etablissement=self.tenant)
        local_user = Utilisateur.objects.create_user(
            "student-medical-boundary", role="eleve", etablissement=self.tenant
        )
        local_pupil = Eleve.objects.create(
            user=local_user,
            etablissement=self.tenant,
            matricule="MEDICAL-BOUNDARY-LOCAL",
            date_naissance="2010-01-01",
            lieu_naissance="Test",
            sexe="F",
            date_inscription=timezone.localdate(),
        )
        local_dossier = DossierMedical.objects.create(eleve=local_pupil, observations="Donnée locale fictive")

        foreign = type(self.tenant)(schema_name="foreign_medical_records")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_user = Utilisateur.objects.create_user(
            "student-foreign-medical-boundary", role="eleve", etablissement=foreign
        )
        foreign_pupil = Eleve.objects.create(
            user=foreign_user,
            etablissement=foreign,
            matricule="MEDICAL-BOUNDARY-FOREIGN",
            date_naissance="2010-01-01",
            lieu_naissance="Test",
            sexe="F",
            date_inscription=timezone.localdate(),
        )
        foreign_dossier = DossierMedical.objects.create(eleve=foreign_pupil, observations="Donnée étrangère fictive")
        foreign_visit = VisiteInfirmerie.objects.create(
            eleve=foreign_pupil,
            infirmier=nurse,
            date=timezone.now(),
            heure_arrivee="09:00",
            motif="Visite étrangère fictive",
        )
        local_visit = VisiteInfirmerie.objects.create(
            eleve=local_pupil,
            infirmier=nurse,
            date=timezone.now(),
            heure_arrivee="09:00",
            motif="Visite locale fictive",
        )

        self.client.force_authenticate(nurse)
        base = "/api/v1/infirmerie/"
        assert self.client.get(f"{base}dossiers-medicaux/{local_dossier.pk}/").status_code == 200
        assert self.client.get(f"{base}visites-infirmerie/{local_visit.pk}/").status_code == 200
        dossiers = self.client.get(f"{base}dossiers-medicaux/")
        assert dossiers.status_code == 200
        assert [row["id"] for row in dossiers.data["results"]] == [local_dossier.pk]
        assert self.client.get(f"{base}dossiers-medicaux/{foreign_dossier.pk}/").status_code == 404
        assert self.client.get(f"{base}dossiers-medicaux/{foreign_dossier.pk}/visites/").status_code == 404
        assert self.client.patch(
            f"{base}dossiers-medicaux/{foreign_dossier.pk}/",
            {"observations": "Modification indue"},
            format="json",
        ).status_code == 404
        foreign_dossier.refresh_from_db()
        assert foreign_dossier.observations == "Donnée étrangère fictive"
        visites = self.client.get(f"{base}visites-infirmerie/")
        assert visites.status_code == 200
        assert [row["id"] for row in visites.data["results"]] == [local_visit.pk]
        assert self.client.get(f"{base}visites-infirmerie/{foreign_visit.pk}/").status_code == 404
        stats = self.client.get(f"{base}visites-infirmerie/statistiques/")
        assert stats.status_code == 200
        assert stats.data["total"] == 1

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
