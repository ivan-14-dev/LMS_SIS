"""API tests for memoires."""

from django.test import SimpleTestCase
from django.urls import resolve

from apps.enseignants.models import EnseignantChercheur
from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.memoires.models import Memoire, SujetMemoire
from apps.utilisateurs.models import Utilisateur


class MemoiresAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `memoires` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/memoires/sujets-memoire/").url_name == "sujet-memoire-list"
        assert resolve("/api/v1/memoires/").url_name == "memoire-list"
        assert resolve("/api/v1/memoires/jurys-memoire/").url_name == "jury-memoire-list"


class MemoireValidationTestCase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        agent = Utilisateur.objects.create_user(username="memoire_agent", role="scolarite", etablissement=self.tenant)
        supervisor_user = Utilisateur.objects.create_user(
            username="memoire_supervisor", role="enseignant", etablissement=self.tenant
        )
        supervisor = EnseignantChercheur.objects.create(user=supervisor_user, specialite="Mathématiques")
        student_user = Utilisateur.objects.create_user(
            username="memoire_student", role="etudiant", etablissement=self.tenant
        )
        student = Etudiant.objects.create(
            user=student_user, universite=self.tenant, matricule="MEM-01", date_naissance="2000-01-01"
        )
        year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2024-2025", date_debut="2024-09-01", date_fin="2025-08-31"
        )
        formation = Formation.objects.create(nom="Master", code="MEM", type="master")
        topic = SujetMemoire.objects.create(
            formation=formation,
            annee_universitaire=year,
            titre="Mémoire test",
            description="Sujet",
            encadreur=supervisor,
        )
        self.memoire = Memoire.objects.create(
            sujet=topic, etudiant=student, fichier="memoires/depot.pdf", statut="soumis"
        )
        self.client.force_login(agent)

    def test_validation_cannot_mark_a_memoire_as_defended(self):
        url = f"/api/v1/memoires/{self.memoire.pk}/valider/"

        for decision in ("soutenu", "inconnu"):
            with self.subTest(decision=decision):
                response = self.client.post(url, {"decision": decision}, format="json")
                self.assertEqual(response.status_code, 400)
                self.memoire.refresh_from_db()
                self.assertEqual(self.memoire.statut, "soumis")

        response = self.client.post(url, {"decision": "accepte"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.memoire.refresh_from_db()
        self.assertEqual(self.memoire.statut, "accepte")

    def test_crud_cannot_mark_a_memoire_as_defended(self):
        url = f"/api/v1/memoires/{self.memoire.pk}/"
        response = self.client.patch(url, {"statut": "soutenu"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.memoire.refresh_from_db()
        self.assertEqual(self.memoire.statut, "soumis")

        student_user = Utilisateur.objects.create_user(
            username="memoire_second_student", role="etudiant", etablissement=self.tenant
        )
        student = Etudiant.objects.create(
            user=student_user, universite=self.tenant, matricule="MEM-02", date_naissance="2000-01-01"
        )
        response = self.client.post(
            "/api/v1/memoires/",
            {"sujet": self.memoire.sujet_id, "etudiant": student.pk, "statut": "soutenu"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Memoire.objects.filter(etudiant=student).exists())

    def test_decisions_require_validation_and_terminal_states_cannot_be_resubmitted(self):
        url = f"/api/v1/memoires/{self.memoire.pk}/"
        for statut in ("accepte", "reserve", "refuse", "soutenu"):
            with self.subTest(statut=statut):
                response = self.client.patch(url, {"statut": statut}, format="json")
                self.assertEqual(response.status_code, 400)
                self.memoire.refresh_from_db()
                self.assertEqual(self.memoire.statut, "soumis")

        response = self.client.patch(url, {"statut": "en_relecture"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.memoire.refresh_from_db()
        self.assertEqual(self.memoire.statut, "en_relecture")

        Memoire.objects.filter(pk=self.memoire.pk).update(statut="accepte")
        response = self.client.post(f"{url}soumettre/", format="json")
        self.assertEqual(response.status_code, 400)
        self.memoire.refresh_from_db()
        self.assertEqual(self.memoire.statut, "accepte")

    def test_validation_only_accepts_submitted_review_or_reserved_memoire(self):
        url = f"/api/v1/memoires/{self.memoire.pk}/valider/"

        for statut in ("brouillon", "soutenu", "accepte", "refuse"):
            with self.subTest(statut=statut):
                Memoire.objects.filter(pk=self.memoire.pk).update(statut=statut)
                response = self.client.post(url, {"decision": "accepte"}, format="json")
                self.assertEqual(response.status_code, 400)
                self.memoire.refresh_from_db()
                self.assertEqual(self.memoire.statut, statut)

        for statut, decision in (("soumis", "accepte"), ("en_relecture", "refuse"), ("reserve", "reserve")):
            with self.subTest(statut=statut, decision=decision):
                Memoire.objects.filter(pk=self.memoire.pk).update(statut=statut)
                response = self.client.post(url, {"decision": decision}, format="json")
                self.assertEqual(response.status_code, 200)
                self.memoire.refresh_from_db()
                self.assertEqual(self.memoire.statut, decision)
