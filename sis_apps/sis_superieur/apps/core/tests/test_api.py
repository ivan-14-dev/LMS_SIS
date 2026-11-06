"""API tests for core."""

import uuid

from apps.etablissement.models import AnneeUniversitaire, Universite
from apps.etudiants.models import Etudiant, InscriptionAdministrative
from apps.formations.models import Formation, Parcours
from apps.integration.tests.tenant_test_case import TenantAPITestCase
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
