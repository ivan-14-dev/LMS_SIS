"""API tests for salles."""

from unittest.mock import patch

from apps.classes.models import Classe, Matiere
from apps.core.models import WorkflowEvent
from apps.emplois_du_temps.models import Creneau
from apps.enseignants.models import Personnel
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.salles.models import Equipement, IndisponibiliteSalle, Salle
from apps.utilisateurs.models import Utilisateur
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context


class SallesAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `salles` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/salles/").url_name == "salle-list"
        assert resolve("/api/v1/salles/equipements/").url_name == "equipement-list"
        assert resolve("/api/v1/salles/equipements/1/").url_name == "equipement-detail"
        assert resolve("/api/v1/salles/indisponibilites/").url_name == "indisponibilite-salle-list"


class SalleCapacityAPITestCase(TenantAPITestCase):
    def test_room_capacity_must_be_positive_on_create_and_update(self):
        admin = Utilisateur.objects.create_superuser(
            "salles-admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        url = "/api/v1/salles/"

        rejected = self.client.post(
            url, {"code": "S0", "nom": "Salle vide", "capacite": 0}, format="json"
        )
        assert rejected.status_code == 400, rejected.data
        assert "capacite" in rejected.data
        assert not Salle.objects.filter(code="S0").exists()

        room = self.client.post(
            url, {"code": "S1", "nom": "Salle valide", "capacite": 1}, format="json"
        )
        assert room.status_code == 201, room.data
        room_url = f"{url}{room.data['id']}/"
        rejected = self.client.patch(room_url, {"capacite": 0}, format="json")
        assert rejected.status_code == 400, rejected.data
        assert "capacite" in rejected.data
        assert self.client.get(room_url).data["capacite"] == 1


class EquipementAPITestCase(TenantAPITestCase):
    url = "/api/v1/salles/equipements/"

    def setUp(self):
        admin = Utilisateur.objects.create_superuser(
            "equipements-admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        self.room = Salle.objects.create(
            etablissement=self.tenant, code="EQ-1", nom="Salle A", capacite=1
        )
        self.other_room = Salle.objects.create(
            etablissement=self.tenant, code="EQ-2", nom="Salle B", capacite=30
        )

    def test_register_assign_move_unassign_and_list(self):
        created = self.client.post(
            self.url, {"identifiant": "INV-001", "nom": "Vidéoprojecteur"}, format="json"
        )
        assert created.status_code == 201, created.data
        assert created.data["etablissement"] == self.tenant.pk
        assert created.data["salle"] is None
        detail_url = f"{self.url}{created.data['id']}/"

        duplicate = self.client.post(
            self.url, {"identifiant": "INV-001", "nom": "Autre appareil"}, format="json"
        )
        assert duplicate.status_code == 400, duplicate.data
        assert "identifiant" in duplicate.data
        other = self.client.post(
            self.url, {"identifiant": "INV-002", "nom": "Écran"}, format="json"
        )
        assert other.status_code == 201, other.data
        duplicate_update = self.client.patch(
            f"{self.url}{other.data['id']}/", {"identifiant": "INV-001"}, format="json"
        )
        assert duplicate_update.status_code == 400, duplicate_update.data
        assert "identifiant" in duplicate_update.data

        for room in (self.room, self.other_room):
            assigned = self.client.patch(detail_url, {"salle": room.pk}, format="json")
            assert assigned.status_code == 200, assigned.data
            assert assigned.data["salle"] == room.pk
            assert assigned.data["salle_nom"] == room.nom
            assert self.client.get(detail_url).data["salle"] == room.pk

        listing = self.client.get(self.url, {"salle": self.other_room.pk})
        assert listing.status_code == 200, listing.data
        results = listing.data.get("results", listing.data)
        assert [item["identifiant"] for item in results] == ["INV-001"]
        assert self.client.get(f"{self.url}{other.data['id']}/").data["identifiant"] == "INV-002"
        assert self.client.patch(detail_url, {"salle": None}, format="json").status_code == 200
        assert self.client.get(detail_url).data["salle"] is None
        assert self.client.get(f"/api/v1/salles/{self.room.pk}/").data["capacite"] == 1

    def test_foreign_establishment_and_room_are_rejected_and_hidden(self):
        foreign = type(self.tenant)(schema_name="foreign_equipment")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_room = Salle.objects.create(
            etablissement=foreign, code="FOREIGN", nom="Hors établissement"
        )
        foreign_asset = Equipement.objects.create(
            etablissement=foreign, identifiant="INV-001", nom="Non visible", salle=foreign_room
        )
        invalid_room = self.client.post(
            self.url, {"identifiant": "INV-003", "nom": "Invalide", "salle": 99999999},
            format="json",
        )
        assert invalid_room.status_code == 400, invalid_room.data
        assert "salle" in invalid_room.data

        created = self.client.post(
            self.url,
            {"identifiant": "INV-001", "nom": "Appareil local", "salle": self.room.pk},
            format="json",
        )
        assert created.status_code == 201, created.data
        detail_url = f"{self.url}{created.data['id']}/"
        for payload in (
            {"salle": foreign_room.pk},
            {"etablissement": foreign.pk},
        ):
            rejected = self.client.post(
                self.url, {"identifiant": "INV-002", "nom": "Autre", **payload}, format="json"
            )
            assert rejected.status_code == 400, rejected.data
            rejected = self.client.patch(detail_url, payload, format="json")
            assert rejected.status_code == 400, rejected.data
        assert self.client.get(detail_url).data["salle"] == self.room.pk
        assert self.client.get(f"{self.url}{foreign_asset.pk}/").status_code == 404
        listing = self.client.get(self.url)
        results = listing.data.get("results", listing.data)
        assert [item["id"] for item in results] == [created.data["id"]]

    def test_deactivation_releases_assignment_and_keeps_audited_history(self):
        created = self.client.post(
            self.url,
            {"identifiant": "INV-LIFE", "nom": "Projecteur", "salle": self.room.pk},
            format="json",
        )
        assert created.status_code == 201, created.data
        assert created.data["actif"] is True
        equipment = Equipement.objects.get(pk=created.data["id"])
        detail_url = f"{self.url}{equipment.pk}/"
        events = WorkflowEvent.objects.filter(
            app_label="salles", model="equipement", object_id=str(equipment.pk)
        )
        assert events.get(action="creation").metadata["apres"]["salle_id"] == self.room.pk

        rejected = self.client.patch(
            detail_url, {"actif": False, "salle": self.other_room.pk}, format="json"
        )
        assert rejected.status_code == 400, rejected.data
        assert "salle" in rejected.data
        equipment.refresh_from_db()
        assert equipment.actif is True
        assert equipment.salle_id == self.room.pk
        assert events.count() == 1

        disabled = self.client.patch(detail_url, {"actif": False}, format="json")
        assert disabled.status_code == 200, disabled.data
        equipment.refresh_from_db()
        assert equipment.actif is False
        assert equipment.salle_id is None
        event = events.get(action="desactivation")
        assert event.actor.username == "equipements-admin"
        assert event.tenant_id == self.tenant.pk
        assert event.metadata == {
            "avant": {
                "actif": True, "salle_id": self.room.pk,
                "salle_code": self.room.code, "salle_nom": self.room.nom,
            },
            "apres": {"actif": False, "salle_id": None, "salle_code": None, "salle_nom": None},
        }
        assert self.client.patch(detail_url, {"actif": False}, format="json").status_code == 200
        for room in (self.room, self.other_room):
            rejected = self.client.patch(detail_url, {"salle": room.pk}, format="json")
            assert rejected.status_code == 400, rejected.data
            assert "salle" in rejected.data
        assert events.count() == 2
        assert self.client.get(detail_url).data["salle"] is None
        listing = self.client.get(self.url, {"actif": "false"})
        assert listing.status_code == 200, listing.data
        results = listing.data.get("results", listing.data)
        assert [item["id"] for item in results] == [equipment.pk]

        reactivated = self.client.patch(detail_url, {"actif": True}, format="json")
        assert reactivated.status_code == 200, reactivated.data
        assert reactivated.data["salle"] is None
        reassigned = self.client.patch(detail_url, {"salle": self.other_room.pk}, format="json")
        assert reassigned.status_code == 200, reassigned.data
        equipment.refresh_from_db()
        assert equipment.actif is True
        assert equipment.salle_id == self.other_room.pk
        assert events.get(action="reactivation").metadata["apres"]["salle_id"] is None
        assert events.get(action="affectation").metadata["apres"]["salle_id"] == self.other_room.pk
        assert events.get(action="desactivation").metadata["avant"]["salle_id"] == self.room.pk

    def test_inactive_create_and_full_update_require_no_room(self):
        payload = {"identifiant": "INV-INACTIVE", "nom": "Écran", "actif": False}
        rejected = self.client.post(self.url, {**payload, "salle": self.room.pk}, format="json")
        assert rejected.status_code == 400, rejected.data
        assert "salle" in rejected.data
        assert not Equipement.objects.filter(identifiant=payload["identifiant"]).exists()
        created = self.client.post(self.url, payload, format="json")
        assert created.status_code == 201, created.data
        assert created.data["salle"] is None
        detail_url = f"{self.url}{created.data['id']}/"
        for update in (payload, {"identifiant": payload["identifiant"], "nom": "Écran renommé"}):
            rejected = self.client.put(detail_url, {**update, "salle": self.room.pk}, format="json")
            assert rejected.status_code == 400, rejected.data
            assert "salle" in rejected.data
        equipment = Equipement.objects.get(pk=created.data["id"])
        assert equipment.actif is False
        assert equipment.salle_id is None
        reactivated = self.client.patch(
            detail_url, {"actif": True, "salle": self.room.pk}, format="json"
        )
        assert reactivated.status_code == 200, reactivated.data
        equipment.refresh_from_db()
        assert equipment.actif is True
        assert equipment.salle_id == self.room.pk

    def test_failed_lifecycle_audit_rolls_back_deactivation(self):
        equipment = Equipement.objects.create(
            etablissement=self.tenant, identifiant="INV-ROLLBACK", nom="Écran", salle=self.room
        )
        with patch("apps.salles.api.record_workflow_event", side_effect=RuntimeError("Audit indisponible")):
            with self.assertRaises(RuntimeError):
                self.client.patch(f"{self.url}{equipment.pk}/", {"actif": False}, format="json")
        equipment.refresh_from_db()
        assert equipment.actif is True
        assert equipment.salle_id == self.room.pk

    def test_database_rejects_inactive_equipment_with_room(self):
        equipment = Equipement.objects.create(
            etablissement=self.tenant, identifiant="INV-CHECK", nom="Écran", salle=self.room
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Equipement.objects.filter(pk=equipment.pk).update(actif=False)
        equipment.refresh_from_db()
        assert equipment.actif is True
        assert equipment.salle_id == self.room.pk


class IndisponibiliteSalleAPITestCase(TenantAPITestCase):
    url = "/api/v1/salles/indisponibilites/"
    creneaux_url = "/api/v1/edt/creneaux/"

    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            "indispo-admin", etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        self.salle = Salle.objects.create(
            etablissement=self.tenant, code="IND-A", nom="Salle A"
        )
        self.autre_salle = Salle.objects.create(
            etablissement=self.tenant, code="IND-B", nom="Salle B"
        )
        year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-07-01",
        )
        niveau = Niveau.objects.create(
            etablissement=self.tenant, code="6e", libelle="Sixième"
        )
        classe = Classe.objects.create(
            etablissement=self.tenant, niveau=niveau, annee_scolaire=year, nom="6A"
        )
        matiere = Matiere.objects.create(
            etablissement=self.tenant, code="MAT", nom="Maths"
        )
        professeur = Utilisateur.objects.create_user(
            "indispo-prof", role="enseignant", etablissement=self.tenant
        )
        enseignant = Personnel.objects.create(
            user=professeur, matricule="IND-P", date_embauche="2026-01-01"
        )
        self.creneau = {
            "classe": classe.pk, "matiere": matiere.pk, "enseignant": enseignant.pk,
            "salle": self.salle.pk, "jour": 1,
            "heure_debut": "08:00", "heure_fin": "09:00",
        }

    def test_unavailable_days_block_spot_and_recurring_reservations_and_updates(self):
        response = self.client.post(
            self.url,
            {"salle": self.salle.pk, "date_debut": "2026-09-07",
             "date_fin": "2026-09-14", "motif": "Travaux"},
            format="json",
        )
        assert response.status_code == 201, response.data
        for date in ("2026-09-07", "2026-09-14"):
            refused = self.client.post(
                self.creneaux_url, {**self.creneau, "date_specifique": date},
                format="json",
            )
            assert refused.status_code == 400, refused.data
            assert "salle" in refused.data
        refused = self.client.post(self.creneaux_url, self.creneau, format="json")
        assert refused.status_code == 400, refused.data
        assert "salle" in refused.data
        outside = self.client.post(
            self.creneaux_url,
            {**self.creneau, "date_specifique": "2026-09-21"},
            format="json",
        )
        assert outside.status_code == 201, outside.data
        inactive = self.client.post(
            self.creneaux_url, {**self.creneau, "actif": False}, format="json"
        )
        assert inactive.status_code == 201, inactive.data
        assert self.client.patch(
            f"{self.creneaux_url}{outside.data['id']}/",
            {"date_specifique": "2026-09-07"}, format="json",
        ).status_code == 400
        assert self.client.patch(
            f"{self.creneaux_url}{outside.data['id']}/",
            {"salle": self.autre_salle.pk}, format="json",
        ).status_code == 200
        assert self.client.patch(
            f"{self.creneaux_url}{outside.data['id']}/",
            {"salle": self.salle.pk, "date_specifique": "2026-09-14"}, format="json",
        ).status_code == 400
        assert Creneau.objects.filter(salle=self.salle, actif=True).count() == 0

    def test_unavailability_cannot_overlap_existing_reservation_on_create_or_update(self):
        reservation = self.client.post(
            self.creneaux_url,
            {**self.creneau, "date_specifique": "2026-09-07"}, format="json",
        )
        assert reservation.status_code == 201, reservation.data
        refused = self.client.post(
            self.url,
            {"salle": self.salle.pk, "date_debut": "2026-09-07",
             "date_fin": "2026-09-07"}, format="json",
        )
        assert refused.status_code == 400, refused.data
        assert "date_debut" in refused.data
        allowed = self.client.post(
            self.url,
            {"salle": self.salle.pk, "date_debut": "2026-09-08",
             "date_fin": "2026-09-08"}, format="json",
        )
        assert allowed.status_code == 201, allowed.data
        detail = f"{self.url}{allowed.data['id']}/"
        assert self.client.patch(
            detail, {"date_debut": "2026-09-07"}, format="json"
        ).status_code == 400
        assert self.client.get(detail).data["date_debut"] == "2026-09-08"
        assert self.client.patch(
            detail, {"date_fin": "2026-09-06"}, format="json"
        ).status_code == 400
        assert IndisponibiliteSalle.objects.count() == 1

    def test_permissions_and_foreign_rooms_are_isolated(self):
        foreign = type(self.tenant)(schema_name="foreign_indisponibilites")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_room = Salle.objects.create(
            etablissement=foreign, code="FOREIGN", nom="Salle étrangère"
        )
        foreign_period = IndisponibiliteSalle.objects.create(
            salle=foreign_room, date_debut="2026-09-07", date_fin="2026-09-07"
        )
        foreign_year = AnneeScolaire.objects.create(
            etablissement=foreign, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-07-01",
        )
        foreign_level = Niveau.objects.create(
            etablissement=foreign, code="5e", libelle="Cinquième"
        )
        foreign_class = Classe.objects.create(
            etablissement=foreign, niveau=foreign_level,
            annee_scolaire=foreign_year, nom="Classe étrangère",
        )
        foreign_teacher = Utilisateur.objects.create_user(
            "indispo-foreign-teacher", role="enseignant", etablissement=foreign
        )
        foreign_personnel = Personnel.objects.create(
            user=foreign_teacher, matricule="IND-FOREIGN", date_embauche="2026-01-01"
        )
        assert self.client.get(
            f"{self.creneaux_url}par_classe/", {"classe_id": self.creneau["classe"]}
        ).status_code == 200
        assert self.client.get(
            f"{self.creneaux_url}par_enseignant/", {"enseignant_id": self.creneau["enseignant"]}
        ).status_code == 200
        assert self.client.get(f"/api/v1/salles/{foreign_room.pk}/").status_code == 404
        assert self.client.get(f"{self.url}{foreign_period.pk}/").status_code == 404
        assert self.client.post(
            self.url, {"salle": foreign_room.pk, "date_debut": "2026-09-07",
                       "date_fin": "2026-09-07"}, format="json",
        ).status_code == 400
        assert self.client.post(
            self.creneaux_url, {**self.creneau, "salle": foreign_room.pk},
            format="json",
        ).status_code == 400
        assert self.client.get(
            f"{self.creneaux_url}par_salle/", {"salle_id": foreign_room.pk}
        ).status_code == 404
        assert self.client.get(
            f"{self.creneaux_url}par_classe/", {"classe_id": foreign_class.pk}
        ).status_code == 404
        assert self.client.get(
            f"{self.creneaux_url}par_enseignant/", {"enseignant_id": foreign_personnel.pk}
        ).status_code == 404
        reader = Utilisateur.objects.create_user(
            "indispo-reader", role="eleve", etablissement=self.tenant
        )
        self.client.force_authenticate(reader)
        assert self.client.get(self.url).status_code == 200
        assert self.client.post(
            self.url, {"salle": self.salle.pk, "date_debut": "2026-09-07",
                       "date_fin": "2026-09-07"}, format="json",
        ).status_code == 403
        foreign_admin = Utilisateur.objects.create_superuser(
            "indispo-foreign-admin", etablissement=foreign
        )
        self.client.force_authenticate(foreign_admin)
        assert self.client.get(self.url).status_code == 403

    def test_weekly_reservation_only_blocks_dates_in_its_school_year_and_weekday(self):
        response = self.client.post(
            self.creneaux_url, {**self.creneau, "semaine": 2}, format="json"
        )
        assert response.status_code == 201, response.data
        for start, end, expected in (
            ("2026-09-07", "2026-09-07", 400),
            ("2026-09-08", "2026-09-13", 201),
            ("2027-07-02", "2027-07-09", 201),
        ):
            result = self.client.post(
                self.url, {"salle": self.salle.pk, "date_debut": start,
                           "date_fin": end}, format="json",
            )
            assert result.status_code == expected, result.data
