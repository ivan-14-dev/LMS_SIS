"""Mounted search/native/PDF parity; only PDF rendering is substituted."""

import uuid
from unittest.mock import patch

from apps.classes.models import Classe
from apps.eleves.models import Eleve, EleveTuteur, Tuteur
from apps.enseignants.models import Personnel
from apps.etablissement.models import AnneeScolaire, Etablissement, Niveau, Periode
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.notes.models import Bulletin
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.http import HttpResponse
from django.test import override_settings
from django_tenants.utils import schema_context


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class BulletinVisibilityHTTPTests(TenantAPITestCase):
    search_url = "/api/v1/core/recherche-academique/"
    source_urls = ("/api/v1/notes/bulletins/", "/api/v1/bulletins/")

    def setUp(self):
        self.other = Etablissement(schema_name=f"bulletin_search_{uuid.uuid4().hex[:12]}")
        self.setup_tenant(self.other)
        self.other.auto_create_schema = False
        with schema_context("public"):
            self.other.save()
        self.manager = Utilisateur.objects.create_user(
            "bulletin-direction", role="direction", etablissement=self.tenant
        )
        self.teacher = Utilisateur.objects.create_user("bulletin-teacher", role="enseignant", etablissement=self.tenant)
        Personnel.objects.create(user=self.teacher, matricule="TEACHER-BUL", date_embauche="2026-09-01")
        self.year = self._year(self.tenant)
        self.foreign_year = self._year(self.other)
        self.level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        self.foreign_level = Niveau.objects.create(etablissement=self.other, code="6e", libelle="Sixième")
        self.classroom = self._classroom("PrivateClass", prof_principal=self.teacher)
        self.peer_classroom = self._classroom("PeerClass")
        self.period = self._period(1)
        self.draft_period = self._period(2)
        self.foreign_period = self._period(1, annee_scolaire=self.foreign_year)
        self.owner = self._pupil("owner", self.tenant)
        self.peer = self._pupil("peer", self.tenant)
        self.foreign = self._pupil("foreign", self.other)
        self.published = self._bulletin(self.owner, self.period, publie=True)
        self.draft = self._bulletin(self.owner, self.draft_period)
        self.peer_bulletin = self._bulletin(self.peer, self.period, classe=self.peer_classroom, publie=True)
        self.foreign_bulletin = self._bulletin(self.foreign, self.period, publie=True)
        self.visible = [self.published, self.draft, self.peer_bulletin]
        self.bulletins = [*self.visible, self.foreign_bulletin]
        self.read_permission = Permission.objects.get(content_type__app_label="notes", codename="view_bulletin")

    def _year(self, tenant):
        return AnneeScolaire.objects.create(
            etablissement=tenant, libelle="2026-2027", date_debut="2026-09-01", date_fin="2027-08-31"
        )

    def _classroom(self, name, **overrides):
        return Classe.objects.create(
            **{
                "etablissement": self.tenant,
                "annee_scolaire": self.year,
                "niveau": self.level,
                "nom": name,
                **overrides,
            }
        )

    def _period(self, number, **overrides):
        return Periode.objects.create(
            **{
                "annee_scolaire": self.year,
                "type": "trimestre",
                "numero": number,
                "libelle": f"PrivatePeriod {number}",
                "date_debut": "2026-09-01",
                "date_fin": "2026-12-31",
                **overrides,
            }
        )

    def _pupil(self, name, tenant):
        user = Utilisateur.objects.create_user(
            f"bulletin-{name}", role="eleve", etablissement=tenant, first_name="PrivateFirst", last_name="PrivateLast"
        )
        return Eleve.objects.create(
            etablissement=tenant,
            user=user,
            matricule=f"PRIVATE-{name}",
            date_naissance="2010-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )

    def _bulletin(self, pupil, period, **overrides):
        return Bulletin.objects.create(
            **{
                "eleve": pupil,
                "classe": self.classroom,
                "periode": period,
                "moyenne_generale": "18.50",
                "appreciation_conseil": "PrivateAppreciation",
                "decision": "PrivateDecision",
                "pdf_path": "private/bulletin.pdf",
                **overrides,
            }
        )

    def _parent(self):
        parent = Utilisateur.objects.create_user("bulletin-parent", role="parent", etablissement=self.tenant)
        guardian = Tuteur.objects.create(
            etablissement=self.tenant,
            user=parent,
            nom="Parent",
            prenom="Parent",
            lien_parente="mere",
            telephone="0100000000",
            email="parent@example.test",
        )
        link = EleveTuteur.objects.create(eleve=self.owner, tuteur=guardian, autorise_acces_portail=True)
        EleveTuteur.objects.create(eleve=self.peer, tuteur=guardian, autorise_acces_portail=False)
        return parent, guardian, link

    def _authenticate(self, user):
        self.client.force_authenticate(Utilisateur.objects.get(pk=user.pk) if user else None)

    def _search(self, term="BUL-", **params):
        return self.client.get(self.search_url, {"ressource": "bulletins", "q": term, **params}, secure=True)

    def _assert_visible(self, user, expected):
        self._authenticate(user)
        search = self._search()
        assert search.status_code == 200, search.data
        assert search.data["count"] == len(expected)
        assert search.data["results"] == [
            {"id": bulletin.pk, "code": f"BUL-{bulletin.pk}", "nom": f"Bulletin BUL-{bulletin.pk}"}
            for bulletin in sorted(expected, key=lambda bulletin: bulletin.pk)
        ]
        expected_ids = {bulletin.pk for bulletin in expected}
        with patch(
            "apps.notes.api.render_official_pdf",
            side_effect=lambda *args, **kwargs: HttpResponse(b"%PDF-test", content_type="application/pdf"),
        ) as render:
            for base in self.source_urls:
                listing = self.client.get(base, secure=True)
                assert listing.status_code == 200, listing.data
                assert listing.data["count"] == len(expected)
                assert {row["id"] for row in listing.data["results"]} == expected_ids
                for bulletin in self.bulletins:
                    detail = self.client.get(f"{base}{bulletin.pk}/", secure=True)
                    render.reset_mock()
                    pdf = self.client.get(f"{base}{bulletin.pk}/pdf_officiel/", secure=True)
                    assert detail.status_code == pdf.status_code == (200 if bulletin.pk in expected_ids else 404)
                    if bulletin.pk in expected_ids:
                        assert pdf["Cache-Control"] == "private, no-store"
                        assert ("Numéro / série", f"BUL-{bulletin.pk}") in render.call_args.args[2]
                    else:
                        render.assert_not_called()

    def _assert_denied(self, user):
        self._authenticate(user)
        urls = [
            url
            for base in self.source_urls
            for url in (base, f"{base}{self.published.pk}/", f"{base}{self.published.pk}/pdf_officiel/")
        ]
        results = [self._search(), *(self.client.get(url, secure=True) for url in urls)]
        for result in results:
            assert result.status_code in ((403,) if user else (401, 403))
            assert f"BUL-{self.published.pk}" not in str(result.data)
            assert self.owner.matricule not in str(result.data)

    def test_search_reuses_official_pdf_reference_and_excludes_private_search_fields(self):
        self._assert_visible(self.manager, self.visible)
        result = self._search(f" bul-{self.published.pk} ")
        assert result.status_code == 200
        assert result.data["results"] == [
            {
                "id": self.published.pk,
                "code": f"BUL-{self.published.pk}",
                "nom": f"Bulletin BUL-{self.published.pk}",
            }
        ]
        for term in (
            self.owner.matricule,
            "PrivateFirst",
            "PrivateLast",
            "PrivateClass",
            "PrivatePeriod",
            "PrivateAppreciation",
            "PrivateDecision",
            "private/bulletin.pdf",
            "18.50",
        ):
            assert self._search(term).data["count"] == 0

    def test_pupil_publication_revocation_and_read_grant_do_not_expand_ownership(self):
        self.draft.signe = True
        self.draft.save(update_fields=["signe"])
        self.owner.user.user_permissions.add(self.read_permission)
        self._assert_visible(self.owner.user, [self.published])
        self.published.publie = False
        self.published.save(update_fields=["publie"])
        self._assert_visible(self.owner.user, [])
        self.draft.publie = True
        self.draft.save(update_fields=["publie"])
        self._assert_visible(self.owner.user, [self.draft])

    def test_guardian_portal_revocation_publication_and_foreign_profile_are_enforced(self):
        parent, guardian, link = self._parent()
        parent.user_permissions.add(self.read_permission)
        self._assert_visible(parent, [self.published])
        guardian.etablissement = self.other
        guardian.save(update_fields=["etablissement"])
        self._assert_visible(parent, [])
        guardian.etablissement = self.tenant
        guardian.save(update_fields=["etablissement"])
        link.autorise_acces_portail = False
        link.save(update_fields=["autorise_acces_portail"])
        self._assert_visible(parent, [])
        link.autorise_acces_portail = True
        link.save(update_fields=["autorise_acces_portail"])
        self.published.publie = False
        self.published.save(update_fields=["publie"])
        self._assert_visible(parent, [])

    def test_teacher_uses_user_fk_and_read_grant_cannot_bypass_principal_class_revocation(self):
        self.teacher.user_permissions.add(self.read_permission)
        self._assert_visible(self.teacher, [self.published, self.draft])
        self.classroom.prof_principal = None
        self.classroom.save(update_fields=["prof_principal"])
        self._assert_visible(self.teacher, [])
        self.teacher.personnel_profile.delete()
        self._assert_visible(self.teacher, [])
        self.peer_classroom.prof_principal = self.teacher
        self.peer_classroom.save(update_fields=["prof_principal"])
        self._assert_visible(self.teacher, [self.peer_bulletin])

    def test_staff_flag_is_not_a_grant_and_permission_revocation_is_explicit(self):
        self.manager.role = "comptable"
        self.manager.is_staff = True
        self.manager.save(update_fields=["role", "is_staff"])
        self._assert_denied(self.manager)
        self.manager.user_permissions.add(self.read_permission)
        self._assert_visible(self.manager, self.visible)
        self.manager.user_permissions.remove(self.read_permission)
        self._assert_denied(self.manager)

    def test_foreign_superuser_inactive_and_anonymous_are_denied_on_all_routes(self):
        self.foreign.user.is_superuser = True
        self.foreign.user.is_staff = True
        self.foreign.user.save(update_fields=["is_superuser", "is_staff"])
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        for user in (self.foreign.user, self.manager, None):
            self._assert_denied(user)

    def test_local_superuser_cannot_bypass_foreign_bulletin_relationships(self):
        self.manager.is_superuser = True
        self.manager.save(update_fields=["is_superuser"])
        foreign_classes = [
            self._classroom("ForeignClass", etablissement=self.other),
            self._classroom("ForeignYear", annee_scolaire=self.foreign_year),
            self._classroom("ForeignLevel", niveau=self.foreign_level),
        ]
        for classroom in foreign_classes:
            with self.subTest(classroom=classroom.nom):
                self.published.classe = classroom
                self.published.save(update_fields=["classe"])
                self._assert_visible(self.manager, [self.draft, self.peer_bulletin])
        self.published.classe = self.classroom
        self.published.periode = self.foreign_period
        self.published.save(update_fields=["classe", "periode"])
        self._assert_visible(self.manager, [self.draft, self.peer_bulletin])
        self.published.periode = self.period
        self.published.save(update_fields=["periode"])
        self.owner.user.etablissement = self.other
        self.owner.user.save(update_fields=["etablissement"])
        self._assert_visible(self.manager, [self.peer_bulletin])

    def test_read_scopes_only_narrow_native_pdf_and_search_visibility(self):
        for constraints, expected in (
            ({"classes": [self.peer_classroom.pk]}, [self.peer_bulletin]),
            ({"annees": [self.year.pk], "periodes": [self.draft_period.pk]}, [self.draft]),
            ({"annees": [self.foreign_year.pk]}, []),
            ({"classes": []}, []),
            ({"classes": "all"}, []),
            ({"unsupported": [self.published.pk]}, []),
        ):
            with self.subTest(constraints=constraints):
                cache.clear()
                self.manager.attributs_acces = {"permission_scopes": {"notes.view_bulletin": constraints}}
                self.manager.save(update_fields=["attributs_acces"])
                self._assert_visible(self.manager, expected)
        self.owner.user.attributs_acces = {
            "permission_scopes": {"notes.view_bulletin": {"classes": [self.peer_classroom.pk]}}
        }
        self.owner.user.save(update_fields=["attributs_acces"])
        self._assert_visible(self.owner.user, [])

    def test_bulletin_queries_are_bounded_and_control_characters_rejected(self):
        self._authenticate(self.manager)
        for term in ("", " ", "a", "x" * 101, " " * 99 + "ab", "ab\n", "a\tb", "ab\x00", "ab\x7f", "ab\x85"):
            with self.subTest(term=term):
                result = self._search(term)
                assert result.status_code == 400
                assert "q" in result.data
        for term in ("ab", "x" * 100):
            assert self._search(term).status_code == 200
        assert self.client.get(self.search_url, {"ressource": "bulletins"}, secure=True).status_code == 400

    def test_bulletin_pagination_is_stable_and_preserves_twenty_fifty_limits(self):
        for number in range(1, 49):
            self._bulletin(self.owner, self._period(number, type="sequence"))
        self._authenticate(self.manager)
        first = self._search()
        second = self.client.get(first.data["next"], secure=True)
        assert first.status_code == second.status_code == 200
        assert first.data["count"] == second.data["count"] == 51
        assert len(first.data["results"]) == len(second.data["results"]) == 20
        assert not {row["id"] for row in first.data["results"]} & {row["id"] for row in second.data["results"]}
        capped = self._search(page_size=999)
        last = self.client.get(capped.data["next"], secure=True)
        assert capped.status_code == last.status_code == 200
        assert len(capped.data["results"]) == 50
        assert len(last.data["results"]) == 1
        assert last.data["next"] is None
