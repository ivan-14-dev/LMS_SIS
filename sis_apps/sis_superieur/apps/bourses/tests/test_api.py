"""API tests for bourses."""

from apps.bourses.models import AttributionBourse, DemandeBourse, TypeBourse
from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class BoursesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `bourses` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/bourses/types-bourses/").url_name == "type-bourse-list"
        assert resolve("/api/v1/bourses/demandes-bourses/").url_name == "demande-bourse-list"
        assert resolve("/api/v1/bourses/attributions-bourses/").url_name == "attribution-bourse-list"
        assert resolve("/api/v1/bourses/versements-bourses/").url_name == "versement-bourse-list"


class AttributionEligibilityAPITestCase(TenantAPITestCase):
    def setUp(self):
        manager = Utilisateur.objects.create_user(
            "bourses-manager", role="service_social"
        )
        student_user = Utilisateur.objects.create_user(
            "bourses-student", role="etudiant"
        )
        student = Etudiant.objects.create(
            universite=self.tenant,
            user=student_user,
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
        self.client.force_authenticate(user=manager)

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
