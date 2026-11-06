"""API tests for rattrapages."""

from django.test import SimpleTestCase
from django.urls import resolve

from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.etudiants.models import Etudiant
from apps.examens.models import SessionExamen
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.rattrapages.models import InscriptionRattrapage
from apps.ue_ecue.models import ECUE, UE
from apps.utilisateurs.models import Utilisateur


class RattrapagesAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `rattrapages` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/rattrapages/").url_name == "inscription-rattrapage-list"


class RattrapageSessionValidationTestCase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        agent = Utilisateur.objects.create_superuser(
            username="retake-agent", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(agent)
        student_user = Utilisateur.objects.create_user(
            username="retake-student", role="etudiant", etablissement=self.tenant
        )
        student = Etudiant.objects.create(
            user=student_user, universite=self.tenant, matricule="RET-01", date_naissance="2000-01-01"
        )
        year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2026-2027", date_debut="2026-09-01", date_fin="2027-08-31"
        )
        semester = Semestre.objects.create(
            annee_universitaire=year, numero=1, type="impair", date_debut="2026-09-01", date_fin="2027-01-31"
        )
        formation = Formation.objects.create(nom="Licence", code="RET", type="licence")
        maquette = MaquetteFormation.objects.create(formation=formation, annee_universitaire=year)
        ue = UE.objects.create(maquette=maquette, semestre=semester, code="UE1", nom="UE", credits_ects=6)
        ecue = ECUE.objects.create(ue=ue, code="EC1", nom="ECUE", credits_ects=6)
        self.normal_session = SessionExamen.objects.create(
            semestre=semester, numero=1, type="normale", date_debut="2027-01-10", date_fin="2027-01-15"
        )
        self.retake_session = SessionExamen.objects.create(
            semestre=semester, numero=2, type="rattrapage", date_debut="2027-01-20", date_fin="2027-01-25"
        )
        self.payload = {
            "etudiant": student.pk,
            "ecue": ecue.pk,
            "date_echeance_inscription": "2027-01-18",
        }

    def test_normal_exam_session_cannot_be_used_for_a_retake(self):
        response = self.client.post(
            "/api/v1/rattrapages/",
            {**self.payload, "session_rattrapage": self.normal_session.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("session_rattrapage", response.data)
        self.assertFalse(InscriptionRattrapage.objects.exists())

        valid = self.client.post(
            "/api/v1/rattrapages/",
            {**self.payload, "session_rattrapage": self.retake_session.pk},
            format="json",
        )
        self.assertEqual(valid.status_code, 201, valid.data)
        self.assertEqual(InscriptionRattrapage.objects.get().session_rattrapage, self.retake_session)

        update = self.client.patch(
            f"/api/v1/rattrapages/{valid.data['id']}/",
            {"session_rattrapage": self.normal_session.pk},
            format="json",
        )
        self.assertEqual(update.status_code, 400, update.data)
        self.assertIn("session_rattrapage", update.data)
        self.assertEqual(InscriptionRattrapage.objects.get().session_rattrapage, self.retake_session)
