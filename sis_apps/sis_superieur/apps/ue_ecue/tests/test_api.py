"""API tests for ue_ecue."""

import datetime

from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.structure.models import Departement, Faculte
from apps.ue_ecue.models import Prerequis, UE
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class UeEcueAPITestCase(SimpleTestCase):
    def test_ue_ecue_history_routes_are_registered(self):
        ue_history = resolve("/api/v1/ue-ecue/ues/1/historique/")
        ecue_history = resolve("/api/v1/ue-ecue/ecues/1/historique/")
        prerequis_history = resolve("/api/v1/ue-ecue/prerequis/1/historique/")

        assert ue_history.url_name == "ue-historique"
        assert ecue_history.url_name == "ecue-historique"
        assert prerequis_history.url_name == "prerequis-historique"


class PrerequisWriteTestCase(TenantAPITestCase):
    def setUp(self):
        faculte = Faculte.objects.create(universite=self.tenant, nom="Sciences", code="FS")
        departement = Departement.objects.create(faculte=faculte, nom="Informatique", code="INFO")
        formation = Formation.objects.create(departement=departement, nom="Informatique", code="INFO")
        annee = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 6, 30),
        )
        semestre = Semestre.objects.create(
            annee_universitaire=annee,
            numero=1,
            type="impair",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 1, 31),
        )
        maquette = MaquetteFormation.objects.create(formation=formation, annee_universitaire=annee)
        self.ue = UE.objects.create(
            maquette=maquette, code="UE1", nom="Algorithmique", credits_ects=6, semestre=semestre
        )
        self.autre_ue = UE.objects.create(
            maquette=maquette, code="UE2", nom="Réseaux", credits_ects=6, semestre=semestre
        )
        agent = Utilisateur.objects.create_user(username="prerequis_agent", role="scolarite", etablissement=self.tenant)
        self.client.force_authenticate(agent)

    def test_create_rejects_self_prerequisite(self):
        response = self.client.post(
            "/api/v1/ue-ecue/prerequis/",
            {"ue_cible": self.ue.pk, "ue_prereq": self.ue.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ue_prereq", response.data)
        self.assertFalse(Prerequis.objects.exists())

    def test_patch_rejects_self_prerequisite_without_changing_valid_link(self):
        prerequisite = Prerequis.objects.create(ue_cible=self.ue, ue_prereq=self.autre_ue)

        response = self.client.patch(
            f"/api/v1/ue-ecue/prerequis/{prerequisite.pk}/",
            {"ue_prereq": self.ue.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ue_prereq", response.data)
        prerequisite.refresh_from_db()
        self.assertEqual(prerequisite.ue_prereq_id, self.autre_ue.pk)
