"""Budget prévisionnel: une saisie interne par poste, sans livre des dépenses."""

from decimal import Decimal

from apps.etablissement.models import AnneeScolaire
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.paiements.models import BudgetPrevisionnel
from apps.utilisateurs.models import Utilisateur
from django_tenants.utils import schema_context


class BudgetPrevisionnelAPITests(TenantAPITestCase):
    def setUp(self):
        manager = Utilisateur.objects.create_user(
            "budget-manager", role="comptable", etablissement=self.tenant
        )
        self.client.force_authenticate(manager)
        self.annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut="2026-09-01",
            date_fin="2027-08-31",
        )
        self.url = "/api/v1/paiements/budgets-previsionnels/"

    def payload(self, **overrides):
        return {
            "annee_scolaire": self.annee.pk,
            "code": "POSTE-LOCAL",
            "libelle": "Équipement pédagogique",
            "montant_prevu": "500.00",
            **overrides,
        }

    def test_manager_can_record_revise_and_close_a_budget(self):
        created = self.client.post(self.url, self.payload(statut="cloture"), format="json")
        assert created.status_code == 201, created.data
        assert created.data["statut"] == "ouvert"
        detail = f"{self.url}{created.data['id']}/"
        assert self.client.get(self.url).data["results"][0]["id"] == created.data["id"]

        updated = self.client.patch(detail, {"montant_prevu": "750.25"}, format="json")
        assert updated.status_code == 200, updated.data
        assert updated.data["montant_prevu"] == "750.25"
        immutable = self.client.patch(detail, {"code": "AUTRE"}, format="json")
        assert immutable.status_code == 400, immutable.data

        closed = self.client.post(f"{detail}cloturer/", format="json")
        assert closed.status_code == 200, closed.data
        assert closed.data["statut"] == "cloture"
        assert self.client.patch(detail, {"montant_prevu": "800.00"}, format="json").status_code == 409
        assert self.client.post(f"{detail}cloturer/", format="json").status_code == 409
        assert BudgetPrevisionnel.objects.get(pk=created.data["id"]).montant_prevu == Decimal("750.25")

    def test_invalid_amounts_and_closed_year_are_rejected(self):
        for amount in ("0", "-1.00", "invalide", "10000000000.00"):
            with self.subTest(amount=amount):
                response = self.client.post(self.url, self.payload(montant_prevu=amount), format="json")
                assert response.status_code == 400, response.data
        created = self.client.post(self.url, self.payload(), format="json")
        assert created.status_code == 201, created.data
        assert self.client.post(self.url, self.payload(), format="json").status_code == 400
        assert self.client.patch(
            f"{self.url}{created.data['id']}/", {"montant_prevu": "-2.00"}, format="json"
        ).status_code == 400
        self.annee.cloturee = True
        self.annee.save(update_fields=["cloturee"])
        assert self.client.post(self.url, self.payload(code="AUTRE"), format="json").status_code == 400
        detail = f"{self.url}{created.data['id']}/"
        assert self.client.patch(detail, {"montant_prevu": "100.00"}, format="json").status_code == 409
        assert self.client.post(f"{detail}cloturer/", format="json").status_code == 409

    def test_foreign_year_and_foreign_record_are_not_accessible(self):
        foreign = type(self.tenant)(schema_name="foreign_budget")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_year = AnneeScolaire.objects.create(
            etablissement=foreign,
            libelle="2026-2027",
            date_debut="2026-09-01",
            date_fin="2027-08-31",
        )
        assert self.client.post(
            self.url, self.payload(annee_scolaire=foreign_year.pk), format="json"
        ).status_code == 400
        foreign_record = BudgetPrevisionnel.objects.create(
            annee_scolaire=foreign_year,
            code="LEGACY",
            libelle="Import non autorisé",
            montant_prevu="50.00",
        )
        assert self.client.get(self.url).data["results"] == []
        detail = f"{self.url}{foreign_record.pk}/"
        assert self.client.get(detail).status_code == 404
        assert self.client.patch(detail, {"montant_prevu": "75.00"}, format="json").status_code == 404
        assert self.client.post(f"{detail}cloturer/", format="json").status_code == 404

        student = Utilisateur.objects.create_user(
            "budget-student", role="eleve", etablissement=self.tenant
        )
        self.client.force_authenticate(student)
        assert self.client.get(self.url).status_code == 403
        assert self.client.post(self.url, self.payload(), format="json").status_code == 403
