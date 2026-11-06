"""API tests for rattrapages."""

from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context

from apps.etablissement.models import AnneeUniversitaire, Semestre, Universite
from apps.etudiants.models import (
    AffectationECUEIndividuelle,
    Etudiant,
    InscriptionAdministrative,
    InscriptionPedagogique,
)
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
        self.student = Etudiant.objects.create(
            user=student_user, universite=self.tenant, matricule="RET-01", date_naissance="2000-01-01"
        )
        self.year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2026-2027", date_debut="2026-09-01", date_fin="2027-08-31"
        )
        self.semester = Semestre.objects.create(
            annee_universitaire=self.year, numero=1, type="impair",
            date_debut="2026-09-01", date_fin="2027-01-31",
        )
        self.formation = Formation.objects.create(nom="Licence", code="RET", type="licence")
        maquette = MaquetteFormation.objects.create(formation=self.formation, annee_universitaire=self.year)
        self.ue = UE.objects.create(
            maquette=maquette, semestre=self.semester, code="UE1", nom="UE", credits_ects=6,
        )
        self.ecue = ECUE.objects.create(ue=self.ue, code="EC1", nom="ECUE", credits_ects=6)
        self.ia = InscriptionAdministrative.objects.create(
            etudiant=self.student, annee_universitaire=self.year, formation=self.formation,
            date_inscription="2026-09-10", statut="validee",
        )
        self.ip = InscriptionPedagogique.objects.create(
            inscription_admin=self.ia, semestre=self.semester, statut="validee",
        )
        self.ip.ues.add(self.ue)
        self.normal_session = SessionExamen.objects.create(
            semestre=self.semester, numero=1, type="normale",
            date_debut="2027-01-10", date_fin="2027-01-15",
        )
        self.retake_session = SessionExamen.objects.create(
            semestre=self.semester, numero=2, type="rattrapage",
            date_debut="2027-01-20", date_fin="2027-01-25",
        )
        self.payload = {
            "etudiant": self.student.pk,
            "ecue": self.ecue.pk,
            "date_echeance_inscription": "2027-01-18",
            "session_rattrapage": self.retake_session.pk,
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

    def test_validated_registration_succeeds_once_and_replay_is_rejected(self):
        created = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)

        replay = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(replay.status_code, 400, replay.data)
        self.assertEqual(InscriptionRattrapage.objects.count(), 1)

    def test_read_endpoints_only_expose_a_students_own_registrations(self):
        other_user = Utilisateur.objects.create_user(
            username="retake-other-student", role="etudiant", etablissement=self.tenant
        )
        other_student = Etudiant.objects.create(
            user=other_user, universite=self.tenant, matricule="RET-02",
            date_naissance="2000-01-01",
        )
        other_ia = InscriptionAdministrative.objects.create(
            etudiant=other_student, annee_universitaire=self.year, formation=self.formation,
            date_inscription="2026-09-10", statut="validee",
        )
        other_ip = InscriptionPedagogique.objects.create(
            inscription_admin=other_ia, semestre=self.semester, statut="validee",
        )
        other_ip.ues.add(self.ue)
        own = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        other = self.client.post(
            "/api/v1/rattrapages/",
            {**self.payload, "etudiant": other_student.pk}, format="json",
        )
        self.assertEqual(own.status_code, 201, own.data)
        self.assertEqual(other.status_code, 201, other.data)

        self.client.force_authenticate(self.student.user)
        own_list = self.client.get("/api/v1/rattrapages/")
        self.assertEqual(own_list.status_code, 200, own_list.data)
        self.assertEqual([row["id"] for row in own_list.data["results"]], [own.data["id"]])
        self.assertEqual(
            self.client.get(f"/api/v1/rattrapages/{own.data['id']}/").status_code, 200
        )
        self.assertEqual(
            self.client.get(f"/api/v1/rattrapages/{other.data['id']}/").status_code, 404
        )
        filtered = self.client.get("/api/v1/rattrapages/", {"etudiant": other_student.pk})
        self.assertEqual(filtered.status_code, 200, filtered.data)
        self.assertEqual(filtered.data["results"], [])
        pending = self.client.get("/api/v1/rattrapages/en_attente/")
        self.assertEqual(pending.status_code, 200, pending.data)
        self.assertEqual([row["id"] for row in pending.data], [own.data["id"]])

        outsider = Utilisateur.objects.create_user(
            username="retake-outsider", role="enseignant", etablissement=self.tenant
        )
        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.get("/api/v1/rattrapages/").data["results"], [])
        self.assertEqual(
            self.client.get(f"/api/v1/rattrapages/{own.data['id']}/").status_code, 404
        )
        self.assertEqual(self.client.get("/api/v1/rattrapages/en_attente/").data, [])

        manager = Utilisateur.objects.create_user(
            username="retake-manager", role="scolarite", etablissement=self.tenant
        )
        self.client.force_authenticate(manager)
        managed = self.client.get("/api/v1/rattrapages/")
        self.assertEqual(managed.status_code, 200, managed.data)
        self.assertEqual(
            {row["id"] for row in managed.data["results"]},
            {own.data["id"], other.data["id"]},
        )
        self.assertEqual(
            self.client.get(f"/api/v1/rattrapages/{other.data['id']}/").status_code, 200
        )

    def test_foreign_manager_cannot_create_a_registration_in_the_current_tenant(self):
        foreign = Universite(
            schema_name="foreign_retake_manager", nom="Autre université",
            type="universite_publique", adresse="1 rue des Tests", code_postal="75000",
            ville="Paris", telephone="0100000000", email="other-manager@example.test",
        )
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_manager = Utilisateur.objects.create_user(
            username="foreign-retake-manager", role="scolarite", etablissement=foreign
        )
        local_manager = Utilisateur.objects.create_user(
            username="local-retake-manager", role="scolarite", etablissement=self.tenant
        )

        self.client.force_authenticate(foreign_manager)
        denied = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(denied.status_code, 403, denied.data)
        self.assertFalse(InscriptionRattrapage.objects.exists())

        self.client.force_authenticate(local_manager)
        allowed = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(allowed.status_code, 201, allowed.data)
        self.assertEqual(InscriptionRattrapage.objects.count(), 1)

    def test_refuses_unvalidated_or_unrelated_registration(self):
        self.ip.statut = "soumise"
        self.ip.save(update_fields=["statut"])
        pending = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(pending.status_code, 400, pending.data)
        self.assertIn("etudiant", pending.data)

        self.ip.statut = "validee"
        self.ip.save(update_fields=["statut"])
        self.ia.statut = "provisoire"
        self.ia.save(update_fields=["statut"])
        provisional = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(provisional.status_code, 400, provisional.data)

        self.ia.statut = "validee"
        self.ia.save(update_fields=["statut"])
        other_ue = UE.objects.create(
            maquette=self.ue.maquette, semestre=self.semester,
            code="UE2", nom="Autre UE", credits_ects=6,
        )
        other_ecue = ECUE.objects.create(ue=other_ue, code="EC2", nom="Autre ECUE", credits_ects=6)
        unrelated = self.client.post(
            "/api/v1/rattrapages/", {**self.payload, "ecue": other_ecue.pk}, format="json",
        )
        self.assertEqual(unrelated.status_code, 400, unrelated.data)
        self.assertIn("etudiant", unrelated.data)
        self.assertFalse(InscriptionRattrapage.objects.exists())

    def test_individual_ecue_assignment_is_accepted(self):
        self.ip.delete()
        AffectationECUEIndividuelle.objects.create(
            inscription_admin=self.ia, semestre_cible=self.semester, ecue=self.ecue,
        )
        response = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_refuses_another_formations_ecue_even_when_added_to_ip_or_assigned(self):
        other_formation = Formation.objects.create(
            nom="Autre licence", code="RET-OTHER", type="licence",
        )
        other_maquette = MaquetteFormation.objects.create(
            formation=other_formation, annee_universitaire=self.year,
        )
        other_ue = UE.objects.create(
            maquette=other_maquette, semestre=self.semester,
            code="UE-OTHER", nom="UE externe", credits_ects=6,
        )
        other_ecue = ECUE.objects.create(
            ue=other_ue, code="EC-OTHER", nom="ECUE externe", credits_ects=6,
        )
        self.ip.ues.add(other_ue)
        foreign_payload = {**self.payload, "ecue": other_ecue.pk}
        through_ip = self.client.post("/api/v1/rattrapages/", foreign_payload, format="json")
        self.assertEqual(through_ip.status_code, 400, through_ip.data)
        self.assertIn("etudiant", through_ip.data)

        self.ip.ues.remove(other_ue)
        AffectationECUEIndividuelle.objects.create(
            inscription_admin=self.ia, semestre_cible=self.semester, ecue=other_ecue,
        )
        through_assignment = self.client.post(
            "/api/v1/rattrapages/", foreign_payload, format="json",
        )
        self.assertEqual(through_assignment.status_code, 400, through_assignment.data)
        self.assertIn("etudiant", through_assignment.data)
        self.assertFalse(InscriptionRattrapage.objects.exists())

        same_formation = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(same_formation.status_code, 201, same_formation.data)

    def test_refuses_different_semester_or_university_on_create_and_update(self):
        other_semester = Semestre.objects.create(
            annee_universitaire=self.year, numero=2, type="pair",
            date_debut="2027-02-01", date_fin="2027-06-30",
        )
        other_session = SessionExamen.objects.create(
            semestre=other_semester, numero=2, type="rattrapage",
            date_debut="2027-06-20", date_fin="2027-06-25",
        )
        wrong_semester = self.client.post(
            "/api/v1/rattrapages/",
            {**self.payload, "session_rattrapage": other_session.pk}, format="json",
        )
        self.assertEqual(wrong_semester.status_code, 400, wrong_semester.data)
        self.assertIn("ecue", wrong_semester.data)

        foreign = Universite(
            schema_name="foreign_retake_eligibility", nom="Autre université",
            type="universite_publique", adresse="1 rue des Tests", code_postal="75000",
            ville="Paris", telephone="0100000000", email="other@example.test",
        )
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        self.student.universite = foreign
        self.student.save(update_fields=["universite"])
        wrong_university = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(wrong_university.status_code, 400, wrong_university.data)
        self.assertIn("ecue", wrong_university.data)

        foreign_year = AnneeUniversitaire.objects.create(
            universite=foreign, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )
        foreign_semester = Semestre.objects.create(
            annee_universitaire=foreign_year, numero=1, type="impair",
            date_debut="2026-09-01", date_fin="2027-01-31",
        )
        foreign_maquette = MaquetteFormation.objects.create(
            formation=self.formation, annee_universitaire=foreign_year,
        )
        foreign_ue = UE.objects.create(
            maquette=foreign_maquette, semestre=foreign_semester,
            code="UE-FOREIGN", nom="UE externe", credits_ects=6,
        )
        foreign_ecue = ECUE.objects.create(
            ue=foreign_ue, code="EC-FOREIGN", nom="ECUE externe", credits_ects=6,
        )
        foreign_ia = InscriptionAdministrative.objects.create(
            etudiant=self.student, formation=self.formation, annee_universitaire=foreign_year,
            date_inscription="2026-09-10", statut="validee",
        )
        foreign_ip = InscriptionPedagogique.objects.create(
            inscription_admin=foreign_ia, semestre=foreign_semester, statut="validee",
        )
        foreign_ip.ues.add(foreign_ue)
        foreign_session = SessionExamen.objects.create(
            semestre=foreign_semester, numero=2, type="rattrapage",
            date_debut="2027-01-20", date_fin="2027-01-25",
        )
        foreign_registration = self.client.post(
            "/api/v1/rattrapages/",
            {**self.payload, "ecue": foreign_ecue.pk, "session_rattrapage": foreign_session.pk},
            format="json",
        )
        self.assertEqual(foreign_registration.status_code, 400, foreign_registration.data)
        self.assertIn("ecue", foreign_registration.data)

        self.student.universite = self.tenant
        self.student.save(update_fields=["universite"])

        created = self.client.post("/api/v1/rattrapages/", self.payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        invalid_update = self.client.patch(
            f"/api/v1/rattrapages/{created.data['id']}/",
            {"session_rattrapage": other_session.pk}, format="json",
        )
        self.assertEqual(invalid_update.status_code, 400, invalid_update.data)
        self.assertEqual(InscriptionRattrapage.objects.get().session_rattrapage, self.retake_session)
