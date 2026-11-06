"""API tests for core."""

import uuid
from decimal import Decimal

from apps.etablissement.models import AnneeUniversitaire, Universite
from apps.etudiants.models import Etudiant, InscriptionAdministrative
from apps.formations.models import Formation, Parcours
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.paiements.models import FactureFrais, TypeFraisInscription
from apps.structure.models import Departement, Faculte
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context


class MetricsEndpointTestCase(TenantAPITestCase):
    """L'endpoint ``/metrics/`` doit exposer un format Prometheus valide."""

    def test_metrics_returns_prometheus_exposition_format(self):
        response = self.client.get("/metrics/")

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/plain")

        body = response.content.decode("utf-8")
        assert "# HELP sis_users_total" in body
        assert "# TYPE sis_users_total gauge" in body
        assert "sis_users_total " in body
        assert "sis_outbox_events_dead " in body
        assert "sis_metrics_scrape_timestamp_seconds " in body


class CoreAPITestCase(SimpleTestCase):
    def test_academic_search_route_is_registered(self):
        assert resolve("/api/v1/core/recherche-academique/").url_name == "recherche-academique"

    def test_workflow_event_routes_are_registered(self):
        list_match = resolve("/api/v1/core/workflow-events/")
        summary_match = resolve("/api/v1/core/workflow-events/bilan/")
        export_match = resolve("/api/v1/core/workflow-events/exporter/")

        assert list_match.url_name == "workflow-event-list"
        assert summary_match.url_name == "workflow-event-bilan"
        assert export_match.url_name == "workflow-event-exporter"

    def test_notification_routes_are_registered(self):
        list_match = resolve("/api/v1/core/notifications/")
        summary_match = resolve("/api/v1/core/notifications/bilan_livraison/")
        trends_match = resolve("/api/v1/core/notifications/tendances_livraison/")
        read_match = resolve("/api/v1/core/notifications/1/marquer_lue/")
        read_all_match = resolve("/api/v1/core/notifications/tout_marquer_lu/")

        assert list_match.url_name == "notifications-list"
        assert summary_match.url_name == "notifications-bilan-livraison"
        assert trends_match.url_name == "notifications-tendances-livraison"
        assert read_match.url_name == "notifications-marquer-lue"
        assert read_all_match.url_name == "notifications-tout-marquer-lu"


