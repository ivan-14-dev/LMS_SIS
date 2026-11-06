from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.apps import apps
from django.utils import timezone
from django_tenants.utils import schema_context


class SchoolServicesWorkflowTest(TenantAPITestCase):
    def create(self, model, **values):
        return apps.get_model(model).objects.create(**values)

    def setUp(self):
        self.today = timezone.localdate()
        self.day = self.today.isoformat()
        self.instant = timezone.now().isoformat()
        self.admin = Utilisateur.objects.create_superuser(
            "services-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        self.year_values = {
            "libelle": str(self.today.year),
            "date_debut": self.today.replace(month=1, day=1),
            "date_fin": self.today.replace(month=12, day=31),
        }
        self.year = self.create("etablissement.AnneeScolaire", etablissement=self.tenant, **self.year_values)
        self.period_values = {
            "type": "trimestre",
            "numero": 1,
            **{key: self.year_values[key] for key in ("date_debut", "date_fin")},
        }
        self.period = self.create("etablissement.Periode", annee_scolaire=self.year, **self.period_values)
        level = self.create("etablissement.Niveau", etablissement=self.tenant, code="6e", libelle="Sixième")
        self.classe = self.create(
            "classes.Classe", etablissement=self.tenant, annee_scolaire=self.year, niveau=level, nom="6A"
        )
        pupil = Utilisateur.objects.create_user("services-pupil", role="eleve", etablissement=self.tenant)
        self.pupil = self.create(
            "eleves.Eleve",
            etablissement=self.tenant,
            user=pupil,
            matricule="SERV-1",
            date_naissance="2005-01-01",
            lieu_naissance="Test",
            sexe="F",
            date_inscription=self.today,
            classe_actuelle=self.classe,
        )
        teacher = Utilisateur.objects.create_user("services-teacher", role="enseignant", etablissement=self.tenant)
        self.teacher = self.create("enseignants.Personnel", user=teacher, matricule="ENS-1", date_embauche=self.today)

    def post(self, resource, **payload):
        response = self.client.post(f"/api/v1/{resource}/", payload, format="json")
        assert response.status_code == 201, response.data
        record = response.data
        detail = self.client.get(f"/api/v1/{resource}/{record['id']}/")
        assert detail.status_code == 200, detail.data
        listing = self.client.get(f"/api/v1/{resource}/")
        assert listing.status_code == 200, listing.data
        assert record["id"] in [row["id"] for row in listing.data["results"]]
        if "eleve_classe" in record:
            assert record["eleve_classe"] == "6A"
        return record

    def test_clubs_meals_rooms_and_transport_can_be_created_and_retrieved(self):
        club = self.post(
            "clubs",
            nom="Club recette",
            type="culturel",
            description="Recette",
            responsable=self.admin.pk,
            horaires="Mercredi",
            date_creation=self.day,
            capacite=30,
        )
        self.post("clubs/membres-clubs", club=club["id"], eleve=self.pupil.pk)
        self.post(
            "clubs/activites-clubs",
            club=club["id"],
            date=self.day,
            heure_debut="14:00",
            heure_fin="15:00",
            activite="Recette",
        )
        menu = self.post("cantine/menus", date=self.day, plat="Repas recette", prix="3.75", regime="standard")
        self.post("cantine/inscriptions-cantine", eleve=self.pupil.pk, date_debut=self.day, regime="standard")
        self.post("cantine/presences-cantine", eleve=self.pupil.pk, menu=menu["id"], present=True)
        building = self.post("internat/batiments", nom="Bâtiment recette")
        room = self.post("internat/chambres", batiment=building["id"], numero="A1", type="double", capacite=2)
        self.post("internat/occupants-chambres", chambre=room["id"], eleve=self.pupil.pk, date_debut=self.day)
        line = self.post("transport/lignes-transport", nom="Ligne recette", itineraire="Trajet recette")
        stop = self.post("transport/arrets", ligne=line["id"], nom="Arrêt recette", heure_passage="07:30", ordre=1)
        vehicle = self.post(
            "transport/vehicules",
            immatriculation="TEST-1",
            capacite=30,
            ligne=line["id"],
            chauffeur="Conducteur recette",
            telephone_chauffeur="0000000000",
        )
        assert vehicle["chauffeur"] == "Conducteur recette"
        self.post(
            "transport/inscriptions-transport",
            eleve=self.pupil.pk,
            ligne=line["id"],
            arret_montee=stop["id"],
            arret_descente=stop["id"],
            annee_scolaire=self.year.pk,
        )

    def test_incidents_and_sanctions_preserve_datetime_and_validate_partial_date_changes(self):
        incident = self.post(
            "discipline/incidents",
            eleve=self.pupil.pk,
            date_incident=self.instant,
            type="comportement",
            gravite=1,
            description="Incident fictif de recette",
            rapporteur=self.teacher.pk,
        )
        assert incident["rapporteur"] == self.teacher.pk
        sanction = self.post(
            "discipline/sanctions",
            incident=incident["id"],
            type="avertissement",
            date_effet=self.day,
            date_fin=self.day,
            motif="Recette",
        )
        url = f"/api/v1/discipline/sanctions/{sanction['id']}/"
        response = self.client.patch(url, {"date_fin": "2000-01-01"}, format="json")
        assert response.status_code == 400, response.data
        response = self.client.patch(url, {"date_fin": None}, format="json")
        assert response.status_code == 200, response.data
        assert response.data["date_fin"] is None
        assert self.client.get(url).data["date_fin"] is None

    def test_open_ended_enrollments_reject_reversed_dates_on_create_and_update(self):
        building = self.create("internat.BatimentInternat", nom="B1")
        room = self.create("internat.Chambre", batiment=building, numero="1")
        for resource, extra in [
            ("cantine/inscriptions-cantine", {}),
            ("internat/occupants-chambres", {"chambre": room.pk}),
        ]:
            payload = {"eleve": self.pupil.pk, "date_debut": self.day, "date_fin": "2000-01-01", **extra}
            response = self.client.post(f"/api/v1/{resource}/", payload, format="json")
            assert response.status_code == 400, response.data
            record = self.post(resource, **{**payload, "date_fin": self.day})
            url = f"/api/v1/{resource}/{record['id']}/"
            response = self.client.patch(url, {"date_debut": "2099-01-01"}, format="json")
            assert response.status_code == 400, response.data
            response = self.client.patch(url, {"date_fin": None}, format="json")
            assert response.status_code == 200, response.data
            assert response.data["date_fin"] is None

    def test_transport_rejects_inconsistent_stops_and_foreign_academic_years(self):
        first = self.create("transport.LigneTransport", nom="L1", itineraire="Route")
        second = self.create("transport.LigneTransport", nom="L2", itineraire="Route")
        self.create("transport.Vehicule", immatriculation="SERV-TRANSPORT-1", capacite=2, ligne=first)
        stop = self.create("transport.Arret", ligne=first, nom="A1", heure_passage="07:30", ordre=1)
        payload = {
            "eleve": self.pupil.pk,
            "ligne": first.pk,
            "arret_montee": stop.pk,
            "arret_descente": stop.pk,
            "annee_scolaire": self.year.pk,
        }
        response = self.client.post(
            "/api/v1/transport/inscriptions-transport/", {**payload, "ligne": second.pk}, format="json"
        )
        assert response.status_code == 400, response.data
        record = self.post("transport/inscriptions-transport", **payload)
        foreign = type(self.tenant)(schema_name="foreign_services")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        year = self.create("etablissement.AnneeScolaire", etablissement=foreign, **self.year_values)
        url = f"/api/v1/transport/inscriptions-transport/{record['id']}/"
        for changes in [{"ligne": second.pk}, {"annee_scolaire": year.pk}]:
            response = self.client.patch(url, changes, format="json")
            assert response.status_code == 400, response.data
        assert self.client.get(url).data["ligne"] == first.pk

    def test_council_uses_real_status_transitions_and_rejects_wrong_year(self):
        payload = {
            "classe": self.classe.pk,
            "periode": self.period.pk,
            "president": self.admin.pk,
            "date": self.instant,
        }
        other_year = self.create(
            "etablissement.AnneeScolaire",
            etablissement=self.tenant,
            **{**self.year_values, "libelle": "Autre année"},
        )
        other_period = self.create("etablissement.Periode", annee_scolaire=other_year, **self.period_values)
        response = self.client.post(
            "/api/v1/conseils/conseils-classe/", {**payload, "periode": other_period.pk}, format="json"
        )
        assert response.status_code == 400, response.data
        record = self.post("conseils/conseils-classe", **payload)
        assert record["periode_nom"] == str(self.period)
        base = f"/api/v1/conseils/conseils-classe/{record['id']}/"
        assert self.client.post(f"{base}valider/").status_code == 400
        assert self.client.post(f"{base}tenir/").status_code == 200
        assert self.client.post(f"{base}valider/").status_code == 200
        assert self.client.get(base).data["statut"] == "valide"
        assert self.client.get(f"{base}historique/").status_code == 200

    def test_medical_records_bind_author_and_remain_restricted(self):
        nurse = Utilisateur.objects.create_user("services-nurse", role="infirmier", etablissement=self.tenant)
        self.client.force_authenticate(nurse)
        roster = self.client.get("/api/v1/eleves/")
        assert roster.status_code == 200, roster.data
        assert self.pupil.pk in [row["id"] for row in roster.data["results"]]
        payload = {
            "eleve": self.pupil.pk,
            "date": self.instant,
            "heure_arrivee": "09:00",
            "motif": "Donnée fictive de recette",
            "infirmier": self.admin.pk,
        }
        visit = self.post("infirmerie/visites-infirmerie", **payload)
        assert visit["infirmier"] == nurse.pk
        url = f"/api/v1/infirmerie/visites-infirmerie/{visit['id']}/"
        response = self.client.patch(url, {"infirmier": self.admin.pk, "heure_sortie": None}, format="json")
        assert response.status_code == 200, response.data
        assert response.data["infirmier"] == nurse.pk
        self.post("infirmerie/stock-medicaments", nom="Article fictif", quantite=0, unite="unité")
        self.client.force_authenticate(self.pupil.user)
        assert self.client.get(url).status_code == 403
        assert self.client.post("/api/v1/infirmerie/visites-infirmerie/", payload, format="json").status_code == 403
