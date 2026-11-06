"""API tests for entreprises."""

from datetime import date

from apps.enseignants.models import EnseignantChercheur
from apps.entreprises.models import ContactEntreprise, Entreprise
from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.stages.models import ConventionStage, OffreStage
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class EntreprisesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `entreprises` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/entreprises/entreprises/").url_name == "entreprise-list"
        assert resolve("/api/v1/entreprises/contacts-entreprises/").url_name == "contact-entreprise-list"


class ContactEntrepriseAssociationTestCase(TenantAPITestCase):
    def setUp(self):
        manager = Utilisateur.objects.create_user(
            "entreprise-manager", role="scolarite", etablissement=self.tenant
        )
        self.client.force_authenticate(manager)
        self.entreprise = Entreprise.objects.create(
            raison_sociale="Entreprise A", adresse="1 rue A", code_postal="75000", ville="Paris"
        )
        self.autre_entreprise = Entreprise.objects.create(
            raison_sociale="Entreprise B", adresse="2 rue B", code_postal="75000", ville="Paris"
        )
        self.contact = ContactEntreprise.objects.create(
            entreprise=self.entreprise, nom="Contact", prenom="Test",
            email="contact@example.test", telephone="0100000000",
        )
        student_user = Utilisateur.objects.create_user(
            "entreprise-student", role="etudiant", etablissement=self.tenant
        )
        etudiant = Etudiant.objects.create(
            universite=self.tenant, user=student_user, matricule="ENT-STAGE-01",
            date_naissance=date(2004, 1, 1), lieu_naissance="Paris", sexe="F",
            adresse="1 rue A", code_postal="75000", ville="Paris", telephone="0100000000",
        )
        teacher_user = Utilisateur.objects.create_user(
            "entreprise-teacher", role="enseignant", etablissement=self.tenant
        )
        teacher = EnseignantChercheur.objects.create(user=teacher_user, specialite="Informatique")
        offre = OffreStage.objects.create(
            entreprise=self.entreprise, titre="Stage", type="application", description="Stage",
            duree_mois=2, date_debut=date(2026, 6, 1), date_fin=date(2026, 7, 31),
            date_limite_candidature=date(2026, 5, 1), lieu="Paris",
        )
        self.convention = ConventionStage.objects.create(
            etudiant=etudiant, offre=offre, entreprise=self.entreprise,
            maitre_stage=self.contact, tuteur_pedagogique=teacher,
            date_debut=offre.date_debut, date_fin=offre.date_fin,
            missions="Stage", pdf_path="stages/conventions/test.pdf",
        )

    def test_contact_used_by_convention_cannot_move_to_another_company(self):
        response = self.client.patch(
            f"/api/v1/entreprises/contacts-entreprises/{self.contact.pk}/",
            {"entreprise": self.autre_entreprise.pk}, format="json", secure=True,
        )

        assert response.status_code == 400, response.data
        self.contact.refresh_from_db()
        self.convention.refresh_from_db()
        assert self.contact.entreprise_id == self.convention.entreprise_id == self.entreprise.pk

    def test_unreferenced_contact_can_change_company(self):
        contact = ContactEntreprise.objects.create(
            entreprise=self.entreprise, nom="Libre", prenom="Test",
            email="libre@example.test", telephone="0100000000",
        )
        response = self.client.patch(
            f"/api/v1/entreprises/contacts-entreprises/{contact.pk}/",
            {"entreprise": self.autre_entreprise.pk}, format="json", secure=True,
        )

        assert response.status_code == 200, response.data
        contact.refresh_from_db()
        assert contact.entreprise_id == self.autre_entreprise.pk
