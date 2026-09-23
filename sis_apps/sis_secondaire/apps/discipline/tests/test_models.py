"""Model tests for discipline."""

import datetime

from apps.discipline.models import Incident
from apps.eleves.models import Eleve
from apps.enseignants.models import Personnel
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class DisciplineModelTestCase(TenantTestCase):
    def test_incident_str_includes_eleve_and_date(self):
        eleve_user = Utilisateur.objects.create_user(
            "eleve_discipline",
            "eleve_discipline@test.com",
            TEST_USER_PASSWORD,
            role="eleve",
            etablissement=self.tenant,
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=eleve_user,
            matricule="MAT-DISC-001",
            date_naissance=datetime.date(2012, 1, 1),
            lieu_naissance="Paris",
            sexe="M",
            date_inscription=datetime.date(2026, 9, 1),
        )
        rapporteur_user = Utilisateur.objects.create_user(
            "rapporteur_discipline",
            "rapporteur_discipline@test.com",
            TEST_USER_PASSWORD,
            role="enseignant",
            etablissement=self.tenant,
        )
        rapporteur = Personnel.objects.create(
            user=rapporteur_user,
            matricule="PERS-DISC-001",
            date_embauche=datetime.date(2020, 9, 1),
        )
        date_incident = datetime.datetime(2026, 10, 5, 10, 0, tzinfo=datetime.timezone.utc)
        incident = Incident.objects.create(
            eleve=eleve,
            date_incident=date_incident,
            type="comportement",
            description="Bavardage en classe.",
            rapporteur=rapporteur,
        )

        assert str(incident) == f"Incident {eleve} - {date_incident}"