class AcademicSearchAPITests(TenantAPITestCase):
    url = "/api/v1/core/recherche-academique/"

    def _create_student(self, username, universite, surname):
        user = Utilisateur.objects.create_user(username, etablissement=universite, role="etudiant")
        user.first_name = "Anne"
        user.last_name = surname
        user.save(update_fields=["first_name", "last_name"])
        profile = Etudiant.objects.create(
            universite=universite, user=user, matricule=f"SEARCH-{username}",
            date_naissance="2003-01-01", lieu_naissance="Paris", sexe="F",
            adresse="1 rue des Tests", code_postal="75000", ville="Paris", telephone="0100000000",
        )
        return user, profile

    def setUp(self):
        self.user = Utilisateur.objects.create_user("academic_search", etablissement=self.tenant, role="scolarite")
        self.user.user_permissions.add(
            Permission.objects.get(content_type__app_label="formations", codename="view_formation"),
            Permission.objects.get(content_type__app_label="formations", codename="view_parcours"),
        )
        self.client.force_authenticate(self.user)
        other = Universite(
            schema_name=f"other_search_{uuid.uuid4().hex[:12]}",
            nom="Autre université", type="universite_publique",
            adresse="1 rue des Tests", code_postal="75000", ville="Paris",
            telephone="0100000000", email="other@example.test",
        )
        other.auto_create_schema = False
        with schema_context("public"):
            other.save()
        self.other = other
        own_faculty = Faculte.objects.create(universite=self.tenant, nom="Sciences", code="SCI")
        foreign_faculty = Faculte.objects.create(universite=other, nom="Sciences externe", code="EXT")
        self.own_department = Departement.objects.create(faculte=own_faculty, nom="Physique", code="PHY")
        foreign_department = Departement.objects.create(faculte=foreign_faculty, nom="Physique", code="PHY")
        self.own = Formation.objects.create(
            code="PHY-OWN", nom="Physique appliquée", type="licence", departement=self.own_department,
        )
        self.foreign = Formation.objects.create(
            code="PHY-OTHER", nom="Physique externe", type="licence", departement=foreign_department,
        )
        self.own_track = Parcours.objects.create(formation=self.own, code="PHY-TRACK", nom="Physique nucléaire")
        self.foreign_track = Parcours.objects.create(
            formation=self.foreign, code="PHY-OTHER", nom="Physique étrangère",
        )

    def test_results_are_limited_to_own_tenant_and_explicit_columns(self):
        for resource, expected in (("formations", self.own), ("parcours", self.own_track)):
            response = self.client.get(self.url, {"ressource": resource, "q": "physique"})

            assert response.status_code == 200, response.data
            assert response.data["count"] == 1
            assert response.data["results"] == [
                {"id": expected.pk, "code": expected.code, "nom": expected.nom}
            ]

    def test_permission_is_checked_for_each_model(self):
        no_permission = Utilisateur.objects.create_user("no_search_access", etablissement=self.tenant)
        self.client.force_authenticate(no_permission)
        assert self.client.get(self.url, {"ressource": "formations", "q": "physique"}).status_code == 403
        self.client.force_authenticate(self.user)
        self.user.user_permissions.remove(
            Permission.objects.get(content_type__app_label="formations", codename="view_parcours")
        )
        # Clear Django's per-instance permission cache after the grant changes.
        self.user = Utilisateur.objects.get(pk=self.user.pk)
        self.client.force_authenticate(self.user)
        assert self.client.get(self.url, {"ressource": "formations", "q": "physique"}).status_code == 200
        assert self.client.get(self.url, {"ressource": "parcours", "q": "physique"}).status_code == 403

    def test_foreign_tenant_user_cannot_search_even_with_model_permission(self):
        foreign_user = Utilisateur.objects.create_user(
            "foreign_search_access", etablissement=self.other, is_superuser=True,
        )
        self.client.force_authenticate(foreign_user)
        assert self.client.get(self.url, {"ressource": "formations", "q": "physique"}).status_code == 403

    def test_scoped_permission_limits_results(self):
        orphan = Formation.objects.create(code="PHY-ORPHAN", nom="Physique libre", type="licence")
        self.user.attributs_acces = {
            "permission_scopes": {"formations.view_formation": {"departements": [self.own_department.pk]}}
        }
        self.user.save(update_fields=["attributs_acces"])
        response = self.client.get(self.url, {"ressource": "formations", "q": "physique"})

        assert response.status_code == 200, response.data
        assert [row["id"] for row in response.data["results"]] == [self.own.pk]
        assert orphan.pk not in [row["id"] for row in response.data["results"]]

    def test_student_search_requires_validated_enrollment(self):
        student = Utilisateur.objects.create_user(
            "student_search", etablissement=self.tenant, role="etudiant"
        )
        student.user_permissions.add(
            Permission.objects.get(content_type__app_label="formations", codename="view_formation"),
            Permission.objects.get(content_type__app_label="formations", codename="view_parcours"),
        )
        profile = Etudiant.objects.create(
            universite=self.tenant, user=student, matricule="SEARCH-001",
            date_naissance="2003-01-01", lieu_naissance="Paris", sexe="F",
            adresse="1 rue des Tests", code_postal="75000", ville="Paris", telephone="0100000000",
        )
        current_year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-06-30",
        )
        prior_year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2024-2025", date_debut="2024-09-01", date_fin="2025-06-30",
        )
        enrollment = InscriptionAdministrative.objects.create(
            etudiant=profile, formation=self.own, annee_universitaire=current_year,
            date_inscription="2025-09-01", statut="provisoire",
        )
        other_formation = Formation.objects.create(
            code="PHY-OLD", nom="Physique ancienne", type="licence", departement=self.own_department,
        )
        InscriptionAdministrative.objects.create(
            etudiant=profile, formation=other_formation, annee_universitaire=prior_year,
            date_inscription="2024-09-01", statut="validee",
        )
        self.client.force_authenticate(student)

        for state, expected in (
            ("provisoire", []), ("refusee", []), ("annulee", []),
            ("validee", [self.own.pk]),
        ):
            enrollment.statut = state
            enrollment.save(update_fields=["statut"])
            result = self.client.get(self.url, {"ressource": "formations", "q": "appliquée"})
            track_result = self.client.get(self.url, {"ressource": "parcours", "q": "nucléaire"})
            assert result.status_code == track_result.status_code == 200
            assert [row["id"] for row in result.data["results"]] == expected
            assert [row["id"] for row in track_result.data["results"]] == (
                [self.own_track.pk] if state == "validee" else []
            )
        historical = self.client.get(self.url, {"ressource": "formations", "q": "ancienne"})
        assert [row["id"] for row in historical.data["results"]] == [other_formation.pk]

    def test_learner_search_respects_tenant_scope_and_permission_revocation(self):
        _, own = self._create_student("local_a", self.tenant, "Mercier")
        _, peer = self._create_student("local_b", self.tenant, "Mercier")
        self._create_student("foreign_a", self.other, "Mercier")
        permission = Permission.objects.get(content_type__app_label="etudiants", codename="view_etudiant")
        self.user.user_permissions.add(permission)

        result = self.client.get(self.url, {"ressource": "etudiants", "q": "Mercier"})
        assert result.status_code == 200
        assert [row["id"] for row in result.data["results"]] == [own.pk, peer.pk]
        assert result.data["results"][0] == {
            "id": own.pk, "code": own.matricule, "nom": "Anne Mercier",
        }

        self.user.attributs_acces = {
            "permission_scopes": {"etudiants.view_etudiant": {"etudiants": [peer.pk]}}
        }
        self.user.save(update_fields=["attributs_acces"])
        scoped = self.client.get(self.url, {"ressource": "etudiants", "q": "Mercier"})
        assert [row["id"] for row in scoped.data["results"]] == [peer.pk]

        self.user.user_permissions.remove(permission)
        self.user = Utilisateur.objects.get(pk=self.user.pk)
        self.client.force_authenticate(self.user)
        assert self.client.get(self.url, {"ressource": "etudiants", "q": "Mercier"}).status_code == 403

    def test_learner_cannot_search_other_learners_with_model_permission(self):
        user, own = self._create_student("learner_a", self.tenant, "Mercier")
        self._create_student("learner_b", self.tenant, "Durand")
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label="etudiants", codename="view_etudiant")
        )
        self.client.force_authenticate(user)

        result = self.client.get(self.url, {"ressource": "etudiants", "q": "Mercier"})
        assert result.status_code == 200
        assert [row["id"] for row in result.data["results"]] == [own.pk]
        assert self.client.get(self.url, {"ressource": "etudiants", "q": "Durand"}).data["count"] == 0

    def test_invalid_queries_and_unauthenticated_access(self):
        for params in (
            {"ressource": "formations"},
            {"ressource": "formations", "q": " "},
            {"ressource": "formations", "q": "a"},
            {"ressource": "formations", "q": "x" * 101},
            {"ressource": "formations", "q": "physique\n"},
            {"ressource": "unknown", "q": "physique"},
            {"q": "physique"},
        ):
            assert self.client.get(self.url, params).status_code == 400
        self.client.force_authenticate(user=None)
        assert self.client.get(self.url, {"ressource": "formations", "q": "physique"}).status_code in (401, 403)

    def test_results_are_paginated_and_page_size_is_capped(self):
        Formation.objects.bulk_create([
            Formation(code=f"PH-{index:02}", nom="Physique", type="licence", departement=self.own_department)
            for index in range(50)
        ])
        first = self.client.get(self.url, {"ressource": "formations", "q": "physique", "page_size": "999"})
        second = self.client.get(
            self.url, {"ressource": "formations", "q": "physique", "page_size": "999", "page": "2"}
        )

        assert first.status_code == second.status_code == 200
        assert first.data["count"] == second.data["count"] == 51
        assert len(first.data["results"]) == 50
        assert len(second.data["results"]) == 1


