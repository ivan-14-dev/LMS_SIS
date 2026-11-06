"""API tests for presences."""

from types import SimpleNamespace

from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve, EleveTuteur, Tuteur
from apps.emplois_du_temps.models import Creneau
from apps.enseignants.models import Personnel
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.presences.models import Appel, Justificatif, Presence
from apps.presences.serializers import PresenceSaisieSerializer, validate_attendance
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.exceptions import ValidationError


class PresencesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `presences` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/presences/appels/").url_name == "appel-list"
        assert resolve("/api/v1/presences/").url_name == "presence-list"
        assert resolve("/api/v1/presences/justificatifs/").url_name == "justificatif-list"

    def test_attendance_rejects_closed_calls_other_classes_and_other_teachers(self):
        request = SimpleNamespace(
            tenant=SimpleNamespace(pk=1),
            user=SimpleNamespace(pk=10, is_staff=False, role="enseignant"),
        )
        appel = SimpleNamespace(
            statut="ouvert",
            enseignant=SimpleNamespace(user_id=10),
            creneau=SimpleNamespace(
                classe_id=1,
                classe=SimpleNamespace(etablissement_id=1, annee_scolaire=SimpleNamespace(cloturee=False)),
            ),
        )
        validate_attendance(request, appel, SimpleNamespace(classe_actuelle_id=1))
        with self.assertRaises(ValidationError):
            validate_attendance(request, appel, SimpleNamespace(classe_actuelle_id=2))
        appel.enseignant.user_id = 99
        with self.assertRaises(ValidationError):
            validate_attendance(request, appel)
        appel.enseignant.user_id = 10
        appel.statut = "ferme"
        with self.assertRaises(ValidationError):
            validate_attendance(request, appel)

    def test_negative_delays_cannot_enter_bulk_attendance(self):
        serializer = PresenceSaisieSerializer(data={"eleve_id": 1, "retard_minutes": -1})
        assert not serializer.is_valid()
        assert "retard_minutes" in serializer.errors


class JustificatifWorkflowTestCase(TenantAPITestCase):
    def setUp(self):
        teacher = Utilisateur.objects.create_user(
            "attendance-teacher", role="enseignant", etablissement=self.tenant
        )
        self.teacher = Personnel.objects.create(
            user=teacher, matricule="attendance-teacher", date_embauche="2026-01-01"
        )
        parent = Utilisateur.objects.create_user("attendance-parent", role="parent", etablissement=self.tenant)
        tuteur = Tuteur.objects.create(
            etablissement=self.tenant,
            user=parent,
            nom="Parent",
            prenom="Test",
            lien_parente="mere",
            telephone="0100000000",
            email="parent@example.test",
        )
        year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut="2026-09-01",
            date_fin="2027-07-01",
        )
        level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        classe = Classe.objects.create(etablissement=self.tenant, niveau=level, annee_scolaire=year, nom="6A")
        subject = Matiere.objects.create(etablissement=self.tenant, code="MAT", nom="Maths")
        creneau = Creneau.objects.create(
            classe=classe,
            matiere=subject,
            enseignant=self.teacher,
            jour=1,
            heure_debut="08:00",
            heure_fin="09:00",
        )
        pupil_user = Utilisateur.objects.create_user("attendance-pupil", role="eleve", etablissement=self.tenant)
        pupil = Eleve.objects.create(
            etablissement=self.tenant,
            user=pupil_user,
            matricule="ATT-001",
            date_naissance="2013-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
            classe_actuelle=classe,
        )
        EleveTuteur.objects.create(eleve=pupil, tuteur=tuteur, autorise_acces_portail=True)
        appel = Appel.objects.create(creneau=creneau, date="2026-09-07", enseignant=self.teacher)
        self.presence = Presence.objects.create(appel=appel, eleve=pupil, statut="absent")
        self.parent = parent
        self.client.force_authenticate(teacher)
        self.url = "/api/v1/presences/justificatifs/"

    def test_creation_cannot_preapprove_an_absence(self):
        response = self.client.post(
            self.url,
            {"presence": self.presence.pk, "motif": "Maladie", "statut": "accepte"},
            format="json",
        )
        assert response.status_code == 201, response.data
        justificatif = Justificatif.objects.get(presence=self.presence)
        assert justificatif.statut == "en_attente"
        self.presence.refresh_from_db()
        assert self.presence.statut == "absent"

    def test_edit_cannot_preapprove_but_review_action_still_justifies_absence(self):
        created = self.client.post(
            self.url, {"presence": self.presence.pk, "motif": "Maladie"}, format="json"
        )
        assert created.status_code == 201, created.data
        justificatif = Justificatif.objects.get(presence=self.presence)
        detail_url = f"{self.url}{justificatif.pk}/"

        updated = self.client.patch(
            detail_url,
            {
                "motif": "Certificat médical",
                "statut": "accepte",
                "valide_par": self.teacher.pk,
                "date_validation": "2026-09-08T09:00:00Z",
                "commentaire_validation": "Accepté hors revue",
            },
            format="json",
        )
        assert updated.status_code == 200, updated.data
        justificatif.refresh_from_db()
        self.presence.refresh_from_db()
        assert justificatif.motif == "Certificat médical"
        assert justificatif.statut == "en_attente"
        assert justificatif.valide_par_id is None
        assert justificatif.date_validation is None
        assert justificatif.commentaire_validation == ""
        assert self.presence.statut == "absent"

        accepted = self.client.post(f"{detail_url}accepter/", {"commentaire": "Certificat reçu"}, format="json")
        assert accepted.status_code == 200, accepted.data
        justificatif.refresh_from_db()
        self.presence.refresh_from_db()
        assert justificatif.statut == "accepte"
        assert justificatif.commentaire_validation == "Certificat reçu"
        assert self.presence.statut == "absent_justifie"

        self.client.force_authenticate(self.parent)
        assert self.client.get(detail_url).data["statut"] == "accepte"
        assert self.client.patch(detail_url, {"statut": "refuse"}, format="json").status_code == 403
