"""API tests for clubs."""

import uuid

from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.clubs.models import Club, MembreClub
from apps.eleves.models import Eleve
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur


class ClubsAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `clubs` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/clubs/").url_name == "club-list"
        assert resolve("/api/v1/clubs/membres-clubs/").url_name == "membre-club-list"
        assert resolve("/api/v1/clubs/activites-clubs/").url_name == "seance-club-list"


class ClubCapacityAPITestCase(TenantAPITestCase):
    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            "clubs-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        self.club = Club.objects.create(
            nom="Échecs", type="culturel", description="Club d'échecs",
            responsable=self.admin, horaires="Mercredi 14h", capacite=1,
            date_creation=timezone.localdate(),
        )

    def pupil(self, username):
        user = Utilisateur.objects.create_user(username, role="eleve", etablissement=self.tenant)
        return Eleve.objects.create(
            etablissement=self.tenant, user=user, matricule=f"CLUB-{username}",
            date_naissance="2008-01-01", lieu_naissance="Paris", sexe="F",
            date_inscription=timezone.localdate(),
        )

    def test_post_cannot_admit_member_beyond_capacity(self):
        first, second = self.pupil("first"), self.pupil("second")
        url = "/api/v1/clubs/membres-clubs/"
        response = self.client.post(url, {"club": self.club.pk, "eleve": first.pk}, secure=True)
        assert response.status_code == 201, response.data

        response = self.client.post(url, {"club": self.club.pk, "eleve": second.pk}, secure=True)
        assert response.status_code == 400, response.data
        assert not MembreClub.objects.filter(club=self.club, eleve=second).exists()

    def test_reactivation_cannot_bypass_capacity_via_action_or_patch(self):
        first, second = self.pupil("first"), self.pupil("second")
        MembreClub.objects.create(club=self.club, eleve=first)
        inactive = MembreClub.objects.create(club=self.club, eleve=second, statut="inactif")
        url = f"/api/v1/clubs/membres-clubs/{inactive.pk}/"

        response = self.client.post(f"{url}reactiver/", secure=True)
        assert response.status_code == 400, response.data
        response = self.client.patch(url, {"statut": "actif"}, secure=True)
        assert response.status_code == 400, response.data
        inactive.refresh_from_db()
        assert inactive.statut == "inactif"

        MembreClub.objects.filter(club=self.club, eleve=first).update(statut="suspendu")
        response = self.client.post(f"{url}reactiver/", secure=True)
        assert response.status_code == 200, response.data
        inactive.refresh_from_db()
        assert inactive.statut == "actif"

    def test_patch_cannot_move_active_member_into_full_club(self):
        occupant, moving = self.pupil("occupant"), self.pupil("moving")
        MembreClub.objects.create(club=self.club, eleve=occupant)
        other = Club.objects.create(
            nom="Lecture", type="culturel", description="Club de lecture",
            responsable=self.admin, horaires="Jeudi 14h", capacite=1,
            date_creation=timezone.localdate(),
        )
        member = MembreClub.objects.create(club=other, eleve=moving)

        response = self.client.patch(
            f"/api/v1/clubs/membres-clubs/{member.pk}/",
            {"club": self.club.pk}, secure=True,
        )
        assert response.status_code == 400, response.data
        member.refresh_from_db()
        assert member.club_id == other.pk

    def test_patch_cannot_lower_capacity_below_active_members(self):
        self.club.capacite = 2
        self.club.save(update_fields=["capacite"])
        for username in ("first", "second"):
            MembreClub.objects.create(club=self.club, eleve=self.pupil(username))
        url = f"/api/v1/clubs/{self.club.pk}/"

        response = self.client.patch(url, {"capacite": 1}, secure=True)
        assert response.status_code == 400, response.data
        self.club.refresh_from_db()
        assert self.club.capacite == 2

        response = self.client.patch(url, {"capacite": 3}, secure=True)
        assert response.status_code == 200, response.data
        response = self.client.patch(url, {"capacite": 2}, secure=True)
        assert response.status_code == 200, response.data
        self.club.refresh_from_db()
        assert self.club.capacite == 2

    def test_foreign_school_superuser_cannot_read_or_manage_club_members(self):
        local_pupil = self.pupil("local")
        other_pupil = self.pupil("other")
        members_url = "/api/v1/clubs/membres-clubs/"
        created = self.client.post(
            members_url, {"club": self.club.pk, "eleve": local_pupil.pk}, secure=True
        )
        assert created.status_code == 201, created.data
        assert self.client.get(f"{members_url}{created.data['id']}/", secure=True).status_code == 200

        foreign = type(self.tenant)(schema_name=f"foreign_clubs_{uuid.uuid4().hex[:12]}")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        visitor = Utilisateur.objects.create_superuser(
            "foreign-clubs-admin", role="super_admin", etablissement=foreign
        )
        self.client.force_authenticate(visitor)

        assert self.client.get(members_url, secure=True).status_code == 403
        assert self.client.get(f"{members_url}{created.data['id']}/", secure=True).status_code == 403
        assert self.client.post(
            members_url, {"club": self.club.pk, "eleve": other_pupil.pk}, secure=True
        ).status_code == 403
        assert not MembreClub.objects.filter(club=self.club, eleve=other_pupil).exists()
