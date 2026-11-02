"""API tests for emplois_du_temps."""

from apps.classes.models import Classe, Matiere
from apps.emplois_du_temps.models import Creneau
from apps.enseignants.models import Personnel
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class EmploisDuTempsAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `emplois_du_temps` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/edt/creneaux/").url_name == "creneau-list"
        assert resolve("/api/v1/edt/contraintes/").url_name == "contrainte-list"


class ScheduleWorkflowTest(TenantAPITestCase):
    def test_schedule_creation_and_teacher_and_learner_visibility(self):
        admin = Utilisateur.objects.create_superuser("schedule-admin", etablissement=self.tenant)
        teacher = Utilisateur.objects.create_user("schedule-teacher", role="enseignant", etablissement=self.tenant)
        other = Utilisateur.objects.create_user("other-teacher", role="enseignant", etablissement=self.tenant)
        profiles = [
            Personnel.objects.create(user=user, matricule=user.username, date_embauche="2026-01-01")
            for user in (teacher, other)
        ]
        year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="Schedule", date_debut="2026-09-01", date_fin="2027-07-01"
        )
        level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixieme")
        classe = Classe.objects.create(etablissement=self.tenant, niveau=level, annee_scolaire=year, nom="6A")
        subject = Matiere.objects.create(etablissement=self.tenant, code="MAT", nom="Maths")
        data = {
            "classe": classe.pk,
            "matiere": subject.pk,
            "enseignant": profiles[0].pk,
            "jour": 1,
            "heure_debut": "08:00",
            "heure_fin": "09:00",
        }
        self.client.force_authenticate(admin)
        url = "/api/v1/edt/creneaux/"
        response = self.client.post(url, data, format="json")
        assert response.status_code == 201, response.data
        own_id = response.data["id"]
        assert self.client.post(url, {**data, "heure_fin": "07:00"}, format="json").status_code == 400
        assert self.client.post(url, {**data, "enseignant": profiles[1].pk}, format="json").status_code == 201
        self.client.force_authenticate(teacher)
        response = self.client.get(url, {"all": "1"})
        assert [row["id"] for row in response.data["results"]] == [own_id]
        response = self.client.get(f"{url}par_enseignant/", {"enseignant_id": profiles[1].pk})
        assert response.data["creneaux"] == []
        learner = Utilisateur.objects.create_user("no-profile", role="eleve", etablissement=self.tenant)
        self.client.force_authenticate(learner)
        assert self.client.get(url).data["results"] == []
        assert Creneau.objects.count() == 2
