"""API tests for transport."""

from datetime import datetime

import pytest
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.transport.models import Arret, InscriptionTransport, LigneTransport, TrajetScolaire, Vehicule
from apps.utilisateurs.models import Utilisateur
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context


class TransportAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `transport` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/transport/lignes-transport/").url_name == "ligne-transport-list"
        assert resolve("/api/v1/transport/arrets/").url_name == "arret-list"
        assert resolve("/api/v1/transport/vehicules/").url_name == "vehicule-list"
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
