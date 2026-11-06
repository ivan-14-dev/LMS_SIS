"""API tests for portail_eleve."""

from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve, EleveTuteur, Tuteur
from apps.emplois_du_temps.models import Creneau
from apps.enseignants.models import AffectationEnseignant, Personnel
from apps.etablissement.models import AnneeScolaire, Niveau, Periode
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.notes.models import Bulletin
from apps.portail_eleve.api import PortailEleveViewSet
from apps.portail_enseignant.api import PortailEnseignantViewSet
from apps.portail_parent.api import PortailParentViewSet
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate


class PortailEleveAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/apprenant/tableau_bord/")

        assert match.url_name == "portail-apprenant-tableau-bord"

    def test_bulletins_route_is_registered(self):
        match = resolve("/api/v1/portail/apprenant/bulletins/")

        assert match.url_name == "portail-apprenant-bulletins"


class PortailNiveauTestCase(TenantAPITestCase):
    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut="2026-09-01",
            date_fin="2027-06-30",
        )
        self.niveau = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixieme")
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=self.annee,
            niveau=self.niveau,
            nom="6e A",
        )
        self.user = Utilisateur.objects.create_user(username="portal_learner", role="eleve", etablissement=self.tenant)
        self.eleve = Eleve.objects.create(
            user=self.user,
            etablissement=self.tenant,
            matricule="PORTAL-001",
            date_naissance="2014-01-01",
            date_inscription="2026-09-01",
            sexe="F",
            classe_actuelle=self.classe,
        )
        self.client.force_authenticate(self.user)

    def get_action(self, viewset, action, user, **params):
        request = APIRequestFactory().get("/", params)
        request.tenant = self.tenant
        force_authenticate(request, user=user)
        response = viewset.as_view({"get": action})(request)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_learner_dashboard_and_profile_with_class_level(self):
        response = self.client.get("/api/v1/portail/apprenant/tableau_bord/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["classe"]["niveau"], "Sixieme")
        profile = self.get_action(PortailEleveViewSet, "profil", self.user)
        self.assertEqual(profile["niveau"], "Sixieme")

    def test_learner_without_class_can_open_dashboard_and_profile(self):
        self.eleve.classe_actuelle = None
        self.eleve.save(update_fields=["classe_actuelle"])
        self.user.refresh_from_db()
        response = self.client.get("/api/v1/portail/apprenant/tableau_bord/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["classe"])
        profile = self.get_action(PortailEleveViewSet, "profil", self.user)
        self.assertIsNone(profile["niveau"])

    def test_published_bulletins_include_level_without_exposing_drafts(self):
        for numero, published in ((1, True), (2, False)):
            periode = Periode.objects.create(
                annee_scolaire=self.annee,
                type="trimestre",
                numero=numero,
                libelle=f"Trimestre {numero}",
                date_debut="2026-09-01",
                date_fin="2026-12-31",
            )
            Bulletin.objects.create(eleve=self.eleve, classe=self.classe, periode=periode, publie=published)
        response = self.client.get("/api/v1/portail/apprenant/bulletins/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["niveau"], "Sixieme")
        self.assertEqual(response.data[0]["periode"], "Trimestre 1")

    def test_family_dashboard_and_child_detail_include_level(self):
        parent = Utilisateur.objects.create_user(username="portal_parent", role="parent", etablissement=self.tenant)
        tuteur = Tuteur.objects.create(user=parent, etablissement=self.tenant, lien_parente="tuteur_legal")
        EleveTuteur.objects.create(eleve=self.eleve, tuteur=tuteur)
        self.client.force_authenticate(parent)
        response = self.client.get("/api/v1/portail/apprenant/tableau_bord/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["enfants"][0]["niveau"], "Sixieme")
        child = self.get_action(PortailParentViewSet, "enfant_detail", parent, enfant_id=self.eleve.pk)
        self.assertEqual(child["niveau"], "Sixieme")

    def test_teacher_dashboard_classes_and_timetable_include_level(self):
        teacher = Utilisateur.objects.create_user(
            username="portal_teacher", role="enseignant", etablissement=self.tenant
        )
        personnel = Personnel.objects.create(user=teacher, matricule="TEACHER-001", date_embauche="2026-09-01")
        matiere = Matiere.objects.create(etablissement=self.tenant, code="MATH", nom="Mathematiques")
        affectation = AffectationEnseignant.objects.create(
            enseignant=personnel, matiere=matiere, annee_scolaire=self.annee
        )
        affectation.classes.add(self.classe)
        self.classe.prof_principal = teacher
        self.classe.save(update_fields=["prof_principal"])
        Creneau.objects.create(
            classe=self.classe,
            matiere=matiere,
            enseignant=personnel,
            jour=1,
            heure_debut="08:00",
            heure_fin="09:00",
        )
        self.client.force_authenticate(teacher)
        response = self.client.get("/api/v1/portail/staff/tableau_bord/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["classes"][0]["niveau"], "Sixieme")
        self.assertEqual(response.data["classes_pp"][0]["niveau"], "Sixieme")
        response = self.client.get("/api/v1/portail/staff/mes_classes/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["niveau"], "Sixieme")
        timetable = self.get_action(PortailEnseignantViewSet, "emploi_du_temps", teacher)
        self.assertEqual(timetable[0]["niveau"], "Sixieme")
