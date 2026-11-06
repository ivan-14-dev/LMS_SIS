"""API tests for discipline."""

from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone

from apps.discipline.models import Incident, Sanction
from apps.eleves.models import Eleve
from apps.enseignants.models import Personnel
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur


class DisciplineAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `discipline` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/discipline/incidents/").url_name == "incident-list"
        assert resolve("/api/v1/discipline/sanctions/").url_name == "sanction-list"
        assert resolve("/api/v1/discipline/conseils-discipline/").url_name == "conseil-discipline-list"


class IncidentStatusAPITestCase(TenantAPITestCase):
    def test_sanctioned_incident_cannot_be_classed_by_patch(self):
        admin = Utilisateur.objects.create_superuser(
            "discipline-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        student_user = Utilisateur.objects.create_user(
            "discipline-student", role="eleve", etablissement=self.tenant
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=student_user,
            matricule="DISC-API-001",
            date_naissance="2012-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )
        rapporteur = Personnel.objects.create(
            user=admin, matricule="DISC-STAFF-001", date_embauche="2020-09-01"
        )
        incident = Incident.objects.create(
            eleve=eleve,
            date_incident=timezone.now(),
            type="comportement",
            description="Incident de test",
            rapporteur=rapporteur,
        )
        url = f"/api/v1/discipline/incidents/{incident.pk}/"
        response = self.client.post(
            "/api/v1/discipline/sanctions/",
            {
                "incident": incident.pk,
                "type": "avertissement",
                "date_effet": timezone.localdate().isoformat(),
                "motif": "Rappel du règlement",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        incident.refresh_from_db()
        assert incident.statut == "sanctionne"

        assert self.client.post(f"{url}classer/").status_code == 400
        response = self.client.patch(url, {"statut": "classe"}, format="json")
        assert response.status_code == 400, response.data
        assert "statut" in response.data
        incident.refresh_from_db()
        assert incident.statut == "sanctionne"

        response = self.client.patch(url, {"description": "Rapport complété"}, format="json")
        assert response.status_code == 200, response.data
        incident.refresh_from_db()
        assert incident.description == "Rapport complété"
        assert incident.statut == "sanctionne"

        pending = Incident.objects.create(
            eleve=eleve,
            date_incident=timezone.now(),
            type="comportement",
            description="Autre incident",
            rapporteur=rapporteur,
        )
        pending_url = f"/api/v1/discipline/incidents/{pending.pk}/"
        assert self.client.patch(pending_url, {"statut": "en_instruction"}, format="json").status_code == 200
        assert self.client.post(f"{pending_url}classer/").status_code == 200
        response = self.client.patch(pending_url, {"statut": "ouvert"}, format="json")
        assert response.status_code == 400, response.data
        pending.refresh_from_db()
        assert pending.statut == "classe"

    def test_sanction_decision_rejects_wrong_role_late_and_replayed_requests(self):
        admin = Utilisateur.objects.create_superuser(
            "discipline-decision-admin", role="super_admin", etablissement=self.tenant
        )
        parent = Utilisateur.objects.create_user(
            "discipline-decision-parent", role="parent", etablissement=self.tenant
        )
        student_user = Utilisateur.objects.create_user(
            "discipline-decision-student", role="eleve", etablissement=self.tenant
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=student_user,
            matricule="DISC-DECISION-001",
            date_naissance="2012-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )
        rapporteur = Personnel.objects.create(
            user=admin, matricule="DISC-DECISION-STAFF", date_embauche="2020-09-01"
        )
        incident = Incident.objects.create(
            eleve=eleve,
            date_incident=timezone.now(),
            type="comportement",
            description="Incident en instruction",
            rapporteur=rapporteur,
            statut="en_instruction",
        )
        url = "/api/v1/discipline/sanctions/"
        payload = {
            "incident": incident.pk,
            "type": "avertissement",
            "date_effet": timezone.localdate().isoformat(),
            "motif": "Rappel du règlement",
        }

        self.client.force_authenticate(parent)
        response = self.client.post(url, payload, format="json")
        assert response.status_code == 403, response.data
        assert not Sanction.objects.filter(incident=incident).exists()

        self.client.force_authenticate(admin)
        response = self.client.post(url, payload, format="json")
        assert response.status_code == 201, response.data
        incident.refresh_from_db()
        assert incident.statut == "sanctionne"

        response = self.client.post(url, payload, format="json")
        assert response.status_code == 400, response.data
        assert "incident" in response.data
        assert Sanction.objects.filter(incident=incident).count() == 1

        late = Incident.objects.create(
            eleve=eleve,
            date_incident=timezone.now(),
            type="comportement",
            description="Incident classé",
            rapporteur=rapporteur,
        )
        response = self.client.post(f"/api/v1/discipline/incidents/{late.pk}/classer/")
        assert response.status_code == 200, response.data
        late_payload = {**payload, "incident": late.pk}
        response = self.client.post(url, late_payload, format="json")
        assert response.status_code == 400, response.data
        assert "incident" in response.data
        late.refresh_from_db()
        assert late.statut == "classe"
        assert not Sanction.objects.filter(incident=late).exists()
