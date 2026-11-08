"""Library access and circulation regressions, runnable with either SIS settings."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from apps.bibliotheque.models import Emprunt, Exemplaire, Livre, Reservation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from sis_common.library_files import PrivateLibraryStorage

BASE = "/api/v1/bibliotheque/"
PDF = b"%PDF-1.4\nLibrary licensed fixture\n%%EOF\n"


class LibraryFixture(TenantAPITestCase):
    def setUp(self):
        self.enterContext(
            override_settings(
                CACHES={
                    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": uuid4().hex}
                }
            )
        )
        self.users = get_user_model()
        self.reader = self.users.objects.create_user(
            "library-digital-reader",
            role="eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant",
            etablissement=self.tenant,
        )
        self.other = self.users.objects.create_user("library-digital-other", etablissement=self.tenant)
        self.manager = self.users.objects.create_user(
            "library-digital-manager", role="bibliothecaire", etablissement=self.tenant
        )
        self.permissions = {p.codename: p for p in Permission.objects.filter(content_type__app_label="bibliotheque")}
        self.book = Livre.objects.create(titre="Ressource privée", auteurs="Auteur")
        self.copy = Exemplaire.objects.create(livre=self.book, code_barre="DIGITAL-1")
        self.book_url = f"{BASE}livres/{self.book.pk}/"
        self.download_url = f"{self.book_url}numerique/"
        self.return_action = "retourner" if settings.SIS_VARIANT == "secondaire" else "rendre"
        self.reservations = "reservations" if settings.SIS_VARIANT == "secondaire" else "reservations-bibliotheque"

    def grant(self, user, *codenames):
        user.user_permissions.add(*(self.permissions[codename] for codename in codenames))

    def loan(self):
        return Emprunt.objects.create(
            exemplaire=self.copy,
            emprunteur=self.reader,
            date_emprunt=timezone.localdate(),
            date_retour_prevue=timezone.localdate() + timedelta(days=14),
        )


class DigitalLibraryTests(LibraryFixture):
    def setUp(self):
        super().setUp()
        temporary = TemporaryDirectory(prefix="sis-library-test-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.enterContext(override_settings(MEDIA_ROOT=self.folder / "media"))
        self.storage = PrivateLibraryStorage(location=self.folder / "private")
        self.enterContext(patch.object(Livre._meta.get_field("ressource_numerique"), "storage", self.storage))
        self.legacy_name = "bibliotheque/numerique/legacy.pdf"
        self.legacy_file = self.folder / "media" / self.legacy_name
        self.legacy_file.parent.mkdir(parents=True)
        self.legacy_file.write_bytes(PDF)
        self.book.ressource_numerique = self.legacy_name
        self.book.save(update_fields=["ressource_numerique"])
        self.media_url = f"/media/{self.legacy_name}"
        self.grant(self.reader, "consulter_ressource_numerique")
        self.client.force_authenticate(self.reader)

    def activate(self):
        self.book.licence_active = True
        self.book.licence_reference = "Autorisation locale documentée LIB-2026"
        self.book.licence_expire_le = timezone.localdate()
        self.book.save(update_fields=["licence_active", "licence_reference", "licence_expire_le"])

    def assert_denied(self):
        for url in (self.download_url, self.media_url):
            with self.subTest(url=url):
                with patch.object(self.storage, "open", side_effect=AssertionError("Unauthorized bytes opened")):
                    response = self.client.get(url)
                assert response.status_code == 403, response.status_code
        detail = self.client.get(self.book_url)
        assert detail.status_code == 200
        assert detail.data["peut_consulter_ressource"] is False
        assert detail.data["ressource_numerique"] is None

    def assert_download(self):
        for url in (self.download_url, self.media_url):
            response = self.client.get(url)
            assert response.status_code == 200, response.status_code
            assert response["Cache-Control"] == "private, no-store"
            assert response["X-Content-Type-Options"] == "nosniff"
            # The test client's iterator closes the response without closing the test transaction.
            assert b"".join(response.streaming_content) == PDF

    @override_settings(DEBUG=True)
    def test_encoded_ambiguous_media_paths_never_reach_the_static_fallback(self):
        public_file = self.folder / "media" / "public.txt"
        public_file.write_bytes(b"Ordinary public media")
        aliases = (
            f"/media/%2e%2e/media/{self.legacy_name}",
            f"/media/other/%2e%2e/{self.legacy_name}",
            f"/media/%2e/{self.legacy_name}",
            f"/media/%2f{self.legacy_name}",
            f"/media/%5c{self.legacy_name}",
        )
        for actor in (None, self.reader):
            self.client.force_authenticate(actor)
            for url in aliases:
                with self.subTest(actor=actor, url=url):
                    with patch(
                        "sis_common.digital_library.serve", side_effect=AssertionError("Ambiguous static fallback")
                    ):
                        response = self.client.get(url)
                    assert response.status_code == 404, response.status_code
            assert self.client.get(self.media_url).status_code in (401, 403)
            response = self.client.get("/media/public.txt")
            assert response.status_code == 200
            assert b"".join(response.streaming_content) == b"Ordinary public media"
        assert self.legacy_file.read_bytes() == PDF

    def test_legacy_bytes_remain_unmoved_and_each_access_rechecks_licence(self):
        self.assert_denied()
        self.activate()
        self.assert_download()
        with self.assertRaises(SuspiciousFileOperation):
            _ = self.book.ressource_numerique.url
        detail = self.client.get(self.book_url)
        assert detail.data["ressource_numerique"] == self.download_url
        search = self.client.get(f"{BASE}livres/", {"search": "Ressource privée"})
        assert search.data["results"][0]["peut_consulter_ressource"] is True
        for changes in (
            {"licence_expire_le": timezone.localdate() - timedelta(days=1)},
            {"licence_expire_le": None, "licence_active": False},
            {"licence_active": True, "licence_reference": ""},
        ):
            Livre.objects.filter(pk=self.book.pk).update(**changes)
            self.assert_denied()
        assert self.legacy_file.read_bytes() == PDF
        assert not list((self.folder / "private").rglob("*"))

    def test_permission_revocation_and_abac_take_effect_without_reauthenticating(self):
        self.client.force_authenticate(None)
        self.client.force_login(self.reader, backend="sis_common.group_backends.ActiveGroupModelBackend")
        self.activate()
        self.assert_download()
        self.reader.user_permissions.remove(self.permissions["consulter_ressource_numerique"])
        self.assert_denied()
        self.grant(self.reader, "consulter_ressource_numerique")
        self.users.objects.filter(pk=self.reader.pk).update(
            attributs_acces={
                "permission_scopes": {"bibliotheque.consulter_ressource_numerique": {"livre_id": [self.book.pk + 1]}}
            }
        )
        self.assert_denied()
        self.users.objects.filter(pk=self.reader.pk).update(
            attributs_acces={
                "permission_scopes": {
                    "bibliotheque.consulter_ressource_numerique": {
                        "livre_id": [self.book.pk],
                        "etablissement_id": [self.tenant.pk],
                    }
                }
            }
        )
        self.assert_download()

    def test_nonstaff_roles_need_explicit_permission_and_foreign_accounts_are_denied(self):
        self.activate()
        for role in ("parent", "enseignant", self.reader.role):
            actor = self.users.objects.create_user(f"library-role-{role}", role=role, etablissement=self.tenant)
            self.client.force_authenticate(actor)
            self.assert_denied()
            self.grant(actor, "consulter_ressource_numerique")
            self.assert_download()
        self.manager.is_staff = True
        self.manager.save(update_fields=["is_staff"])
        self.client.force_authenticate(self.manager)
        self.assert_denied()
        self.reader.etablissement_id = self.tenant.pk + 100
        self.client.force_authenticate(self.reader)
        for url in (self.book_url, self.download_url, self.media_url):
            assert self.client.get(url).status_code == 403
        self.client.force_authenticate(None)
        assert self.client.get(self.media_url).status_code in (401, 403)

    def test_upload_and_licence_require_explicit_scoped_change_permission(self):
        self.client.force_authenticate(self.manager)
        assert self.client.patch(self.book_url, {"licence_active": True}, format="json").status_code == 403
        assert self.client.delete(self.book_url).status_code == 403
        self.grant(self.manager, "change_livre")
        assert self.client.patch(self.book_url, {"licence_active": True}, format="json").status_code == 400
        for filename, body in (("bad.pdf", b"not a PDF"), ("bad.html", PDF)):
            response = self.client.patch(
                self.book_url,
                {"ressource_numerique": SimpleUploadedFile(filename, body, content_type="application/pdf")},
                format="multipart",
            )
            assert response.status_code == 400, response.data
        with override_settings(EXAM_COPY_MAX_SIZE=4):
            assert (
                self.client.patch(
                    self.book_url,
                    {"ressource_numerique": SimpleUploadedFile("large.pdf", PDF, content_type="application/pdf")},
                    format="multipart",
                ).status_code
                == 400
            )
        response = self.client.patch(
            self.book_url,
            {
                "ressource_numerique": SimpleUploadedFile("new.pdf", PDF, content_type="application/pdf"),
                "licence_active": True,
                "licence_reference": "Droit local documenté",
            },
            format="multipart",
        )
        assert response.status_code == 200, response.data
        assert response.data["ressource_numerique"] is None
        self.book.refresh_from_db()
        assert self.book.ressource_numerique.name.startswith(f"bibliotheque/numerique/{self.tenant.schema_name}/")
        assert self.legacy_file.read_bytes() == PDF
        assert self.client.get(self.media_url).status_code == 404
        self.client.force_authenticate(self.reader)
        response = self.client.get(self.download_url)
        assert b"".join(response.streaming_content) == PDF
        self.users.objects.filter(pk=self.manager.pk).update(
            attributs_acces={"permission_scopes": {"bibliotheque.change_livre": {"livre_id": [self.book.pk + 1]}}}
        )
        self.client.force_authenticate(self.manager)
        assert self.client.patch(self.book_url, {"licence_reference": "Interdit"}, format="json").status_code == 403

    def test_same_reader_searches_consults_borrows_returns_then_reserves(self):
        self.activate()
        self.grant(self.reader, "add_emprunt", "change_emprunt")
        self.grant(self.other, "add_emprunt")
        search = self.client.get(f"{BASE}livres/", {"search": self.book.titre})
        assert [item["id"] for item in search.data["results"]] == [self.book.pk]
        self.assert_download()
        borrowed = self.client.post(f"{BASE}emprunts/", {"exemplaire": self.copy.pk}, format="json")
        assert borrowed.status_code == 201, borrowed.data
        assert self.client.post(f"{BASE}emprunts/{borrowed.data['id']}/{self.return_action}/").status_code == 200
        reserved = self.client.post(f"{BASE}{self.reservations}/", {"livre": self.book.pk}, format="json")
        assert reserved.status_code == 201, reserved.data
        hold = Reservation.objects.get(pk=reserved.data["id"])
        assert hold.utilisateur_id == self.reader.pk
        if settings.SIS_VARIANT == "superieur":
            assert hold.statut == "disponible"
        copy_url = f"{BASE}exemplaires/{self.copy.pk}/"
        assert self.client.get(copy_url).data["disponible"] is True
        self.client.force_authenticate(self.other)
        assert self.client.get(copy_url).data["disponible"] is False
        assert self.client.post(f"{BASE}emprunts/", {"exemplaire": self.copy.pk}, format="json").status_code == 400
        if settings.SIS_VARIANT == "secondaire":
            assert self.client.get(f"{BASE}livres/disponibles/").data == []
        self.client.force_authenticate(self.reader)
        if settings.SIS_VARIANT == "secondaire":
            assert [book["id"] for book in self.client.get(f"{BASE}livres/disponibles/").data] == [self.book.pk]
        second = self.client.post(f"{BASE}emprunts/", {"exemplaire": self.copy.pk}, format="json")
        assert second.status_code == 201, second.data
        hold.refresh_from_db()
        assert hold.statut == ("honoree" if settings.SIS_VARIANT == "secondaire" else "recuperee")
        if settings.SIS_VARIANT == "secondaire":
            assert hold.emprunt_id == second.data["id"]
        assert Emprunt.objects.get(pk=borrowed.data["id"]).statut == "rendu"
        assert Emprunt.objects.filter(exemplaire=self.copy).count() == 2


class LibraryCirculationTests(LibraryFixture):
    def test_explicit_self_loan_return_and_reservation_preserve_history(self):
        self.grant(self.reader, "add_emprunt", "change_emprunt")
        self.client.force_authenticate(self.reader)
        denied = self.client.post(
            f"{BASE}emprunts/", {"exemplaire": self.copy.pk, "emprunteur": self.other.pk}, format="json"
        )
        assert denied.status_code == 403, denied.data
        assert (
            self.client.post(
                f"{BASE}emprunts/",
                {"exemplaire": self.copy.pk, "date_retour_prevue": str(timezone.localdate() + timedelta(days=999))},
                format="json",
            ).status_code
            == 400
        )
        created = self.client.post(f"{BASE}emprunts/", {"exemplaire": self.copy.pk}, format="json")
        assert created.status_code == 201, created.data
        assert created.data["emprunteur"] == self.reader.pk
        loan_url = f"{BASE}emprunts/{created.data['id']}/"
        assert self.client.post(f"{BASE}emprunts/", {"exemplaire": self.copy.pk}, format="json").status_code == 400
        self.client.force_authenticate(self.other)
        reserved = self.client.post(f"{BASE}{self.reservations}/", {"livre": self.book.pk}, format="json")
        assert reserved.status_code == 201, reserved.data
        self.client.force_authenticate(self.reader)
        assert self.client.post(f"{loan_url}renouveler/").status_code == 400
        self.reader.user_permissions.remove(self.permissions["change_emprunt"])
        assert self.client.post(f"{loan_url}{self.return_action}/").status_code == 403
        self.grant(self.reader, "change_emprunt")
        assert self.client.post(f"{loan_url}{self.return_action}/").status_code == 200
        assert self.client.post(f"{loan_url}{self.return_action}/").status_code == 400
        assert Reservation.objects.filter(pk=reserved.data["id"]).exists()
        assert Emprunt.objects.get(pk=created.data["id"]).statut == "rendu"
        self.grant(self.manager, "change_livre")
        self.client.force_authenticate(self.manager)
        assert self.client.patch(loan_url, {"statut": "en_cours"}, format="json").status_code == 405
        assert self.client.delete(loan_url).status_code == 405
        assert self.client.delete(self.book_url).status_code == 400
        assert self.client.delete(f"{BASE}exemplaires/{self.copy.pk}/").status_code == 400

    def test_status_injection_lost_copy_and_foreign_title_mutations_are_rejected(self):
        self.client.force_authenticate(self.manager)
        forged = self.client.post(
            f"{BASE}emprunts/",
            {"exemplaire": self.copy.pk, "emprunteur": self.reader.pk, "statut": "rendu"},
            format="json",
        )
        assert forged.status_code == 400, forged.data
        loan = self.loan()
        loan.statut = "perdu"
        loan.save(update_fields=["statut"])
        blocked = self.client.post(
            f"{BASE}emprunts/", {"exemplaire": self.copy.pk, "emprunteur": self.other.pk}, format="json"
        )
        assert blocked.status_code == 400, blocked.data
        other_book = Livre.objects.create(titre="Autre titre", auteurs="Auteur")
        assert (
            self.client.patch(f"{BASE}exemplaires/{self.copy.pk}/", {"livre": other_book.pk}, format="json").status_code
            == 400
        )
        assert Emprunt.objects.filter(exemplaire=self.copy).count() == 1


class LibraryConcurrencyTests(LibraryFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)

    def race(self):
        assert connection.vendor == "postgresql"
        assert not connection.in_atomic_block
        self.grant(self.reader, "add_emprunt")
        self.grant(self.other, "add_emprunt")
        barrier = Barrier(2)

        def borrow(actor_id):
            try:
                with schema_context(self.tenant.schema_name):
                    actor = self.users.objects.get(pk=actor_id)
                    client = APIClient(SERVER_NAME=self.get_test_tenant_domain())
                    client.force_authenticate(actor)
                    barrier.wait(timeout=10)
                    return client.post(f"{BASE}emprunts/", {"exemplaire": self.copy.pk}, format="json").status_code
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(borrow, (self.reader.pk, self.other.pk)))

    def test_two_requests_cannot_issue_the_same_copy(self):
        results = self.race()
        assert sorted(results) == [201, 400], results
        assert Emprunt.objects.filter(exemplaire=self.copy).count() == 1

    def test_hold_owner_wins_against_concurrent_nonowner(self):
        hold = Reservation.objects.create(livre=self.book, utilisateur=self.reader, statut="disponible")
        assert self.race() == [201, 400]
        assert Emprunt.objects.get(exemplaire=self.copy).emprunteur_id == self.reader.pk
        hold.refresh_from_db()
        assert hold.statut == ("honoree" if settings.SIS_VARIANT == "secondaire" else "recuperee")
