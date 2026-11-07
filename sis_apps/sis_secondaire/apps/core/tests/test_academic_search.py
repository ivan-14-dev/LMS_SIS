"""Mounted HTTP search/record visibility parity in a real tenant schema."""

import uuid

from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve, EleveTuteur, Tuteur
from apps.etablissement.models import AnneeScolaire, Etablissement, Niveau
from apps.integration.models import EdxCourseMapping
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.paiements.models import Facture, TypeFrais
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.test import override_settings
from django_tenants.utils import schema_context


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class AcademicSearchAPITests(TenantAPITestCase):
    url = "/api/v1/core/recherche-academique/"
    pupils_url = "/api/v1/eleves/"
    invoices_url = "/api/v1/paiements/factures/"

    def setUp(self):
        self.other = Etablissement(schema_name=f"school_search_{uuid.uuid4().hex[:12]}")
        self.setup_tenant(self.other)
        self.other.auto_create_schema = False
        with schema_context("public"):
            self.other.save()
        self.owner = self._pupil("owner", self.tenant)
        self.peer = self._pupil("peer", self.tenant)
        self.foreign = self._pupil("foreign", self.other)
        self.pupils = [self.owner, self.peer, self.foreign]
        self.staff = Utilisateur.objects.create_user(
            "search-staff", role="enseignant", etablissement=self.tenant, is_staff=True
        )
        self.pupil_permission = Permission.objects.get(content_type__app_label="eleves", codename="view_eleve")
        self.finance_permission = Permission.objects.get(
            content_type__app_label="paiements", codename="change_paiement"
        )
        self.staff.user_permissions.add(self.pupil_permission)
        self.manager = Utilisateur.objects.create_user(
            "search-finance", role="comptable", etablissement=self.tenant
        )
        self.fee = self._fee(self.tenant)
        self.foreign_fee = self._fee(self.other)
        self.own_invoice = self._invoice(self.owner, "SRCH-OWN")
        self.peer_invoice = self._invoice(self.peer, "SRCH-PEER")
        self.foreign_invoice = self._invoice(self.foreign, "SRCH-FOREIGN-PUPIL")
        self.mixed_invoice = self._invoice(self.owner, "SRCH-FOREIGN-FEE", self.foreign_fee)
        self.invoices = [self.own_invoice, self.peer_invoice, self.foreign_invoice, self.mixed_invoice]

    def _pupil(self, name, tenant):
        user = Utilisateur.objects.create_user(
            f"search-{name}", role="eleve", etablissement=tenant, first_name="Anne", last_name="Mercier",
            email=f"{name}@private.example",
        )
        return Eleve.objects.create(
            etablissement=tenant, user=user, matricule=f"SRCH-{name}",
            date_naissance="2010-01-01", lieu_naissance="Paris", sexe="F", date_inscription="2026-09-01",
            ine=f"PRIVATE-{name}", contact_urgence_tel="0102030405",
        )

    def _fee(self, tenant):
        year = AnneeScolaire.objects.create(
            etablissement=tenant, libelle="2026-2027", date_debut="2026-09-01", date_fin="2027-08-31"
        )
        return TypeFrais.objects.create(
            annee_scolaire=year, code="SEARCH", libelle="PrivateRubric", montant="100.00"
        )

    def _invoice(self, pupil, number, fee=None):
        return Facture.objects.create(
            eleve=pupil, type_frais=fee or self.fee, numero=number,
            date_emission="2026-09-01", date_echeance="2026-10-01", montant="100.00",
            note="PrivateNote", pdf_path="private/invoice.pdf",
        )

    def _authenticate(self, user):
        # A new request must observe permission revocation rather than a cached grant.
        self.client.force_authenticate(Utilisateur.objects.get(pk=user.pk))

    def _search(self, resource, term="SRCH-", **params):
        return self.client.get(self.url, {"ressource": resource, "q": term, **params}, secure=True)

    def _assert_pupils(self, user, expected):
        self._authenticate(user)
        search = self._search("eleves")
        listing = self.client.get(self.pupils_url, {"search": "SRCH-"}, secure=True)
        assert search.status_code == listing.status_code == 200
        assert search.data["count"] == listing.data["count"] == len(expected)
        assert search.data["results"] == [
            {"id": pupil.pk, "code": pupil.matricule, "nom": "Anne Mercier"}
            for pupil in sorted(expected, key=lambda pupil: pupil.pk)
        ]
        expected_ids = {pupil.pk for pupil in expected}
        assert {row["id"] for row in listing.data["results"]} == expected_ids
        for pupil in self.pupils:
            detail = self.client.get(f"{self.pupils_url}{pupil.pk}/", secure=True)
            assert detail.status_code == (200 if pupil.pk in expected_ids else 404), detail.data

    def _assert_invoices(self, user, expected):
        self._authenticate(user)
        search = self._search("factures")
        listing = self.client.get(self.invoices_url, {"search": "SRCH-"}, secure=True)
        assert search.status_code == listing.status_code == 200
        assert search.data["count"] == listing.data["count"] == len(expected)
        assert search.data["results"] == [
            {"id": invoice.pk, "code": invoice.numero, "nom": f"Facture {invoice.numero}"}
            for invoice in sorted(expected, key=lambda invoice: invoice.pk)
        ]
        expected_ids = {invoice.pk for invoice in expected}
        assert {row["id"] for row in listing.data["results"]} == expected_ids
        for invoice in self.invoices:
            balance = self.client.get(f"{self.invoices_url}{invoice.pk}/solde-confirme/", secure=True)
            assert balance.status_code == (200 if invoice.pk in expected_ids else 404), balance.data
            if invoice.pk not in expected_ids:
                assert invoice.numero not in str(search.data)

    def test_pupil_search_matches_listing_detail_and_minimal_fields(self):
        self._assert_pupils(self.staff, [self.owner, self.peer])
        for term in (" srch-owner ", "anne", "MERCIER"):
            result = self._search("eleves", term)
            assert result.status_code == 200, result.data
            assert result.data["count"] == (1 if term.strip() == "srch-owner" else 2)
        for private_term in (self.owner.ine, self.owner.user.email, self.owner.contact_urgence_tel):
            assert self._search("eleves", private_term).data["count"] == 0

    def test_pupil_view_permission_is_required_and_revocable(self):
        self._authenticate(self.manager)
        assert self._search("eleves").status_code == 403
        self._assert_pupils(self.staff, [self.owner, self.peer])
        self.staff.user_permissions.remove(self.pupil_permission)
        self._authenticate(self.staff)
        assert self._search("eleves").status_code == 403

    def test_pupil_model_permission_does_not_expand_personal_visibility(self):
        self.owner.user.user_permissions.add(self.pupil_permission)
        self._assert_pupils(self.owner.user, [self.owner])
        assert self._search("eleves", self.peer.matricule).data["count"] == 0
        self.owner.user.attributs_acces = {
            "permission_scopes": {"eleves.view_eleve": {"eleves": [self.peer.pk]}}
        }
        self.owner.user.save(update_fields=["attributs_acces"])
        self._assert_pupils(self.owner.user, [])

    def test_pupil_object_scopes_match_list_and_detail_and_fail_closed(self):
        level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        classroom = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=self.fee.annee_scolaire, niveau=level, nom="6A"
        )
        self.peer.classe_actuelle = classroom
        self.peer.save(update_fields=["classe_actuelle"])
        for constraints, expected in (
            ({"eleves": [self.owner.pk]}, [self.owner]),
            ({"classes": [classroom.pk]}, [self.peer]),
            ({"eleves": []}, []),
            ({"eleves": "all"}, []),
            ({"unsupported": [self.owner.pk]}, []),
        ):
            with self.subTest(constraints=constraints):
                self.staff.attributs_acces = {"permission_scopes": {"eleves.view_eleve": constraints}}
                self.staff.save(update_fields=["attributs_acces"])
                self._assert_pupils(self.staff, expected)

    def test_parent_search_tracks_authorized_portal_links_and_revocation(self):
        parent = Utilisateur.objects.create_user("search-parent", role="parent", etablissement=self.tenant)
        parent.user_permissions.add(self.pupil_permission)
        self._assert_pupils(parent, [])
        self._assert_invoices(parent, [])
        guardian = Tuteur.objects.create(
            etablissement=self.tenant, user=parent, nom="Mercier", prenom="Parent", lien_parente="mere",
            telephone="0100000000", email="parent@example.test",
        )
        link = EleveTuteur.objects.create(eleve=self.owner, tuteur=guardian, autorise_acces_portail=True)
        EleveTuteur.objects.create(eleve=self.peer, tuteur=guardian, autorise_acces_portail=False)
        self._assert_pupils(parent, [self.owner])
        self._assert_invoices(parent, [self.own_invoice])
        parent.user_permissions.add(self.finance_permission)
        self._assert_invoices(parent, [self.own_invoice])
        link.autorise_acces_portail = False
        link.save(update_fields=["autorise_acces_portail"])
        self._assert_pupils(parent, [])
        self._assert_invoices(parent, [])

    def test_invoice_search_matches_personal_list_and_balance_without_private_fields(self):
        self._assert_invoices(self.owner.user, [self.own_invoice])
        result = self._search("factures", " srch-own ")
        assert result.status_code == 200
        assert result.data["results"] == [
            {"id": self.own_invoice.pk, "code": self.own_invoice.numero, "nom": f"Facture {self.own_invoice.numero}"}
        ]
        for term in (
            "Mercier", "PrivateRubric", "PrivateNote", self.owner.ine, self.owner.matricule, self.peer_invoice.numero,
        ):
            assert self._search("factures", term).data["count"] == 0

    def test_finance_grant_does_not_expand_pupils_personal_invoices(self):
        self.owner.user.user_permissions.add(self.finance_permission)
        self._assert_invoices(self.owner.user, [self.own_invoice])

    def test_invoice_access_requires_existing_finance_policy_not_staff_or_read_grant(self):
        self._assert_invoices(self.manager, [self.own_invoice, self.peer_invoice])
        self.staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="paiements", codename="view_facture")
        )
        self._assert_invoices(self.staff, [])
        self.staff.user_permissions.add(self.finance_permission)
        self._assert_invoices(self.staff, [self.own_invoice, self.peer_invoice])
        self.staff.user_permissions.remove(self.finance_permission)
        self._assert_invoices(self.staff, [])
        self.manager.role = "enseignant"
        self.manager.save(update_fields=["role"])
        self._assert_invoices(self.manager, [])
        self.owner.user.role = "enseignant"
        self.owner.user.save(update_fields=["role"])
        self._assert_invoices(self.owner.user, [])

    def test_invoice_read_scopes_only_narrow_authorized_rows(self):
        for constraints, expected in (
            ({"eleves": [self.peer.pk]}, [self.peer_invoice]),
            ({"factures": [self.own_invoice.pk]}, [self.own_invoice]),
            ({"rubriques": [self.foreign_fee.pk]}, []),
            ({"annees": []}, []),
            ({"eleves": "all"}, []),
            ({"unsupported": [self.own_invoice.pk]}, []),
        ):
            with self.subTest(constraints=constraints):
                self.manager.attributs_acces = {"permission_scopes": {"paiements.view_facture": constraints}}
                self.manager.save(update_fields=["attributs_acces"])
                self._assert_invoices(self.manager, expected)
        self.owner.user.attributs_acces = {
            "permission_scopes": {"paiements.view_facture": {"factures": [self.peer_invoice.pk]}}
        }
        self.owner.user.save(update_fields=["attributs_acces"])
        self._assert_invoices(self.owner.user, [])

    def test_scoped_finance_grant_does_not_bypass_existing_manager_check(self):
        for user in (self.manager, self.staff):
            user.user_permissions.add(self.finance_permission)
            user.attributs_acces = {
                "permission_scopes": {"paiements.change_paiement": {"factures": [self.own_invoice.pk]}}
            }
            user.save(update_fields=["attributs_acces"])
            self._assert_invoices(user, [])

    def test_scoped_invoice_visibility_remains_lockable_for_cancellation(self):
        self.manager.attributs_acces = {
            "permission_scopes": {"paiements.view_facture": {"factures": [self.own_invoice.pk]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        self._assert_invoices(self.manager, [self.own_invoice])
        blocked = self.client.post(f"{self.invoices_url}{self.peer_invoice.pk}/annuler/", secure=True)
        assert blocked.status_code == 404, blocked.data
        cancelled = self.client.post(f"{self.invoices_url}{self.own_invoice.pk}/annuler/", secure=True)
        assert cancelled.status_code == 200, cancelled.data
        self.own_invoice.refresh_from_db()
        self.peer_invoice.refresh_from_db()
        assert self.own_invoice.statut == "annulee"
        assert self.peer_invoice.statut == "emise"

    def test_guardian_invoice_visibility_remains_lockable_without_bypassing_revocation(self):
        parent = Utilisateur.objects.create_user("cancel-parent", role="parent", etablissement=self.tenant)
        parent.user_permissions.add(
            Permission.objects.get(content_type__app_label="paiements", codename="change_facture")
        )
        guardian = Tuteur.objects.create(
            etablissement=self.tenant, user=parent, nom="Mercier", prenom="Parent", lien_parente="mere",
            telephone="0100000000", email="parent@example.test",
        )
        link = EleveTuteur.objects.create(eleve=self.owner, tuteur=guardian, autorise_acces_portail=True)
        self._assert_invoices(parent, [self.own_invoice])
        blocked = self.client.post(f"{self.invoices_url}{self.peer_invoice.pk}/annuler/", secure=True)
        assert blocked.status_code == 404, blocked.data
        url = f"{self.invoices_url}{self.own_invoice.pk}/annuler/"
        cancelled = self.client.post(url, secure=True)
        assert cancelled.status_code == 200, cancelled.data
        self.own_invoice.refresh_from_db()
        assert self.own_invoice.statut == "annulee"
        link.autorise_acces_portail = False
        link.save(update_fields=["autorise_acces_portail"])
        self._assert_invoices(parent, [])
        assert self.client.post(url, secure=True).status_code == 404

    def test_foreign_superuser_and_inactive_actor_cannot_search(self):
        foreign = self.foreign.user
        foreign.is_superuser = True
        foreign.save(update_fields=["is_superuser"])
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        for user in (foreign, self.manager):
            self._authenticate(user)
            for resource in ("eleves", "factures"):
                result = self._search(resource)
                assert result.status_code == 403
                assert "SRCH-" not in str(result.data)
            listing = self.client.get(self.invoices_url, secure=True)
            assert listing.status_code == 200
            assert listing.data["count"] == 0
            balance = self.client.get(f"{self.invoices_url}{self.own_invoice.pk}/solde-confirme/", secure=True)
            assert balance.status_code == 404

    def test_queries_are_bounded_and_control_characters_rejected_for_both_resources(self):
        self._authenticate(self.staff)
        for resource in ("eleves", "factures"):
            for term in (
                "", " ", "a", "x" * 101, " " * 99 + "ab", "ab\n", "a\tb", "ab\x00", "ab\x7f", "ab\x85",
            ):
                with self.subTest(resource=resource, term=term):
                    result = self._search(resource, term)
                    assert result.status_code == 400
                    assert "q" in result.data
            for term in ("ab", "x" * 100):
                assert self._search(resource, term).status_code == 200
            assert self.client.get(self.url, {"ressource": resource}, secure=True).status_code == 400
        for resource in ("", "etudiants", "unknown", "eleves,factures"):
            assert self._search(resource).status_code == 400
        assert self.client.get(self.url, {"q": "SRCH-"}, secure=True).status_code == 400
        assert self.client.post(self.url, {}, format="json", secure=True).status_code == 405

    def test_anonymous_search_is_denied_for_both_resources(self):
        self.client.force_authenticate(user=None)
        for resource in ("eleves", "factures"):
            result = self._search(resource)
            assert result.status_code in (401, 403)
            assert "SRCH-" not in str(result.data)

    def test_invoice_pagination_has_stable_pages_default_twenty_and_maximum_fifty(self):
        for index in range(49):
            self._invoice(self.owner, f"SRCH-PAGE-{index:02}")
        self._authenticate(self.manager)
        first = self._search("factures")
        second = self.client.get(first.data["next"], secure=True)
        assert first.status_code == second.status_code == 200
        assert set(first.data) == {"count", "next", "previous", "results"}
        assert first.data["count"] == second.data["count"] == 51
        assert len(first.data["results"]) == len(second.data["results"]) == 20
        assert first.data["previous"] is None
        assert second.data["previous"] is not None
        assert not {row["id"] for row in first.data["results"]} & {
            row["id"] for row in second.data["results"]
        }
        capped = self._search("factures", page_size=999)
        last = self.client.get(capped.data["next"], secure=True)
        assert capped.status_code == last.status_code == 200
        assert len(capped.data["results"]) == 50
        assert len(last.data["results"]) == 1
        assert last.data["next"] is None
        assert last.data["previous"] is not None

    def test_pupil_pagination_preserves_resource_and_visibility(self):
        self._authenticate(self.staff)
        first = self._search("eleves", page_size=1)
        second = self.client.get(first.data["next"], secure=True)
        assert first.status_code == second.status_code == 200
        assert first.data["count"] == second.data["count"] == 2
        assert first.data["results"][0]["id"] == self.owner.pk
        assert second.data["results"][0]["id"] == self.peer.pk
        assert second.data["next"] is None


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class AcademicCourseSearchAPITests(TenantAPITestCase):
    url = "/api/v1/core/recherche-academique/"
    courses_url = "/api/v1/integration/mappings/courses/"

    def setUp(self):
        self.other = Etablissement(schema_name=f"school_courses_{uuid.uuid4().hex[:12]}")
        self.setup_tenant(self.other)
        self.other.auto_create_schema = False
        with schema_context("public"):
            self.other.save()
        self.staff = Utilisateur.objects.create_user(
            "course-search-staff", role="enseignant", etablissement=self.tenant, is_staff=True
        )
        self.year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2026-2027", date_debut="2026-09-01", date_fin="2027-08-31"
        )
        self.foreign_year = AnneeScolaire.objects.create(
            etablissement=self.other, libelle="2026-2027", date_debut="2026-09-01", date_fin="2027-08-31"
        )
        self.level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        self.foreign_level = Niveau.objects.create(etablissement=self.other, code="6e", libelle="Sixième")
        self.classroom = self._classroom("PrivateClass")
        self.subject = Matiere.objects.create(
            etablissement=self.tenant, code="PRIVATE", nom="PrivateSubject"
        )
        self.active = self._mapping("ACTIVE", self.classroom)
        self.inactive = self._mapping("INACTIVE", self._classroom("SecondClass"), actif=False)
        legacy_class = self._classroom("LegacyClass", etablissement=None)
        legacy_subject = Matiere.objects.create(etablissement=None, code="LEGACY", nom="LegacySubject")
        self.legacy = self._mapping("LEGACY", legacy_class, matiere=legacy_subject)
        foreign_subject = Matiere.objects.create(etablissement=self.other, code="FOREIGN", nom="ForeignSubject")
        self.foreign_mappings = [
            self._mapping("FOREIGN-SUBJECT", self.classroom, matiere=foreign_subject),
            self._mapping("FOREIGN-CLASS", self._classroom("ForeignClass", etablissement=self.other)),
            self._mapping("FOREIGN-YEAR", self._classroom("ForeignYear", annee_scolaire=self.foreign_year)),
            self._mapping("FOREIGN-LEVEL", self._classroom("ForeignLevel", niveau=self.foreign_level)),
        ]
        self.visible = [self.active, self.inactive, self.legacy]
        self.mappings = self.visible + self.foreign_mappings

    def _classroom(self, name, **overrides):
        return Classe.objects.create(**{
            "etablissement": self.tenant, "annee_scolaire": self.year,
            "niveau": self.level, "nom": name, **overrides,
        })

    def _mapping(self, code, classroom, **overrides):
        return EdxCourseMapping.objects.create(**{
            "matiere": self.subject, "classe": classroom,
            "course_id": f"course-v1:SEARCH+{code}+2026", "course_name": f"Search course {code}",
            **overrides,
        })

    def _authenticate(self, user):
        self.client.force_authenticate(Utilisateur.objects.get(pk=user.pk))

    def _search(self, term="search", **params):
        return self.client.get(self.url, {"ressource": "cours", "q": term, **params}, secure=True)

    def _assert_courses(self, user, expected):
        self._authenticate(user)
        search = self._search()
        listing = self.client.get(self.courses_url, secure=True)
        assert search.status_code == listing.status_code == 200
        assert search.data["count"] == listing.data["count"] == len(expected)
        assert search.data["results"] == [
            {"id": mapping.pk, "code": mapping.course_id, "nom": mapping.course_name}
            for mapping in sorted(expected, key=lambda mapping: mapping.pk)
        ]
        expected_ids = {mapping.pk for mapping in expected}
        assert {row["id"] for row in listing.data["results"]} == expected_ids
        for mapping in self.mappings:
            detail = self.client.get(f"{self.courses_url}{mapping.pk}/", secure=True)
            assert detail.status_code == (200 if mapping.pk in expected_ids else 404), detail.data
            if mapping.pk in expected_ids:
                assert detail.data == next(row for row in listing.data["results"] if row["id"] == mapping.pk)
            else:
                assert mapping.course_id not in str(search.data)
                assert mapping.course_name not in str(detail.data)

    def test_course_search_list_and_detail_share_tenant_boundaries_and_minimal_results(self):
        self._assert_courses(self.staff, self.visible)
        for term in (f" {self.active.course_id.lower()} ", f" {self.active.course_name.upper()} "):
            result = self._search(term)
            assert result.status_code == 200
            assert result.data["results"] == [
                {"id": self.active.pk, "code": self.active.course_id, "nom": self.active.course_name}
            ]
        self._classroom("UnmappedNeedle")
        Matiere.objects.create(etablissement=self.tenant, code="UNMAPPED", nom="UnmappedNeedle")
        for term in ("PrivateClass", "PrivateSubject", "UnmappedNeedle", "FOREIGN-"):
            assert self._search(term).data["count"] == 0

    def test_course_admin_access_is_required_and_revocable_not_granted_by_model_permission(self):
        self._assert_courses(self.staff, self.visible)
        self.staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="integration", codename="view_edxcoursemapping")
        )
        self.staff.is_staff = False
        self.staff.save(update_fields=["is_staff"])
        for role in ("enseignant", "direction", "eleve", "parent"):
            self.staff.role = role
            self.staff.save(update_fields=["role"])
            self._authenticate(self.staff)
            assert self._search().status_code == 403
            assert self.client.get(self.courses_url, secure=True).status_code == 403
            assert self.client.get(f"{self.courses_url}{self.active.pk}/", secure=True).status_code == 403
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])
        self._assert_courses(self.staff, self.visible)

    def test_course_read_scopes_only_narrow_existing_administrator_access(self):
        for constraints, expected in (
            ({"cours": [self.active.pk]}, [self.active]),
            ({"classes": [self.inactive.classe_id]}, [self.inactive]),
            ({"matieres": [self.legacy.matiere_id]}, [self.legacy]),
            ({"annees": [self.year.pk]}, self.visible),
            ({"annees": [self.foreign_year.pk]}, []),
            ({"cours": [self.active.pk], "classes": [self.inactive.classe_id]}, []),
            ({"cours": []}, []),
            ({"cours": "all"}, []),
            ({"unsupported": [self.active.pk]}, []),
        ):
            with self.subTest(constraints=constraints):
                self.staff.attributs_acces = {
                    "permission_scopes": {"integration.view_edxcoursemapping": constraints}
                }
                self.staff.save(update_fields=["attributs_acces"])
                self._assert_courses(self.staff, expected)

    def test_current_superuser_cannot_bypass_foreign_course_relations(self):
        self.staff.is_superuser = True
        self.staff.attributs_acces = {"permission_scopes": {"integration.view_edxcoursemapping": {"cours": []}}}
        self.staff.save(update_fields=["is_superuser", "attributs_acces"])
        self._assert_courses(self.staff, self.visible)

    def test_foreign_superuser_inactive_and_anonymous_cannot_read_courses(self):
        foreign = Utilisateur.objects.create_user(
            "course-search-foreign", etablissement=self.other, is_staff=True, is_superuser=True
        )
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        for user in (foreign, self.staff, None):
            if user:
                self._authenticate(user)
            else:
                self.client.force_authenticate(user=None)
            for result in (
                self._search(),
                self.client.get(self.courses_url, secure=True),
                self.client.get(f"{self.courses_url}{self.active.pk}/", secure=True),
            ):
                assert result.status_code in ((403,) if user else (401, 403))
                assert self.active.course_id not in str(result.data)
                assert self.active.course_name not in str(result.data)

    def test_existing_unattached_staff_listing_access_is_preserved(self):
        self.staff.etablissement = None
        self.staff.save(update_fields=["etablissement"])
        self._authenticate(self.staff)
        listing = self.client.get(self.courses_url, secure=True)
        assert listing.status_code == 200
        assert listing.data["count"] == len(self.visible)
        assert self.client.get(f"{self.courses_url}{self.active.pk}/", secure=True).status_code == 200
        assert self._search().status_code == 403

    def test_courses_reject_invalid_queries_and_detail_is_read_only(self):
        self._authenticate(self.staff)
        for term in ("", " ", "a", "x" * 101, " " * 99 + "ab", "ab\n", "a\tb", "ab\x00", "ab\x7f", "ab\x85"):
            with self.subTest(term=term):
                result = self._search(term)
                assert result.status_code == 400
                assert "q" in result.data
        for term in ("ab", "x" * 100):
            assert self._search(term).status_code == 200
        assert self.client.get(self.url, {"ressource": "cours"}, secure=True).status_code == 400
        for resource in ("classes", "matieres", "documents", "cours,eleves"):
            result = self.client.get(self.url, {"ressource": resource, "q": "search"}, secure=True)
            assert result.status_code == 400
        detail_url = f"{self.courses_url}{self.active.pk}/"
        for method in ("post", "put", "patch", "delete"):
            assert getattr(self.client, method)(detail_url, {}, format="json", secure=True).status_code == 405
        assert self.client.get(f"{self.courses_url}0/", secure=True).status_code == 404

    def test_course_pagination_has_stable_pages_default_twenty_and_maximum_fifty(self):
        for index in range(48):
            subject = Matiere.objects.create(
                etablissement=self.tenant, code=f"PAGE-{index}", nom=f"Page {index}"
            )
            self._mapping(f"PAGE-{index:02}", self.classroom, matiere=subject)
        self._authenticate(self.staff)
        first = self._search()
        second = self.client.get(first.data["next"], secure=True)
        assert first.status_code == second.status_code == 200
        assert set(first.data) == {"count", "next", "previous", "results"}
        assert first.data["count"] == second.data["count"] == 51
        assert len(first.data["results"]) == len(second.data["results"]) == 20
        assert first.data["previous"] is None
        assert second.data["previous"] is not None
        assert not {row["id"] for row in first.data["results"]} & {
            row["id"] for row in second.data["results"]
        }
        capped = self._search(page_size=999)
        last = self.client.get(capped.data["next"], secure=True)
        assert capped.status_code == last.status_code == 200
        assert len(capped.data["results"]) == 50
        assert len(last.data["results"]) == 1
        assert last.data["next"] is None
        assert last.data["previous"] is not None
