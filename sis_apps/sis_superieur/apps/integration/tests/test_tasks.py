"""Tests des tâches Celery d'intégration (outbox, réconciliation) - SIS Supérieur."""

import datetime
from unittest.mock import MagicMock, patch

from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.models import EdxCourseMapping, EdxUserMapping, OutboxEvent
from apps.integration.tasks import OUTBOX_MAX_ATTEMPTS, publish_outbox_events
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.ue_ecue.models import ECUE, UE
from apps.utilisateurs.models import Utilisateur

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class PublishOutboxEventsTaskTestCase(TenantTestCase):
    """Tests du rejeu réel des événements outbox par ``publish_outbox_events``."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "outbox_user", "outbox_user@test.com", TEST_USER_PASSWORD, role="etudiant"
        )

    def _create_ecue_and_annee(self):
        annee = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2023-2024",
            date_debut=datetime.date(2023, 9, 1),
            date_fin=datetime.date(2024, 6, 30),
        )
        semestre = Semestre.objects.create(
            annee_universitaire=annee,
            numero=1,
            type="impair",
            date_debut=datetime.date(2023, 9, 1),
            date_fin=datetime.date(2024, 1, 31),
        )
        formation = Formation.objects.create(
            nom="Licence Informatique", code="LINFO", type="licence"
        )
        maquette = MaquetteFormation.objects.create(
            formation=formation, annee_universitaire=annee
        )
        ue = UE.objects.create(
            maquette=maquette,
            code="UE1",
            nom="Programmation",
            credits_ects=6,
            semestre=semestre,
        )
        ecue = ECUE.objects.create(
            ue=ue, code="ECUE1", nom="Algorithmique", credits_ects=3
        )
        return ecue, annee

    @patch("apps.integration.sync_service.get_edx_client")
    def test_user_sync_event_is_replayed_and_marked_done(self, mock_get_client):
        """Un événement user.sync rejoué avec succès est marqué done, un mapping est créé."""
        mock_client = MagicMock()
        mock_client.create_user.return_value = {"id": 555}
        mock_get_client.return_value = mock_client

        event = OutboxEvent.objects.create(
            event_type="user.sync",
            aggregate_type="user",
            aggregate_id=str(self.user.id),
            payload={"error": "API Error", "role": "student"},
            statut="pending",
        )

        processed = publish_outbox_events()

        assert processed == 1
        event.refresh_from_db()
        assert event.statut == "done"
        mapping = EdxUserMapping.objects.get(user_sis=self.user)
        assert mapping.user_id_edx == 555
        mock_client.create_user.assert_called_once()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_failed_replay_increments_attempts_and_stays_pending(self, mock_get_client):
        """Un rejeu qui échoue encore incrémente les tentatives et repasse en pending."""
        mock_client = MagicMock()
        mock_client.create_user.side_effect = Exception("Still down")
        mock_get_client.return_value = mock_client

        event = OutboxEvent.objects.create(
            event_type="user.sync",
            aggregate_type="user",
            aggregate_id=str(self.user.id),
            payload={"error": "API Error", "role": "student"},
            statut="pending",
        )

        publish_outbox_events()

        event.refresh_from_db()
        assert event.statut == "pending"
        assert event.nb_tentatives == 1
        assert event.erreur == "Still down"
        assert OutboxEvent.objects.filter(event_type="user.sync").count() == 1

    @patch("apps.integration.sync_service.get_edx_client")
    def test_event_moves_to_dead_letter_after_max_attempts(self, mock_get_client):
        """Après OUTBOX_MAX_ATTEMPTS échecs, l'événement passe en dead letter."""
        mock_client = MagicMock()
        mock_client.create_user.side_effect = Exception("Still down")
        mock_get_client.return_value = mock_client

        event = OutboxEvent.objects.create(
            event_type="user.sync",
            aggregate_type="user",
            aggregate_id=str(self.user.id),
            payload={"error": "API Error", "role": "student"},
            statut="pending",
            nb_tentatives=OUTBOX_MAX_ATTEMPTS - 1,
        )

        publish_outbox_events()

        event.refresh_from_db()
        assert event.statut == "dead"
        assert event.nb_tentatives == OUTBOX_MAX_ATTEMPTS

    def test_unknown_event_type_is_marked_dead_eventually(self):
        """Un type d'événement inconnu échoue proprement au lieu de planter la tâche."""
        event = OutboxEvent.objects.create(
            event_type="unknown.type",
            aggregate_type="user",
            aggregate_id=str(self.user.id),
            payload={},
            statut="pending",
        )

        publish_outbox_events()

        event.refresh_from_db()
        assert event.statut == "pending"
        assert event.nb_tentatives == 1
        assert "unknown.type" in event.erreur

    def test_only_pending_events_are_claimed(self):
        """Les événements déjà traités ou morts ne sont pas re-traités."""
        done_event = OutboxEvent.objects.create(
            event_type="user.sync",
            aggregate_type="user",
            aggregate_id=str(self.user.id),
            payload={"role": "student"},
            statut="done",
        )
        dead_event = OutboxEvent.objects.create(
            event_type="user.sync",
            aggregate_type="user",
            aggregate_id=str(self.user.id),
            payload={"role": "student"},
            statut="dead",
            nb_tentatives=OUTBOX_MAX_ATTEMPTS,
        )

        processed = publish_outbox_events()

        assert processed == 0
        done_event.refresh_from_db()
        dead_event.refresh_from_db()
        assert done_event.statut == "done"
        assert dead_event.statut == "dead"

    @patch("apps.integration.sync_service.get_edx_client")
    def test_course_create_event_is_replayed(self, mock_get_client):
        """Un événement course.create rejoué avec succès crée le mapping de cours."""
        mock_client = MagicMock()
        mock_client.create_course.return_value = {"id": "course-v1:SIS-U+ECUE1+2023"}
        mock_get_client.return_value = mock_client

        ecue, annee = self._create_ecue_and_annee()
        event = OutboxEvent.objects.create(
            event_type="course.create",
            aggregate_type="ecue",
            aggregate_id=str(ecue.id),
            payload={
                "error": "CMS unreachable",
                "annee_universitaire_id": annee.id,
                "display_name": "Algorithmique",
            },
            statut="pending",
        )

        publish_outbox_events()

        event.refresh_from_db()
        assert event.statut == "done"
        assert EdxCourseMapping.objects.filter(ecue=ecue).exists()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_enrollment_create_event_is_replayed(self, mock_get_client):
        """Un événement enrollment.create rejoué avec succès inscrit l'étudiant."""
        mock_client = MagicMock()
        mock_client.enroll_user.return_value = {"id": 999}
        mock_get_client.return_value = mock_client

        ecue, _annee = self._create_ecue_and_annee()
        course_mapping = EdxCourseMapping.objects.create(
            ecue=ecue, course_id="course-v1:SIS-U+ECUE1+2023", course_name="Algorithmique"
        )
        etudiant = Etudiant.objects.create(
            universite=self.tenant,
            user=self.user,
            matricule="MATOUTBOX1",
            date_naissance="2002-01-01",
            lieu_naissance="Paris",
            sexe="F",
            adresse="1 rue des Tests",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        EdxUserMapping.objects.create(user_sis=self.user, username_edx="sis-u-outbox-etudiant")
        event = OutboxEvent.objects.create(
            event_type="enrollment.create",
            aggregate_type="etudiant",
            aggregate_id=str(etudiant.id),
            payload={
                "error": "LMS timeout",
                "course_mapping_id": course_mapping.id,
                "mode": "honor",
            },
            statut="pending",
        )

        publish_outbox_events()

        event.refresh_from_db()
        assert event.statut == "done"
        mock_client.enroll_user.assert_called_once_with(
            course_mapping.course_id, "sis-u-outbox-etudiant", mode="honor"
        )
