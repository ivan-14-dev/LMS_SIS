"""API tests for portail_enseignant."""

from types import SimpleNamespace
from unittest.mock import Mock

from apps.enseignants.models import AffectationEnseignement, EnseignantChercheur
from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.etudiants.models import Etudiant, InscriptionAdministrative, InscriptionPedagogique
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.portail_enseignant.api import PortailEnseignantViewSet
from apps.structure.models import Departement, Faculte
from apps.ue_ecue.models import ECUE, UE
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate


class PortailEnseignantAPITestCase(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(enseignant_profile=object())

    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/tableau_bord/")

        assert match.url_name == "portail-staff-tableau-bord"

    def test_notes_a_saisir_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/notes_a_saisir/")

        assert match.url_name == "portail-staff-notes-a-saisir"

    def test_etudiants_cours_rejects_unassigned_ecue(self):
        request = self.factory.get("/api/v1/portail/enseignant/etudiants_cours/?ecue_id=9")
        request.user = self.user
        request.query_params = request.GET
        view = PortailEnseignantViewSet()
        view.request = request
        view._accessible_ecue_years = lambda _request: {1: {2026}, 2: {2026}}

        response = view.etudiants_cours(request)

        assert response.status_code == 404
        assert response.data["error"] == "ECUE non trouvé ou non autorisé."

    def test_emploi_du_temps_rejects_invalid_week(self):
        request = self.factory.get("/api/v1/portail/enseignant/emploi_du_temps/?semaine=abc")
        request.user = self.user
        request.query_params = request.GET
        view = PortailEnseignantViewSet()
        view.request = request

        response = view.emploi_du_temps(request)

        assert response.status_code == 400
        assert response.data["error"] == "semaine invalide."

    def test_accessible_ecue_years_follow_teaching_assignments(self):
        ecues = Mock()
        ecues.values_list.return_value = [3, 4]
        view = PortailEnseignantViewSet()
        view._affectations_queryset = lambda _teacher: [
            SimpleNamespace(ecue_id=3, ue_id=None, annee_universitaire_id=2024),
            SimpleNamespace(ecue_id=None, ue_id=7, ue=SimpleNamespace(ecues=ecues), annee_universitaire_id=2025),
        ]

        assert view._accessible_ecue_years(SimpleNamespace(user=self.user)) == {
            3: {2024, 2025},
            4: {2025},
        }


class CoursRosterYearTestCase(TenantAPITestCase):
    def test_roster_excludes_other_year_even_with_explicit_semester(self):
        faculty = Faculte.objects.create(universite=self.tenant, nom="Sciences", code="SCI")
        department = Departement.objects.create(faculte=faculty, nom="Math", code="MAT")
        formation = Formation.objects.create(departement=department, nom="Math", code="M", type="licence")
        old_year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2024-2025", date_debut="2024-09-01", date_fin="2025-08-31"
        )
        new_year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2025-2026", date_debut="2025-09-01",
            date_fin="2026-08-31", en_cours=True,
        )
        old_semester = Semestre.objects.create(
            annee_universitaire=old_year, numero=1, type="impair",
            date_debut="2024-09-01", date_fin="2025-01-31",
        )
        new_semester = Semestre.objects.create(
            annee_universitaire=new_year, numero=1, type="impair",
            date_debut="2025-09-01", date_fin="2026-01-31",
        )
        maquette = MaquetteFormation.objects.create(formation=formation, annee_universitaire=old_year)
        ue = UE.objects.create(
            maquette=maquette, code="U1", nom="Analysis", credits_ects=6, semestre=old_semester
        )
        ecue = ECUE.objects.create(ue=ue, code="E1", nom="Calculus", credits_ects=3)
        teacher_user = Utilisateur.objects.create_user(
            username="teacher_roster", role="enseignant", etablissement=self.tenant
        )
        teacher = EnseignantChercheur.objects.create(user=teacher_user, specialite="Math")
        AffectationEnseignement.objects.create(
            enseignant=teacher, ecue=ecue, annee_universitaire=old_year,
            type_enseignement="CM", heures=20,
        )

        def enroll(username, matricule, year, semester):
            user = Utilisateur.objects.create_user(
                username=username, role="etudiant", etablissement=self.tenant
            )
            student = Etudiant.objects.create(
                user=user, universite=self.tenant, matricule=matricule, date_naissance="2000-01-01"
            )
            admin = InscriptionAdministrative.objects.create(
                etudiant=student, formation=formation, annee_universitaire=year,
                date_inscription=year.date_debut,
            )
            pedagogic = InscriptionPedagogique.objects.create(
                inscription_admin=admin, semestre=semester, statut="validee"
            )
            pedagogic.ecues.add(ecue)
            return student

        own = enroll("student_old", "OLD", old_year, old_semester)
        enroll("student_new", "NEW", new_year, new_semester)

        def roster(semester):
            request = APIRequestFactory().get(
                "/", {"ecue_id": ecue.pk, "semestre_id": semester.pk}
            )
            request.tenant = self.tenant
            force_authenticate(request, user=teacher_user)
            return PortailEnseignantViewSet.as_view({"get": "etudiants_cours"})(request)

        response = roster(new_semester)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        response = roster(old_semester)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [own.pk])
