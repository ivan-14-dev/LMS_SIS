"""API tests for emplois_du_temps."""

from apps.classes.models import Classe, Matiere
from apps.emplois_du_temps.models import Creneau
from apps.enseignants.models import Personnel
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.salles.models import Salle
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

    def test_conflits_detect_overlap_only_in_same_year_and_week(self):
        admin = Utilisateur.objects.create_superuser("collision-admin", etablissement=self.tenant)
        teacher = Utilisateur.objects.create_user("collision-teacher", role="enseignant", etablissement=self.tenant)
        personnel = Personnel.objects.create(user=teacher, matricule="collision-teacher", date_embauche="2026-01-01")
        year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2026-2027", date_debut="2026-09-01", date_fin="2027-07-01"
        )
        next_year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2027-2028", date_debut="2027-09-01", date_fin="2028-07-01"
        )
        level = Niveau.objects.create(etablissement=self.tenant, code="5e", libelle="Cinquieme")
        classes = [
            Classe.objects.create(etablissement=self.tenant, niveau=level, annee_scolaire=school_year, nom=name)
            for school_year, name in ((year, "5A"), (year, "5B"), (next_year, "5A"))
        ]
        subject = Matiere.objects.create(etablissement=self.tenant, code="COL", nom="Collisions")
        room = Salle.objects.create(etablissement=self.tenant, code="C1", nom="Salle C1")
        self.client.force_authenticate(admin)
        url = "/api/v1/edt/creneaux/"

        def create(classe, start, end, week):
            response = self.client.post(
                url,
                {
                    "classe": classe.pk,
                    "matiere": subject.pk,
                    "enseignant": personnel.pk,
                    "salle": room.pk,
                    "jour": 1,
                    "heure_debut": start,
                    "heure_fin": end,
                    "semaine": week,
                },
                format="json",
            )
            assert response.status_code == 201, response.data
            return response.data["id"]

        first = create(classes[0], "08:00", "09:00", 1)
        second = create(classes[1], "08:30", "09:30", 1)
        create(classes[1], "09:30", "10:00", 1)  # Contiguous, not overlapping.
        create(classes[1], "08:45", "09:15", 2)  # Alternating week.
        create(classes[2], "08:45", "09:15", 1)  # Different school year.

        response = self.client.get(f"{url}conflits/")
        assert response.status_code == 200, response.data
        assert response.data["total"] == 2
        assert {entry["type"] for entry in response.data["conflits"]} == {"enseignant_double", "salle_double"}
        for entry in response.data["conflits"]:
            assert set(entry["creneaux"]) == {first, second}
            assert entry["jour"] == 1
            assert entry["heure"] == "08:30:00"