class InvoiceSearchAPITests(TenantAPITestCase):
    url = "/api/v1/core/recherche-academique/"
    finance_url = "/api/v1/paiements/factures/"

    def setUp(self):
        self.other = Universite(schema_name=f"invoice_search_{uuid.uuid4().hex[:12]}")
        self.setup_tenant(self.other)
        self.other.auto_create_schema = False
        with schema_context("public"):
            self.other.save()
        self.student_user, self.student = self._learner("owner", self.tenant)
        self.peer_user, self.peer = self._learner("peer", self.tenant)
        self.foreign_user, foreign_student = self._learner("foreign", self.other)
        self.manager = Utilisateur.objects.create_user(
            "invoice-search-manager", role="comptable", etablissement=self.tenant
        )
        self.rubric = self._rubric(self.tenant)
        self.foreign_rubric = self._rubric(self.other)
        self.own = self._invoice(self.student, "SRCH-OWN")
        self.peer_invoice = self._invoice(self.peer, "SRCH-PEER")
        self.foreign_student_invoice = self._invoice(foreign_student, "SRCH-FOREIGN-STUDENT")
        self.foreign_rubric_invoice = self._invoice(self.student, "SRCH-FOREIGN-RUBRIC", self.foreign_rubric)
        self.invoices = [self.own, self.peer_invoice, self.foreign_student_invoice, self.foreign_rubric_invoice]

    def _learner(self, name, tenant):
        user = Utilisateur.objects.create_user(
            f"invoice-search-{name}", role="etudiant", etablissement=tenant, last_name="PrivateSurname"
        )
        student = Etudiant.objects.create(
            universite=tenant, user=user, matricule=f"PRIVATE-{name}",
            date_naissance="2003-01-01", lieu_naissance="Paris", sexe="F",
        )
        return user, student

    def _rubric(self, tenant):
        year = AnneeUniversitaire.objects.create(
            universite=tenant, libelle="Invoice search", date_debut="2025-09-01", date_fin="2026-06-30"
        )
        return TypeFraisInscription.objects.create(
            annee_universitaire=year, code="SEARCH", libelle="PrivateRubric", montant=Decimal("100.00")
        )

    def _invoice(self, student, numero, rubric=None):
        return FactureFrais.objects.create(
            etudiant=student, type_frais=rubric or self.rubric, numero=numero,
            date_emission="2025-09-01", date_echeance="2025-10-01", montant=Decimal("100.00"),
            note="PrivateNote", pdf_path="private/invoice.pdf", qr_paiement="PrivatePaymentIdentifier",
        )

    def _assert_visibility(self, user, expected):
        # A new request must not reuse Django's permission cache after revocation.
        self.client.force_authenticate(Utilisateur.objects.get(pk=user.pk))
        search = self.client.get(self.url, {"ressource": "factures", "q": "srch-"})
        finance = self.client.get(self.finance_url, {"search": "srch-"})
        assert search.status_code == finance.status_code == 200
        assert search.data["count"] == finance.data["count"] == len(expected)
        assert search.data["results"] == [
            {"id": invoice.pk, "code": invoice.numero, "nom": f"Facture {invoice.numero}"}
            for invoice in sorted(expected, key=lambda invoice: invoice.pk)
        ]
        expected_ids = {invoice.pk for invoice in expected}
        assert {row["id"] for row in finance.data["results"]} == expected_ids
        for invoice in self.invoices:
            balance = self.client.get(f"{self.finance_url}{invoice.pk}/solde/")
            assert balance.status_code == (200 if invoice.pk in expected_ids else 404), balance.data
            if invoice.pk not in expected_ids:
                assert invoice.numero not in str(search.data)
                assert invoice.numero not in str(finance.data)
        return search

    def test_owner_search_matches_finance_without_exposing_other_identifiers(self):
        self._assert_visibility(self.student_user, [self.own])
        own = self.client.get(self.url, {"ressource": "factures", "q": " srch-own "})
        assert own.status_code == 200
        assert own.data["results"] == [
            {"id": self.own.pk, "code": self.own.numero, "nom": f"Facture {self.own.numero}"}
        ]
        for term in (
            self.peer_invoice.numero, self.student.matricule, "PrivateSurname", "PrivateRubric",
            "PrivateNote", "PrivatePaymentIdentifier",
        ):
            with self.subTest(term=term):
                result = self.client.get(self.url, {"ressource": "factures", "q": term})
                assert result.status_code == 200
                assert result.data["count"] == 0
                assert result.data["results"] == []

    def test_student_and_doctoral_finance_grants_never_expand_personal_access(self):
        self.student_user.user_permissions.add(
            Permission.objects.get(content_type__app_label="paiements", codename="change_paiementfrais")
        )
        self._assert_visibility(self.student_user, [self.own])
        self.student_user.role = "doctorant"
        self.student_user.is_superuser = True
        self.student_user.save(update_fields=["role", "is_superuser"])
        self._assert_visibility(self.student_user, [self.own])

    def test_local_finance_role_and_explicit_permission_keep_the_same_access(self):
        self._assert_visibility(self.manager, [self.own, self.peer_invoice])
        staff = Utilisateur.objects.create_user(
            "invoice-search-staff", role="enseignant", etablissement=self.tenant, is_staff=True
        )
        staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="paiements", codename="view_facturefrais")
        )
        self._assert_visibility(staff, [])
        permission = Permission.objects.get(content_type__app_label="paiements", codename="change_paiementfrais")
        staff.user_permissions.add(permission)
        self._assert_visibility(staff, [self.own, self.peer_invoice])
        staff.user_permissions.remove(permission)
        self._assert_visibility(staff, [])

    def test_revoked_finance_or_learner_role_cannot_use_a_stale_profile(self):
        for user, expected in (
            (self.manager, [self.own, self.peer_invoice]), (self.student_user, [self.own]),
        ):
            with self.subTest(role=user.role):
                self._assert_visibility(user, expected)
                user.role = "enseignant"
                user.save(update_fields=["role"])
                self._assert_visibility(user, [])

    def test_parent_is_denied_even_with_superuser_and_learner_profile(self):
        self.student_user.role = "parent"
        self.student_user.is_superuser = True
        self.student_user.save(update_fields=["role", "is_superuser"])
        self._assert_visibility(self.student_user, [])

    def test_foreign_or_inactive_finance_actor_cannot_discover_invoice_identifiers(self):
        self.foreign_user.role = "comptable"
        self.foreign_user.is_superuser = True
        self.foreign_user.save(update_fields=["role", "is_superuser"])
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        for user in (self.foreign_user, self.manager):
            with self.subTest(user=user.username):
                self.client.force_authenticate(user)
                search = self.client.get(self.url, {"ressource": "factures", "q": "SRCH-"})
                finance = self.client.get(self.finance_url, {"search": "SRCH-"})
                assert search.status_code == 403
                assert finance.status_code == 200
                assert finance.data["count"] == 0
                assert finance.data["results"] == []
                for invoice in self.invoices:
                    assert invoice.numero not in str(search.data)
                    assert self.client.get(f"{self.finance_url}{invoice.pk}/solde/").status_code == 404

    def test_invoice_read_scopes_only_narrow_finance_and_personal_access(self):
        for constraints, expected in (
            ({"etudiants": [self.peer.pk]}, [self.peer_invoice]),
            ({"factures": [self.own.pk]}, [self.own]),
            ({"rubriques": [self.foreign_rubric.pk]}, []),
            ({"annees": []}, []),
            ({"etudiants": "all"}, []),
            ({"unsupported": [self.own.pk]}, []),
        ):
            with self.subTest(constraints=constraints):
                self.manager.attributs_acces = {
                    "permission_scopes": {"paiements.view_facturefrais": constraints}
                }
                self.manager.save(update_fields=["attributs_acces"])
                self._assert_visibility(self.manager, expected)
        self.student_user.attributs_acces = {
            "permission_scopes": {"paiements.view_facturefrais": {"etudiants": [self.peer.pk]}}
        }
        self.student_user.save(update_fields=["attributs_acces"])
        self._assert_visibility(self.student_user, [])

    def test_finance_permission_scopes_cannot_be_bypassed_by_legacy_role(self):
        self.manager.attributs_acces = {
            "permission_scopes": {"paiements.change_paiementfrais": {"etudiants": [self.student.pk]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        self._assert_visibility(self.manager, [self.own])
        self.manager.user_permissions.add(
            Permission.objects.get(content_type__app_label="paiements", codename="change_paiementfrais")
        )
        # The authoritative finance permission requires context for a scoped grant.
        self._assert_visibility(self.manager, [])

    def test_invoice_search_keeps_query_validation_and_bounded_pagination(self):
        self.client.force_authenticate(self.student_user)
        for term in ("", "a", "x" * 101, "SRCH-\n"):
            assert self.client.get(self.url, {"ressource": "factures", "q": term}).status_code == 400
        FactureFrais.objects.bulk_create([
            FactureFrais(
                etudiant=self.student, type_frais=self.rubric, numero=f"SRCH-PAGE-{index:02}",
                date_emission="2025-09-01", date_echeance="2025-10-01", montant=Decimal("100.00"),
            )
            for index in range(51)
        ])
        for params, length in (({}, 20), ({"page_size": "999"}, 50), ({"page_size": "999", "page": "2"}, 1)):
            result = self.client.get(self.url, {"ressource": "factures", "q": "srch-page", **params})
            assert result.status_code == 200
            assert result.data["count"] == 51
            assert len(result.data["results"]) == length
