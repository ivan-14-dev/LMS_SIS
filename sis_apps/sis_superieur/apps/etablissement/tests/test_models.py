"""Model tests for etablissement."""

import datetime

from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.integration.tests.tenant_test_case import TenantTestCase


class EtablissementModelTestCase(TenantTestCase):
    def test_annee_universitaire_str_returns_libelle(self):
        annee = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 6, 30),
        )

        assert str(annee) == "2026-2027"

    def test_semestre_str_includes_numero_and_annee_universitaire(self):
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

        assert str(semestre) == "S1 - 2026-2027"
        assert semestre.get_type_display() == "Semestre impair (S1, S3, S5)"
