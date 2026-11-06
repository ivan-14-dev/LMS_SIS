"""API tests for cantine."""

from apps.cantine.models import InscriptionCantine, Menu, PresenceCantine
from apps.eleves.models import Eleve
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context


class CantineAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `cantine` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/cantine/menus/").url_name == "menu-list"
        assert resolve("/api/v1/cantine/inscriptions-cantine/").url_name == "inscription-cantine-list"
        assert resolve("/api/v1/cantine/presences-cantine/").url_name == "presence-cantine-list"


class CantinePointageTestCase(TenantAPITestCase):
    def setUp(self):
        admin = Utilisateur.objects.create_superuser(
            "cantine-admin", role="super_admin", etablissement=self.tenant
        )
        self.admin = admin
        self.client.force_authenticate(admin)
        pupil = Utilisateur.objects.create_user(
            "cantine-pupil", role="eleve", etablissement=self.tenant
        )
        self.eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=pupil,
            matricule="CANT-1",
            date_naissance="2010-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )
        response = self.client.post(
            "/api/v1/cantine/menus/",
            {"date": "2026-10-12", "plat": "Repas", "regime": "standard"},
            format="json",
        )
        assert response.status_code == 201, response.data
        self.menu_id = response.data["id"]
        response = self.client.post(
            "/api/v1/cantine/inscriptions-cantine/",
            {"eleve": self.eleve.pk, "date_debut": "2026-10-01", "date_fin": "2026-10-31"},
            format="json",
        )
        assert response.status_code == 201, response.data
        self.inscription_url = f"/api/v1/cantine/inscriptions-cantine/{response.data['id']}/"
        self.presences_url = "/api/v1/cantine/presences-cantine/"

    def test_foreign_superuser_cannot_access_local_canteen_records(self):
        local = self.client.patch(
            self.inscription_url, {"allergies": ["arachides"]}, format="json"
        )
        assert local.status_code == 200, local.data
        pupil_user = Utilisateur.objects.create_user(
            "cantine-second-local-pupil", role="eleve", etablissement=self.tenant
        )
        second_pupil = Eleve.objects.create(
            etablissement=self.tenant,
            user=pupil_user,
            matricule="CANT-2",
            date_naissance="2010-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )

        foreign = type(self.tenant)(schema_name="foreign_cantine_admin")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        visitor = Utilisateur.objects.create_superuser(
            "cantine-foreign-admin", role="super_admin", etablissement=foreign
        )
        self.client.force_authenticate(visitor)

        for url in (
            "/api/v1/cantine/menus/",
            f"/api/v1/cantine/menus/{self.menu_id}/",
            "/api/v1/cantine/inscriptions-cantine/",
            self.inscription_url,
            "/api/v1/cantine/inscriptions-cantine/statistiques/",
            self.presences_url,
        ):
            response = self.client.get(url)
            assert response.status_code == 403, (url, response.data)

        new_menu = self.client.post(
            "/api/v1/cantine/menus/",
            {"date": "2026-10-13", "plat": "Repas étranger"},
            format="json",
        )
        assert new_menu.status_code == 403, new_menu.data
        enrolled = self.client.post(
            "/api/v1/cantine/inscriptions-cantine/",
            {"eleve": second_pupil.pk, "date_debut": "2026-10-01"},
            format="json",
        )
        assert enrolled.status_code == 403, enrolled.data
        changed = self.client.patch(self.inscription_url, {"allergies": []}, format="json")
        assert changed.status_code == 403, changed.data
        pointage = self.client.post(
            self.presences_url,
            {"menu": self.menu_id, "eleve": self.eleve.pk, "present": True},
            format="json",
        )
        assert pointage.status_code == 403, pointage.data
        assert not Menu.objects.filter(date="2026-10-13").exists()
        assert not InscriptionCantine.objects.filter(eleve=second_pupil).exists()
        assert not PresenceCantine.objects.filter(eleve=self.eleve).exists()

        self.client.force_authenticate(self.admin)
        own = self.client.get(self.inscription_url)
        assert own.status_code == 200, own.data
        assert own.data["allergies"] == ["arachides"]
        updated = self.client.patch(self.inscription_url, {"forfait": "mensuel"}, format="json")
        assert updated.status_code == 200, updated.data
        assert updated.data["forfait"] == "mensuel"

    def test_cancelled_inscription_cannot_be_marked_present_via_single_or_bulk_api(self):
        cancelled = self.client.patch(self.inscription_url, {"actif": False}, format="json")
        assert cancelled.status_code == 200, cancelled.data

        single = self.client.post(
            self.presences_url, {"menu": self.menu_id, "eleve": self.eleve.pk, "present": True},
            format="json",
        )
        assert single.status_code == 400, single.data
        assert "eleve" in single.data

        bulk = self.client.post(
            f"{self.presences_url}pointage_masse/",
            {"menu_id": self.menu_id, "pointages": [{"eleve_id": self.eleve.pk, "present": True}]},
            format="json",
        )
        assert bulk.status_code == 400, bulk.data
        assert not PresenceCantine.objects.filter(menu_id=self.menu_id, eleve=self.eleve).exists()

    def test_cancellation_prevents_reactivating_a_presence_but_allows_marking_absent(self):
        response = self.client.post(
            self.presences_url, {"menu": self.menu_id, "eleve": self.eleve.pk, "present": True},
            format="json",
        )
        assert response.status_code == 201, response.data
        presence_url = f"{self.presences_url}{response.data['id']}/"
        cancelled = self.client.patch(self.inscription_url, {"actif": False}, format="json")
        assert cancelled.status_code == 200, cancelled.data

        absent = self.client.patch(presence_url, {"present": False}, format="json")
        assert absent.status_code == 200, absent.data
        reactivated = self.client.patch(presence_url, {"present": True}, format="json")
        assert reactivated.status_code == 400, reactivated.data
        assert not PresenceCantine.objects.get(pk=response.data["id"]).present

    def test_pointage_rejects_an_inscription_outside_its_dates(self):
        response = self.client.patch(self.inscription_url, {"date_fin": "2026-10-11"}, format="json")
        assert response.status_code == 200, response.data
        single = self.client.post(
            self.presences_url, {"menu": self.menu_id, "eleve": self.eleve.pk, "present": True},
            format="json",
        )
        assert single.status_code == 400, single.data
        assert not PresenceCantine.objects.filter(menu_id=self.menu_id, eleve=self.eleve).exists()

    def test_active_subscription_allows_pointage_at_both_inclusive_date_boundaries(self):
        for date, use_bulk in (("2026-10-01", False), ("2026-10-31", True)):
            menu = self.client.post(
                "/api/v1/cantine/menus/",
                {"date": date, "plat": "Repas", "regime": "standard"},
                format="json",
            )
            assert menu.status_code == 201, menu.data
            if use_bulk:
                response = self.client.post(
                    f"{self.presences_url}pointage_masse/",
                    {"menu_id": menu.data["id"], "pointages": [{"eleve_id": self.eleve.pk, "present": True}]},
                    format="json",
                )
                assert response.status_code == 200, response.data
            else:
                response = self.client.post(
                    self.presences_url,
                    {"menu": menu.data["id"], "eleve": self.eleve.pk, "present": True},
                    format="json",
                )
                assert response.status_code == 201, response.data
            assert PresenceCantine.objects.get(menu_id=menu.data["id"], eleve=self.eleve).present

        for date, use_bulk in (("2026-09-30", True), ("2026-11-01", False)):
            menu = self.client.post(
                "/api/v1/cantine/menus/",
                {"date": date, "plat": "Repas", "regime": "standard"},
                format="json",
            )
            assert menu.status_code == 201, menu.data
            if use_bulk:
                response = self.client.post(
                    f"{self.presences_url}pointage_masse/",
                    {"menu_id": menu.data["id"], "pointages": [{"eleve_id": self.eleve.pk}]},
                    format="json",
                )
            else:
                response = self.client.post(
                    self.presences_url,
                    {"menu": menu.data["id"], "eleve": self.eleve.pk, "present": True},
                    format="json",
                )
            assert response.status_code == 400, response.data
            assert not PresenceCantine.objects.filter(menu_id=menu.data["id"], eleve=self.eleve).exists()

    def test_foreign_pupil_with_active_subscription_cannot_be_marked_present(self):
        foreign = type(self.tenant)(schema_name="foreign_cantine_pointage")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        user = Utilisateur.objects.create_user(
            "cantine-foreign-pupil", role="eleve", etablissement=foreign
        )
        pupil = Eleve.objects.create(
            etablissement=foreign,
            user=user,
            matricule="CANT-FOREIGN",
            date_naissance="2010-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )
        InscriptionCantine.objects.create(
            eleve=pupil, date_debut="2026-10-01", date_fin="2026-10-31", actif=True
        )

        single = self.client.post(
            self.presences_url, {"menu": self.menu_id, "eleve": pupil.pk, "present": True},
            format="json",
        )
        assert single.status_code == 400, single.data
        assert "eleve" in single.data

        absent = self.client.post(
            self.presences_url, {"menu": self.menu_id, "eleve": pupil.pk, "present": False},
            format="json",
        )
        assert absent.status_code == 400, absent.data
        assert "eleve" in absent.data

        bulk = self.client.post(
            f"{self.presences_url}pointage_masse/",
            {
                "menu_id": self.menu_id,
                "pointages": [
                    {"eleve_id": self.eleve.pk, "present": True},
                    {"eleve_id": pupil.pk, "present": False},
                ],
            },
            format="json",
        )
        assert bulk.status_code == 400, bulk.data
        assert not PresenceCantine.objects.filter(menu_id=self.menu_id).exists()

        absence = PresenceCantine.objects.create(menu_id=self.menu_id, eleve=pupil, present=False)
        own = self.client.post(
            self.presences_url,
            {"menu": self.menu_id, "eleve": self.eleve.pk, "present": True},
            format="json",
        )
        assert own.status_code == 201, own.data
        listing = self.client.get(self.presences_url)
        assert listing.status_code == 200, listing.data
        assert [item["id"] for item in listing.data["results"]] == [own.data["id"]]
        assert self.client.get(f"{self.presences_url}{absence.pk}/").status_code == 404
        menu_presences = self.client.get(f"/api/v1/cantine/menus/{self.menu_id}/presences/")
        assert menu_presences.status_code == 200, menu_presences.data
        assert [item["id"] for item in menu_presences.data] == [own.data["id"]]
        stats = self.client.get(f"/api/v1/cantine/menus/{self.menu_id}/statistiques/")
        assert stats.status_code == 200, stats.data
        assert (stats.data["total_inscrits"], stats.data["presents"], stats.data["absents"]) == (1, 1, 0)

        reactivated = self.client.patch(
            f"{self.presences_url}{absence.pk}/", {"present": True}, format="json"
        )
        assert reactivated.status_code == 404, reactivated.data
        still_absent = self.client.patch(
            f"{self.presences_url}{absence.pk}/", {"present": False}, format="json"
        )
        assert still_absent.status_code == 404, still_absent.data
        absence.refresh_from_db()
        assert not absence.present

    def test_subscriptions_are_scoped_to_the_pupils_establishment(self):
        foreign = type(self.tenant)(schema_name="foreign_cantine_inscription")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        user = Utilisateur.objects.create_user(
            "cantine-foreign-inscription-pupil", role="eleve", etablissement=foreign
        )
        pupil = Eleve.objects.create(
            etablissement=foreign,
            user=user,
            matricule="CANT-FOREIGN-INSCRIPTION",
            date_naissance="2010-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )
        url = "/api/v1/cantine/inscriptions-cantine/"
        rejected = self.client.post(
            url, {"eleve": pupil.pk, "date_debut": "2026-10-01"}, format="json"
        )
        assert rejected.status_code == 400, rejected.data
        assert "eleve" in rejected.data
        reassigned = self.client.patch(self.inscription_url, {"eleve": pupil.pk}, format="json")
        assert reassigned.status_code == 400, reassigned.data
        assert "eleve" in reassigned.data
        assert not InscriptionCantine.objects.filter(eleve=pupil).exists()
        assert InscriptionCantine.objects.get(eleve=self.eleve).eleve_id == self.eleve.pk

        foreign_inscription = InscriptionCantine.objects.create(
            eleve=pupil, date_debut="2026-10-01", forfait="mensuel",
            regime="vegetarien", allergies=["arachides"]
        )
        listing = self.client.get(url)
        assert listing.status_code == 200, listing.data
        assert [item["eleve"] for item in listing.data["results"]] == [self.eleve.pk]
        foreign_url = f"{url}{foreign_inscription.pk}/"
        assert self.client.get(foreign_url).status_code == 404
        assert self.client.patch(foreign_url, {"actif": False}, format="json").status_code == 404
        assert self.client.delete(foreign_url).status_code == 404
        stats = self.client.get(f"{url}statistiques/")
        assert stats.status_code == 200, stats.data
        assert stats.data["total_inscrits"] == 1
        assert stats.data["par_forfait"] == {"annuel": 1}
        assert stats.data["par_regime"] == {"standard": 1}

        own = self.client.get(self.inscription_url)
        assert own.status_code == 200, own.data
        assert own.data["eleve"] == self.eleve.pk
        updated = self.client.patch(self.inscription_url, {"forfait": "trimestriel"}, format="json")
        assert updated.status_code == 200, updated.data
        assert updated.data["forfait"] == "trimestriel"
        foreign_inscription.refresh_from_db()
        assert foreign_inscription.actif
        assert foreign_inscription.allergies == ["arachides"]

    def test_menu_from_another_schema_cannot_be_used_for_pointage(self):
        foreign = type(self.tenant)(schema_name="foreign_cantine_menu")
        self.setup_tenant(foreign)
        with schema_context("public"):
            foreign.save()
        with schema_context(foreign.schema_name):
            foreign_menu = Menu.objects.create(
                pk=self.menu_id + 100000, date="2026-10-12", plat="Menu étranger"
            )
        assert not Menu.objects.filter(pk=foreign_menu.pk).exists()
        assert self.client.get(f"/api/v1/cantine/menus/{foreign_menu.pk}/presences/").status_code == 404

        single = self.client.post(
            self.presences_url,
            {"menu": foreign_menu.pk, "eleve": self.eleve.pk, "present": False},
            format="json",
        )
        assert single.status_code == 400, single.data
        assert "menu" in single.data
        bulk = self.client.post(
            f"{self.presences_url}pointage_masse/",
            {"menu_id": foreign_menu.pk, "pointages": [{"eleve_id": self.eleve.pk, "present": False}]},
            format="json",
        )
        assert bulk.status_code == 404, bulk.data
        assert not PresenceCantine.objects.filter(eleve=self.eleve).exists()
