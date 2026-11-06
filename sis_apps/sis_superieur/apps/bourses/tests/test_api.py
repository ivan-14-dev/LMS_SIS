"""API tests for bourses."""

from apps.bourses.models import AttributionBourse, DemandeBourse, TypeBourse
from apps.bourses.permissions import CanAwardBourse
from apps.etablissement.models import AnneeUniversitaire, Universite
from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory


class BoursesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `bourses` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/bourses/types-bourses/").url_name == "type-bourse-list"
        assert resolve("/api/v1/bourses/demandes-bourses/").url_name == "demande-bourse-list"
        assert resolve("/api/v1/bourses/attributions-bourses/").url_name == "attribution-bourse-list"
        assert resolve("/api/v1/bourses/versements-bourses/").url_name == "versement-bourse-list"


class AttributionEligibilityAPITestCase(TenantAPITestCase):
    def setUp(self):
        self.manager = Utilisateur.objects.create_user(
            "bourses-manager", role="service_social", etablissement=self.tenant
        )
        self.student_user = Utilisateur.objects.create_user(
            "bourses-student", role="etudiant"
        )
        student = Etudiant.objects.create(
            universite=self.tenant,
            user=self.student_user,
            matricule="BOURSE-API-001",
            date_naissance="2002-01-01",
            lieu_naissance="Paris",
            sexe="F",
            adresse="1 rue des Tests",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        self.year = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2025-2026",
            date_debut="2025-09-01",
            date_fin="2026-06-30",
        )
        self.grant_type = TypeBourse.objects.create(
            nom="Bourse sociale", categorie="sociale", montant_mensuel="150.00"
        )
        self.accepted = DemandeBourse.objects.create(
            etudiant=student,
            type_bourse=self.grant_type,
            annee_universitaire=self.year,
            statut="acceptee",
        )
        other_type = TypeBourse.objects.create(
            nom="Bourse au mérite", categorie="merite", montant_mensuel="100.00"
        )
        self.refused = DemandeBourse.objects.create(
            etudiant=student,
            type_bourse=other_type,
            annee_universitaire=self.year,
            statut="refusee",
        )
        self.client.force_authenticate(user=self.manager)

    def _attribution_data(self, demande, numero):
        return {
            "demande": demande.pk,
            "numero_attribution": numero,
            "date_debut": "2025-09-01",
            "date_fin": "2026-06-30",
            "montant_mensuel": "150.00",
            "montant_total": "1500.00",
        }

    def test_direct_creation_requires_accepted_application(self):
        url = "/api/v1/bourses/attributions-bourses/"
        refused = self.client.post(
            url,
            self._attribution_data(self.refused, "ATT-REFUSED"),
            format="json",
            secure=True,
        )
        assert refused.status_code == 400, refused.data
        assert not AttributionBourse.objects.filter(demande=self.refused).exists()

        accepted = self.client.post(
            url,
            self._attribution_data(self.accepted, "ATT-ACCEPTED"),
            format="json",
            secure=True,
        )
        assert accepted.status_code == 201, accepted.data
        assert (
            AttributionBourse.objects.get(demande=self.accepted).pk
            == accepted.data["id"]
        )

    def test_attribution_cannot_be_reassigned_to_refused_application(self):
        attribution = AttributionBourse.objects.create(
            demande=self.accepted,
            numero_attribution="ATT-EXISTING",
            date_debut="2025-09-01",
            date_fin="2026-06-30",
            montant_mensuel="150.00",
            montant_total="1500.00",
        )
        response = self.client.patch(
            f"/api/v1/bourses/attributions-bourses/{attribution.pk}/",
            {"demande": self.refused.pk},
            format="json",
            secure=True,
        )
        assert response.status_code == 400, response.data
        attribution.refresh_from_db()
        assert attribution.demande_id == self.accepted.pk

    def test_awarded_application_cannot_be_refused_afterwards(self):
        AttributionBourse.objects.create(
            demande=self.accepted,
            numero_attribution="ATT-AWARDED",
            date_debut="2025-09-01",
            date_fin="2026-06-30",
            montant_mensuel="150.00",
            montant_total="1500.00",
        )
        response = self.client.post(
            f"/api/v1/bourses/demandes-bourses/{self.accepted.pk}/decision/",
            {"decision": "refusee", "motif": "Révision"},
            format="json",
            secure=True,
        )
        assert response.status_code == 400, response.data
        self.accepted.refresh_from_db()
        assert self.accepted.statut == "acceptee"

    def test_award_total_stays_consistent_on_direct_create_and_partial_update(self):
        url = "/api/v1/bourses/attributions-bourses/"
        invalid = self.client.post(
            url, self._attribution_data(self.accepted, "ATT-MISMATCH") | {"montant_total": "1400.00"},
            format="json", secure=True,
        )
        assert invalid.status_code == 400, invalid.data
        assert "montant_total" in invalid.data
        zero = self.client.post(
            url, self._attribution_data(self.accepted, "ATT-ZERO") | {
                "montant_mensuel": "0.00", "montant_total": "0.00",
            },
            format="json", secure=True,
        )
        assert zero.status_code == 400, zero.data
        assert not AttributionBourse.objects.filter(demande=self.accepted).exists()

        valid = self.client.post(
            url, self._attribution_data(self.accepted, "ATT-VALID"),
            format="json", secure=True,
        )
        assert valid.status_code == 201, valid.data
        detail = f"{url}{valid.data['id']}/"
        mismatch = self.client.patch(detail, {"montant_mensuel": "200.00"}, format="json", secure=True)
        assert mismatch.status_code == 400, mismatch.data
        updated = self.client.patch(
            detail, {"montant_mensuel": "200.00", "montant_total": "2000.00"},
            format="json", secure=True,
        )
        assert updated.status_code == 200, updated.data
        award = AttributionBourse.objects.get(pk=valid.data["id"])
        assert str(award.montant_total) == "2000.00"

    def test_award_action_calculates_total_and_rejects_nonpositive_monthly_amount(self):
        url = f"/api/v1/bourses/demandes-bourses/{self.accepted.pk}/creer_attribution/"
        invalid = self.client.post(
            url, {"date_debut": "2025-09-01", "date_fin": "2026-06-30", "montant_mensuel": "-1.00"},
            format="json", secure=True,
        )
        assert invalid.status_code == 400, invalid.data
        valid = self.client.post(
            url, {"date_debut": "2025-09-01", "date_fin": "2026-06-30", "montant_mensuel": "150.00"},
            format="json", secure=True,
        )
        assert valid.status_code == 201, valid.data
        assert valid.data["montant_total"] == "1500.00"

    def test_student_cannot_create_or_modify_awards(self):
        url = "/api/v1/bourses/attributions-bourses/"
        award = AttributionBourse.objects.create(
            demande=self.accepted,
            numero_attribution="ATT-PROTECTED",
            date_debut="2025-09-01",
            date_fin="2026-06-30",
            montant_mensuel="150.00",
            montant_total="1500.00",
        )
        self.client.force_authenticate(user=self.student_user)
        direct = self.client.post(url, self._attribution_data(self.refused, "ATT-STUDENT"), format="json", secure=True)
        action = self.client.post(
            f"/api/v1/bourses/demandes-bourses/{self.refused.pk}/creer_attribution/",
            {"date_debut": "2025-09-01", "date_fin": "2026-06-30", "montant_mensuel": "150.00"},
            format="json", secure=True,
        )
        patch = self.client.patch(
            f"{url}{award.pk}/", {"montant_total": "100000.00"}, format="json", secure=True,
        )
        assert direct.status_code == 403, direct.data
        assert action.status_code == 403, action.data
        assert patch.status_code == 403, patch.data
        award.refresh_from_db()
        assert str(award.montant_total) == "1500.00"

    def test_unassigned_legacy_role_cannot_award(self):
        unassigned = Utilisateur.objects.create_user(
            "unassigned-social", role="service_social"
        )
        self.client.force_authenticate(user=unassigned)
        response = self.client.post(
            "/api/v1/bourses/attributions-bourses/",
            self._attribution_data(self.accepted, "ATT-UNASSIGNED"),
            format="json", secure=True,
        )
        assert response.status_code == 403, response.data
        assert not AttributionBourse.objects.filter(demande=self.accepted).exists()

    def test_delegated_award_permissions_allow_create_and_update(self):
        delegated = Utilisateur.objects.create_user(
            "delegated-awards", role="personnel_administratif", etablissement=self.tenant,
        )
        delegated.user_permissions.add(
            Permission.objects.get(content_type__app_label="bourses", codename="add_attributionbourse"),
            Permission.objects.get(content_type__app_label="bourses", codename="change_attributionbourse"),
        )
        self.client.force_authenticate(user=delegated)
        url = "/api/v1/bourses/attributions-bourses/"
        created = self.client.post(
            url, self._attribution_data(self.accepted, "ATT-DELEGATED"),
            format="json", secure=True,
        )
        assert created.status_code == 201, created.data
        changed = self.client.patch(
            f"{url}{created.data['id']}/",
            {"montant_mensuel": "200.00", "montant_total": "2000.00"},
            format="json", secure=True,
        )
        assert changed.status_code == 200, changed.data
        self.refused.statut = "acceptee"
        self.refused.save(update_fields=["statut"])
        action = self.client.post(
            f"/api/v1/bourses/demandes-bourses/{self.refused.pk}/creer_attribution/",
            {"date_debut": "2025-09-01", "date_fin": "2026-06-30", "montant_mensuel": "100.00"},
            format="json", secure=True,
        )
        assert action.status_code == 201, action.data
        assert action.data["montant_total"] == "1000.00"

    def test_award_permission_rejects_mismatched_database_schema(self):
        request = APIRequestFactory().post("/api/v1/bourses/attributions-bourses/")
        request.user = self.manager
        request.tenant = self.tenant
        view = type("AwardView", (), {"action": "create"})()
        with schema_context("public"):
            assert not CanAwardBourse().has_permission(request, view)

    def test_foreign_tenant_application_cannot_be_awarded(self):
        foreign = Universite(
            schema_name=f"other_bourses_{self._testMethodName[-8:]}",
            nom="Autre université", type="universite_publique",
            adresse="1 rue des Tests", code_postal="75000", ville="Paris",
            telephone="0100000000", email="other@example.test",
        )
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_manager = Utilisateur.objects.create_user(
            "foreign-social", role="service_social", etablissement=foreign,
        )
        self.client.force_authenticate(user=foreign_manager)
        foreign_direct = self.client.post(
            "/api/v1/bourses/attributions-bourses/",
            self._attribution_data(self.accepted, "ATT-FOREIGN-USER"),
            format="json", secure=True,
        )
        foreign_action = self.client.post(
            f"/api/v1/bourses/demandes-bourses/{self.accepted.pk}/creer_attribution/",
            {"date_debut": "2025-09-01", "date_fin": "2026-06-30", "montant_mensuel": "150.00"},
            format="json", secure=True,
        )
        assert foreign_direct.status_code == 403, foreign_direct.data
        assert foreign_action.status_code == 403, foreign_action.data
        assert not AttributionBourse.objects.filter(demande=self.accepted).exists()
        self.client.force_authenticate(user=self.manager)
        foreign_student = Etudiant.objects.create(
            universite=foreign, user=Utilisateur.objects.create_user("foreign-boursier"),
            matricule="BOURSE-FOREIGN-001",
            date_naissance="2002-01-01", lieu_naissance="Paris", sexe="F",
            adresse="1 rue des Tests", code_postal="75000", ville="Paris",
            telephone="0100000000",
        )
        foreign_year = AnneeUniversitaire.objects.create(
            universite=foreign, libelle="2025-2026",
            date_debut="2025-09-01", date_fin="2026-06-30",
        )
        foreign_application = DemandeBourse.objects.create(
            etudiant=foreign_student, type_bourse=self.grant_type,
            annee_universitaire=foreign_year, statut="acceptee",
        )
        direct = self.client.post(
            "/api/v1/bourses/attributions-bourses/",
            self._attribution_data(foreign_application, "ATT-FOREIGN"),
            format="json", secure=True,
        )
        action = self.client.post(
            f"/api/v1/bourses/demandes-bourses/{foreign_application.pk}/creer_attribution/",
            {"date_debut": "2025-09-01", "date_fin": "2026-06-30", "montant_mensuel": "150.00"},
            format="json", secure=True,
        )
        assert direct.status_code == 400, direct.data
        assert action.status_code == 404, action.data
        assert not AttributionBourse.objects.filter(demande=foreign_application).exists()
