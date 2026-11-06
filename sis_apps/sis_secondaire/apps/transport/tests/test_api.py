"""API tests for transport."""

from datetime import datetime
from uuid import uuid4

import pytest
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.transport.models import Arret, Chauffeur, InscriptionTransport, LigneTransport, TrajetScolaire, Vehicule
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.db import IntegrityError, connection, transaction
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context


class TransportAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `transport` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/transport/lignes-transport/").url_name == "ligne-transport-list"
        assert resolve("/api/v1/transport/arrets/").url_name == "arret-list"
        assert resolve("/api/v1/transport/vehicules/").url_name == "vehicule-list"
        assert resolve("/api/v1/transport/chauffeurs/").url_name == "chauffeur-list"
        assert resolve("/api/v1/transport/trajets-scolaires/").url_name == "trajet-scolaire-list"
        assert resolve("/api/v1/transport/inscriptions-transport/").url_name == "inscription-transport-list"


class TransportTripTestCase(TenantAPITestCase):
    url = "/api/v1/transport/trajets-scolaires/"

    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            "trip-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        self.line = LigneTransport.objects.create(nom="Ligne A", itineraire="A-B")
        self.other_line = LigneTransport.objects.create(nom="Ligne B", itineraire="C-D")
        self.vehicle = Vehicule.objects.create(
            immatriculation="TRIP-A", ligne=self.line, capacite=20, chauffeur="Conducteur"
        )
        self.other_vehicle = Vehicule.objects.create(
            immatriculation="TRIP-B", ligne=self.other_line, capacite=20, chauffeur="Conducteur"
        )

    def payload(
        self, *, vehicle=None, line=None,
        start="2026-11-09T08:00:00+01:00", end="2026-11-09T09:00:00+01:00",
    ):
        return {
            "ligne": (line or self.line).pk,
            "vehicule": (vehicle or self.vehicle).pk,
            "depart_at": start,
            "arrivee_at": end,
        }

    def test_vehicle_cannot_be_double_booked_across_lines_but_adjacent_trips_are_allowed(self):
        first = self.client.post(self.url, self.payload(), format="json")
        assert first.status_code == 201, first.data
        overlap = self.client.post(
            self.url,
            self.payload(line=self.other_line, start="2026-11-09T08:30:00+01:00",
                         end="2026-11-09T09:30:00+01:00"),
            format="json",
        )
        assert overlap.status_code == 400, overlap.data
        assert "vehicule" in overlap.data
        assert TrajetScolaire.objects.count() == 1

        adjacent = self.client.post(
            self.url,
            self.payload(start="2026-11-09T09:00:00+01:00", end="2026-11-09T10:00:00+01:00"),
            format="json",
        )
        other_vehicle = self.client.post(
            self.url,
            self.payload(vehicle=self.other_vehicle, start="2026-11-09T08:30:00+01:00",
                         end="2026-11-09T09:30:00+01:00"),
            format="json",
        )
        next_day = self.client.post(
            self.url,
            self.payload(start="2026-11-10T08:00:00+01:00", end="2026-11-10T09:00:00+01:00"),
            format="json",
        )
        assert adjacent.status_code == other_vehicle.status_code == next_day.status_code == 201
        assert self.client.get(f"{self.url}{first.data['id']}/").status_code == 200

        move = self.client.patch(
            f"{self.url}{adjacent.data['id']}/",
            {"depart_at": "2026-11-09T08:45:00+01:00"}, format="json",
        )
        assert move.status_code == 400, move.data
        assert "vehicule" in move.data
        assert TrajetScolaire.objects.get(pk=adjacent.data["id"]).depart_at == datetime.fromisoformat(
            "2026-11-09T09:00:00+01:00"
        )

    def test_invalid_times_and_direct_database_overlap_are_rejected(self):
        invalid = self.client.post(
            self.url,
            self.payload(end="2026-11-09T08:00:00+01:00"), format="json",
        )
        assert invalid.status_code == 400, invalid.data
        assert "arrivee_at" in invalid.data

        first = self.client.post(self.url, self.payload(), format="json")
        assert first.status_code == 201, first.data
        with pytest.raises(IntegrityError), transaction.atomic():
            TrajetScolaire.objects.create(
                ligne=self.other_line, vehicule=self.vehicle,
                depart_at="2026-11-09T08:59:00+01:00",
                arrivee_at="2026-11-09T10:00:00+01:00",
            )
        with pytest.raises(IntegrityError), transaction.atomic():
            TrajetScolaire.objects.create(
                ligne=self.line, vehicule=self.other_vehicle,
                depart_at="2026-11-09T10:00:00+01:00",
                arrivee_at="2026-11-09T10:00:00+01:00",
            )
        assert TrajetScolaire.objects.count() == 1

    def test_write_requires_existing_transport_permission(self):
        pupil = Utilisateur.objects.create_user(
            "trip-pupil", role="eleve", etablissement=self.tenant
        )
        self.client.force_authenticate(pupil)
        assert self.client.get(self.url).status_code == 200
        denied = self.client.post(self.url, self.payload(), format="json")
        assert denied.status_code == 403
        assert TrajetScolaire.objects.count() == 0

    def test_legacy_text_and_undated_stops_do_not_create_driver_identities(self):
        stop = Arret.objects.create(ligne=self.line, nom="École", heure_passage="08:00", ordre=1)
        first = self.client.post(self.url, self.payload(), format="json")
        second = self.client.post(
            self.url, {**self.payload(vehicle=self.other_vehicle), "chauffeur": None}, format="json"
        )
        assert first.status_code == second.status_code == 201, (first.data, second.data)
        assert first.data["chauffeur"] is None
        assert second.data["chauffeur"] is None
        updated = self.client.patch(
            f"{self.url}{first.data['id']}/", {"ligne": self.other_line.pk}, format="json"
        )
        assert updated.status_code == 200, updated.data
        assert updated.data["chauffeur"] is None
        assert not Chauffeur.objects.exists()
        assert TrajetScolaire.objects.filter(chauffeur__isnull=True).count() == 2
        self.vehicle.refresh_from_db()
        self.other_vehicle.refresh_from_db()
        stop.refresh_from_db()
        assert self.vehicle.chauffeur == self.other_vehicle.chauffeur == "Conducteur"
        assert self.vehicle.ligne_id == self.line.pk
        assert stop.heure_passage.isoformat() == "08:00:00"

    def test_foreign_account_cannot_read_or_manage_local_trips(self):
        created = self.client.post(self.url, self.payload(), format="json")
        assert created.status_code == 201, created.data
        foreign = type(self.tenant)(schema_name="foreign_trip_account")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        visitor = Utilisateur.objects.create_superuser(
            "trip-foreign-account", role="super_admin", etablissement=foreign
        )
        self.client.force_authenticate(visitor)
        assert self.client.get(self.url).status_code == 403
        assert self.client.get(f"{self.url}{created.data['id']}/").status_code == 403
        assert self.client.post(self.url, self.payload(), format="json").status_code == 403
        assert TrajetScolaire.objects.count() == 1


