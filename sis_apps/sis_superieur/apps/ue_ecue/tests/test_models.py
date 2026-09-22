"""Model tests for UE et ECUE."""

import datetime

from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.structure.models import Departement, Faculte
from apps.ue_ecue.models import ECUE, UE


class UeEcueModelTestCase(TenantTestCase):
    def setUp(self):
        faculte = Faculte.objects.create(universite=self.tenant, nom="Sciences", code="FS")
        departement = Departement.objects.create(faculte=faculte, nom="Informatique", code="INFO")
        formation = Formation.objects.create(departement=departement, nom="Licence Informatique", code="LINFO")
        annee = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 6, 30),
        )
        self.semestre = Semestre.objects.create(
            annee_universitaire=annee,
            numero=1,
            type="impair",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 1, 31),
        )
        self.maquette = MaquetteFormation.objects.create(formation=formation, annee_universitaire=annee)

    def test_ue_str_includes_code_and_nom(self):
        ue = UE.objects.create(
            maquette=self.maquette,
            code="UE1",
            nom="Algorithmique",
            credits_ects=6,
            semestre=self.semestre,
        )

        assert str(ue) == "UE1 - Algorithmique"

    def test_ue_volume_horaire_total_sums_cm_td_tp(self):
        ue = UE.objects.create(
            maquette=self.maquette,
            code="UE2",
            nom="Réseaux",
            credits_ects=6,
            semestre=self.semestre,
            volume_horaire_cm=10,
            volume_horaire_td=15,
            volume_horaire_tp=20,
        )

        assert ue.volume_horaire_total == 45

    def test_ecue_str_includes_ue_code_and_ecue_code(self):
        ue = UE.objects.create(
            maquette=self.maquette,
            code="UE3",
            nom="Programmation",
            credits_ects=6,
            semestre=self.semestre,
        )
        ecue = ECUE.objects.create(ue=ue, code="C1", nom="Python", credits_ects=3)

        assert str(ecue) == "UE3.C1 - Python"