class TransportDriverTestCase(TenantAPITestCase):
    drivers_url = "/api/v1/transport/chauffeurs/"
    trips_url = "/api/v1/transport/trajets-scolaires/"

    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            "driver-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        self.line = LigneTransport.objects.create(nom="Ligne A", itineraire="A-B")
        self.other_line = LigneTransport.objects.create(nom="Ligne B", itineraire="C-D")
        self.vehicle = Vehicule.objects.create(immatriculation="DRIVER-A", chauffeur="Libellé historique")
        self.other_vehicle = Vehicule.objects.create(immatriculation="DRIVER-B", chauffeur="Libellé historique")
        self.driver = Chauffeur.objects.create(nom="Conducteur homonyme")
        self.other_driver = Chauffeur.objects.create(nom="Conducteur homonyme")

    def payload(
        self, *, driver=None, vehicle=None, line=None,
        start="2026-11-09T08:00:00+01:00", end="2026-11-09T09:00:00+01:00",
    ):
        return {
            "ligne": (line or self.line).pk,
            "vehicule": (vehicle or self.vehicle).pk,
            "chauffeur": (driver or self.driver).pk,
            "depart_at": start,
            "arrivee_at": end,
        }

    def test_driver_crud_uses_existing_module_permission(self):
        manager = Utilisateur.objects.create_user(
            "driver-manager", role="eleve", etablissement=self.tenant
        )
        manager.user_permissions.add(
            Permission.objects.get(content_type__app_label="transport", codename="change_lignetransport")
        )
        self.client.force_authenticate(manager)
        created = self.client.post(
            self.drivers_url, {"nom": "Nouveau conducteur", "telephone": "0102030405"}, format="json"
        )
        assert created.status_code == 201, created.data
        detail_url = f"{self.drivers_url}{created.data['id']}/"
        assert self.client.get(self.drivers_url).status_code == 200
        detail = self.client.get(detail_url)
        assert detail.status_code == 200, detail.data
        assert detail.data["telephone"] == "0102030405"
        updated = self.client.patch(detail_url, {"nom": "Nom corrigé"}, format="json")
        assert updated.status_code == 200, updated.data
        assert Chauffeur.objects.get(pk=created.data["id"]).nom == "Nom corrigé"
        assert self.client.delete(detail_url).status_code == 204
        assert not Chauffeur.objects.filter(pk=created.data["id"]).exists()

    def test_driver_directory_allows_granted_readers_without_write_access_and_legacy_managers(self):
        self.driver.telephone = "0102030405"
        self.driver.save(update_fields=["telephone"])
        detail_url = f"{self.drivers_url}{self.driver.pk}/"
        reader = Utilisateur.objects.create_user(
            "driver-reader", role="eleve", etablissement=self.tenant
        )
        reader.user_permissions.add(
            Permission.objects.get(content_type__app_label="transport", codename="view_chauffeur")
        )
        self.client.force_authenticate(reader)
        listed = self.client.get(self.drivers_url)
        assert listed.status_code == 200, listed.data
        detail = self.client.get(detail_url)
        assert detail.status_code == 200, detail.data
        assert detail.data["telephone"] == "0102030405"
        assert self.client.post(self.drivers_url, {"nom": "Interdit"}, format="json").status_code == 403
        assert self.client.patch(detail_url, {"nom": "Interdit"}, format="json").status_code == 403
        assert self.client.delete(detail_url).status_code == 403
        assert Chauffeur.objects.count() == 2
        self.driver.refresh_from_db()
        assert self.driver.nom == "Conducteur homonyme"

        manager = Utilisateur.objects.create_user(
            "driver-legacy-manager", role="intendance", etablissement=self.tenant
        )
        self.client.force_authenticate(manager)
        assert self.client.get(self.drivers_url).status_code == 200
        assert self.client.get(detail_url).status_code == 200

    def test_same_driver_cannot_overlap_across_vehicles_but_boundaries_and_homonyms_are_allowed(self):
        first = self.client.post(self.trips_url, self.payload(), format="json")
        assert first.status_code == 201, first.data
        for start, end in (("08:30", "09:30"), ("08:15", "08:45"), ("07:30", "09:30"), ("08:00", "09:00")):
            rejected = self.client.post(
                self.trips_url,
                self.payload(
                    vehicle=self.other_vehicle, line=self.other_line,
                    start=f"2026-11-09T{start}:00+01:00", end=f"2026-11-09T{end}:00+01:00",
                ),
                format="json",
            )
            assert rejected.status_code == 400, rejected.data
            assert "chauffeur" in rejected.data
            assert TrajetScolaire.objects.count() == 1

        for start, end in (("07:00", "08:00"), ("09:00", "10:00")):
            adjacent = self.client.post(
                self.trips_url,
                self.payload(
                    vehicle=self.other_vehicle, start=f"2026-11-09T{start}:00+01:00",
                    end=f"2026-11-09T{end}:00+01:00",
                ),
                format="json",
            )
            assert adjacent.status_code == 201, adjacent.data
        homonym = self.client.post(
            self.trips_url, self.payload(driver=self.other_driver, vehicle=self.other_vehicle), format="json"
        )
        assert homonym.status_code == 201, homonym.data
        next_day = self.client.post(
            self.trips_url,
            self.payload(start="2026-11-10T08:00:00+01:00", end="2026-11-10T09:00:00+01:00"),
            format="json",
        )
        assert next_day.status_code == 201, next_day.data
        assert TrajetScolaire.objects.count() == 5

    def test_partial_updates_check_driver_and_times_without_conflicting_with_self(self):
        first = self.client.post(self.trips_url, self.payload(), format="json")
        second = self.client.post(
            self.trips_url, self.payload(driver=self.other_driver, vehicle=self.other_vehicle), format="json"
        )
        assert first.status_code == second.status_code == 201, (first.data, second.data)
        second_url = f"{self.trips_url}{second.data['id']}/"
        reassignment = self.client.patch(second_url, {"chauffeur": self.driver.pk}, format="json")
        assert reassignment.status_code == 400, reassignment.data
        assert "chauffeur" in reassignment.data
        assert TrajetScolaire.objects.get(pk=second.data["id"]).chauffeur_id == self.other_driver.pk

        unchanged = self.client.patch(
            f"{self.trips_url}{first.data['id']}/", {"ligne": self.other_line.pk}, format="json"
        )
        assert unchanged.status_code == 200, unchanged.data
        moved = self.client.patch(
            second_url,
            {"chauffeur": self.driver.pk, "depart_at": "2026-11-09T09:00:00+01:00",
             "arrivee_at": "2026-11-09T10:00:00+01:00"},
            format="json",
        )
        assert moved.status_code == 200, moved.data
        conflict = self.client.patch(
            second_url, {"depart_at": "2026-11-09T08:30:00+01:00"}, format="json"
        )
        assert conflict.status_code == 400, conflict.data
        assert "chauffeur" in conflict.data
        trip = TrajetScolaire.objects.get(pk=second.data["id"])
        assert trip.chauffeur_id == self.driver.pk
        assert trip.depart_at == datetime.fromisoformat("2026-11-09T09:00:00+01:00")

    def test_database_enforces_driver_exclusion_on_insert_and_update(self):
        TrajetScolaire.objects.create(
            ligne=self.line, vehicule=self.vehicle, chauffeur=self.driver,
            depart_at="2026-11-09T08:00:00+01:00", arrivee_at="2026-11-09T09:00:00+01:00",
        )
        with pytest.raises(IntegrityError) as error, transaction.atomic():
            TrajetScolaire.objects.create(
                ligne=self.other_line, vehicule=self.other_vehicle, chauffeur=self.driver,
                depart_at="2026-11-09T08:30:00+01:00", arrivee_at="2026-11-09T09:30:00+01:00",
            )
        assert error.value.__cause__.diag.constraint_name == "transport_trajet_driver_no_overlap"
        adjacent = TrajetScolaire.objects.create(
            ligne=self.other_line, vehicule=self.other_vehicle, chauffeur=self.driver,
            depart_at="2026-11-09T09:00:00+01:00", arrivee_at="2026-11-09T10:00:00+01:00",
        )
        with pytest.raises(IntegrityError) as error, transaction.atomic():
            TrajetScolaire.objects.filter(pk=adjacent.pk).update(depart_at="2026-11-09T08:30:00+01:00")
        assert error.value.__cause__.diag.constraint_name == "transport_trajet_driver_no_overlap"
        adjacent.refresh_from_db()
        assert adjacent.depart_at == datetime.fromisoformat("2026-11-09T09:00:00+01:00")

    def test_referenced_driver_cannot_be_deleted_and_assignment_can_be_explicitly_cleared(self):
        created = self.client.post(self.trips_url, self.payload(), format="json")
        assert created.status_code == 201, created.data
        driver_url = f"{self.drivers_url}{self.driver.pk}/"
        renamed = self.client.patch(driver_url, {"nom": "Nom modifié"}, format="json")
        assert renamed.status_code == 200, renamed.data
        assert TrajetScolaire.objects.get(pk=created.data["id"]).chauffeur_id == self.driver.pk
        blocked = self.client.delete(driver_url)
        assert blocked.status_code == 400, blocked.data
        assert "chauffeur" in blocked.data
        assert Chauffeur.objects.filter(pk=self.driver.pk).exists()
        cleared = self.client.patch(
            f"{self.trips_url}{created.data['id']}/", {"chauffeur": None}, format="json"
        )
        assert cleared.status_code == 200, cleared.data
        assert TrajetScolaire.objects.get(pk=created.data["id"]).chauffeur_id is None
        assert self.client.delete(driver_url).status_code == 204
        self.vehicle.refresh_from_db()
        assert self.vehicle.chauffeur == "Libellé historique"

    def test_driver_directory_requires_permission_and_foreign_accounts_are_denied(self):
        detail_url = f"{self.drivers_url}{self.driver.pk}/"
        self.client.force_authenticate(user=None)
        assert self.client.get(self.drivers_url).status_code in (401, 403)
        pupil = Utilisateur.objects.create_user(
            "driver-pupil", role="eleve", etablissement=self.tenant
        )
        self.client.force_authenticate(pupil)
        assert self.client.get(self.drivers_url).status_code == 403
        assert self.client.get(detail_url).status_code == 403
        assert self.client.head(self.drivers_url).status_code == 403
        assert self.client.options(detail_url).status_code == 403
        assert self.client.post(self.drivers_url, {"nom": "Interdit"}, format="json").status_code == 403
        assert self.client.patch(detail_url, {"nom": "Interdit"}, format="json").status_code == 403
        assert self.client.delete(detail_url).status_code == 403

        foreign = type(self.tenant)(schema_name="foreign_driver_account")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        visitor = Utilisateur.objects.create_superuser(
            "driver-foreign", role="super_admin", etablissement=foreign
        )
        self.client.force_authenticate(visitor)
        assert self.client.get(self.drivers_url).status_code == 403
        assert self.client.get(detail_url).status_code == 403
        assert self.client.post(self.drivers_url, {"nom": "Interdit"}, format="json").status_code == 403
        assert self.client.patch(detail_url, {"nom": "Interdit"}, format="json").status_code == 403
        assert self.client.delete(detail_url).status_code == 403
        assert self.client.post(self.trips_url, self.payload(), format="json").status_code == 403
        assert Chauffeur.objects.count() == 2
        assert not TrajetScolaire.objects.exists()

    def test_driver_records_in_another_schema_cannot_be_read_modified_or_assigned(self):
        foreign_schema = f"transport_driver_{uuid4().hex}"
        quoted_schema = connection.ops.quote_name(foreign_schema)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA {quoted_schema}")
        try:
            with schema_context(foreign_schema):
                with connection.schema_editor() as editor:
                    editor.create_model(Chauffeur)
                foreign_driver = Chauffeur.objects.create(pk=self.driver.pk + 100000, nom="Autre établissement")
            detail_url = f"{self.drivers_url}{foreign_driver.pk}/"
            assert self.client.get(detail_url).status_code == 404
            assert self.client.patch(detail_url, {"nom": "Interdit"}, format="json").status_code == 404
            assert self.client.delete(detail_url).status_code == 404
            listed = self.client.get(self.drivers_url)
            assert listed.status_code == 200, listed.data
            results = listed.data["results"] if isinstance(listed.data, dict) else listed.data
            assert {driver["id"] for driver in results} == {self.driver.pk, self.other_driver.pk}
            rejected = self.client.post(
                self.trips_url, self.payload(driver=foreign_driver), format="json"
            )
            assert rejected.status_code == 400, rejected.data
            assert "chauffeur" in rejected.data
            created = self.client.post(self.trips_url, self.payload(), format="json")
            assert created.status_code == 201, created.data
            rejected_update = self.client.patch(
                f"{self.trips_url}{created.data['id']}/", {"chauffeur": foreign_driver.pk}, format="json"
            )
            assert rejected_update.status_code == 400, rejected_update.data
            assert "chauffeur" in rejected_update.data
            assert TrajetScolaire.objects.get(pk=created.data["id"]).chauffeur_id == self.driver.pk
            with schema_context(foreign_schema):
                foreign_driver.refresh_from_db()
                assert foreign_driver.nom == "Autre établissement"
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA {quoted_schema} CASCADE")


class TransportCapacityTestCase(TenantAPITestCase):
    def setUp(self):
        admin = Utilisateur.objects.create_superuser(
            "transport-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        self.year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut="2026-09-01",
            date_fin="2027-07-01",
        )
        self.next_year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2027-2028",
            date_debut="2027-09-01",
            date_fin="2028-07-01",
        )
        self.line = LigneTransport.objects.create(nom="Ligne A", itineraire="A-B")
        self.other_line = LigneTransport.objects.create(nom="Ligne B", itineraire="C-D")
        self.stops = {}
        for line in (self.line, self.other_line):
            self.stops[line.pk] = [
                Arret.objects.create(ligne=line, nom=name, heure_passage="08:00", ordre=order)
                for order, name in enumerate(("Départ", "Arrivée"), start=1)
            ]
        Vehicule.objects.create(immatriculation="TRANSPORT-A", ligne=self.line, capacite=1)
        Vehicule.objects.create(immatriculation="TRANSPORT-B", ligne=self.other_line, capacite=1)
        self.pupils = []
        for number in range(1, 4):
            user = Utilisateur.objects.create_user(
                f"transport-pupil-{number}", role="eleve", etablissement=self.tenant
            )
            self.pupils.append(
                Eleve.objects.create(
                    etablissement=self.tenant,
                    user=user,
                    matricule=f"TRANS-{number}",
                    date_naissance="2010-01-01",
                    lieu_naissance="Paris",
                    sexe="F",
                    date_inscription="2026-09-01",
                )
            )
        self.url = "/api/v1/transport/inscriptions-transport/"

    def payload(self, pupil, line=None, year=None):
        line = line or self.line
        stops = self.stops[line.pk]
        return {
            "eleve": pupil.pk,
            "ligne": line.pk,
            "arret_montee": stops[0].pk,
            "arret_descente": stops[1].pk,
            "annee_scolaire": (year or self.year).pk,
        }

    def test_capacity_is_released_on_cancellation_but_not_overbooked_on_reactivation(self):
        first = self.client.post(self.url, self.payload(self.pupils[0]), format="json")
        assert first.status_code == 201, first.data

        rejected = self.client.post(self.url, self.payload(self.pupils[1]), format="json")
        assert rejected.status_code == 400, rejected.data
        assert "ligne" in rejected.data
        assert InscriptionTransport.objects.filter(ligne=self.line, actif=True).count() == 1

        first_url = f"{self.url}{first.data['id']}/"
        cancelled = self.client.patch(first_url, {"actif": False}, format="json")
        assert cancelled.status_code == 200, cancelled.data
        second = self.client.post(self.url, self.payload(self.pupils[1]), format="json")
        assert second.status_code == 201, second.data

        reactivation = self.client.patch(first_url, {"actif": True}, format="json")
        assert reactivation.status_code == 400, reactivation.data
        assert "ligne" in reactivation.data
        assert not InscriptionTransport.objects.get(pk=first.data["id"]).actif

    def test_line_transfer_checks_destination_and_other_year_has_its_own_seats(self):
        first = self.client.post(self.url, self.payload(self.pupils[0]), format="json")
        second = self.client.post(
            self.url, self.payload(self.pupils[1], self.other_line), format="json"
        )
        assert first.status_code == second.status_code == 201, (first.data, second.data)

        move = self.client.patch(
            f"{self.url}{second.data['id']}/",
            {
                "ligne": self.line.pk,
                "arret_montee": self.stops[self.line.pk][0].pk,
                "arret_descente": self.stops[self.line.pk][1].pk,
            },
            format="json",
        )
        assert move.status_code == 400, move.data
        assert "ligne" in move.data
        assert InscriptionTransport.objects.get(pk=second.data["id"]).ligne_id == self.other_line.pk

        other_year = self.client.post(
            self.url, self.payload(self.pupils[2], year=self.next_year), format="json"
        )
        assert other_year.status_code == 201, other_year.data
        assert InscriptionTransport.objects.filter(ligne=self.line, actif=True).count() == 2
