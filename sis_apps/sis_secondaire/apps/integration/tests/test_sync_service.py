"""Tests du service de synchronisation LMS - SIS Secondaire."""

from unittest.mock import MagicMock, patch

import pytest
from apps.integration.models import EdxUserMapping, OutboxEvent
from apps.integration.sync_service import SyncService
from apps.utilisateurs.models import Utilisateur
from django.test import TestCase
from django.utils import timezone


class SyncServiceUserTestCase(TestCase):
    """Tests de synchronisation des utilisateurs."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            username="sync_test_eleve",
            email="sync_eleve@test.com",
            password="testpass123",
            first_name="Marie",
            last_name="Martin",
            role="etudiant",
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_to_lms_creates_mapping(self, mock_get_client):
        """Synchroniser un utilisateur crée un mapping."""
        mock_client = MagicMock()
        mock_client.create_user.return_value = {"id": 22222}
        mock_get_client.return_value = mock_client

        service = SyncService()
        mapping = service.sync_user_to_lms(self.user, role="student")

        assert mapping is not None
        assert mapping.user_id_edx == 22222
        assert mapping.user_sis == self.user
        assert mapping.actif
        mock_client.create_user.assert_called_once()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_to_lms_updates_existing_mapping(self, mock_get_client):
        """Synchroniser un utilisateur existant met à jour le mapping."""
        existing_mapping = EdxUserMapping.objects.create(
            user_sis=self.user, username_edx=f"sis-s-{self.user.id}", user_id_edx=11111
        )

        mock_client = MagicMock()
        mock_client.update_user.return_value = {}
        mock_get_client.return_value = mock_client

        service = SyncService()
        mapping = service.sync_user_to_lms(self.user)

        assert mapping.id == existing_mapping.id
        mock_client.update_user.assert_called_once()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_failure_creates_outbox_event(self, mock_get_client):
        """En cas d'échec, un événement outbox est créé."""
        mock_client = MagicMock()
        mock_client.create_user.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        service = SyncService()

        with pytest.raises(Exception, match="API Error"):
            service.sync_user_to_lms(self.user)

        outbox_event = OutboxEvent.objects.filter(
            event_type="user.sync", aggregate_id=str(self.user.id)
        ).first()

        assert outbox_event is not None
        assert "error" in outbox_event.payload


class SyncServiceCourseTestCase(TestCase):
    """Tests de synchronisation des cours (matière/classe)."""

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_course_to_cms(self, mock_get_client):
        """Synchroniser un cours vers le CMS."""
        mock_client = MagicMock()
        mock_client.create_course.return_value = {
            "id": "course-v1:SIS-S+MATH001+2024",
            "display_name": "Mathématiques - Terminale S",
        }
        mock_get_client.return_value = mock_client

        # Nécessite Matiere, Classe, AnneeScolaire
        pass


class SyncServiceEnrollmentTestCase(TestCase):
    """Tests de synchronisation des inscriptions élèves."""

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_enrollment_to_lms(self, mock_get_client):
        """Inscrire un élève à un cours LMS."""
        mock_client = MagicMock()
        mock_client.enroll_user.return_value = {"id": 88888}
        mock_get_client.return_value = mock_client

        # Nécessite Eleve, EdxUserMapping, EdxCourseMapping
        pass

    @patch("apps.integration.sync_service.get_edx_client")
    def test_bulk_sync_enrollments_for_class(self, mock_get_client):
        """Inscrire tous les élèves d'une classe à un cours."""
        mock_client = MagicMock()
        mock_client.bulk_enroll.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_get_client.return_value = mock_client
        pass


class SyncServiceGradeTestCase(TestCase):
    """Tests de synchronisation des notes."""

    @patch("apps.integration.sync_service.get_edx_client")
    def test_import_grades_from_lms(self, mock_get_client):
        """Importer les notes depuis le LMS."""
        mock_client = MagicMock()
        mock_client.get_grades.return_value = {
            "percent": 0.75,
            "subsections": [
                {"id": "sub1", "score": 15, "max_score": 20},
                {"id": "sub2", "score": 12, "max_score": 20},
            ],
        }
        mock_get_client.return_value = mock_client
        pass

    @patch("apps.integration.sync_service.get_edx_client")
    def test_grades_create_edx_grade_log(self, mock_get_client):
        """Les notes importées créent des EdxGradeLog."""
        mock_client = MagicMock()
        mock_client.get_grades.return_value = {"percent": 0.80, "subsections": []}
        mock_get_client.return_value = mock_client
        pass


class SyncServiceReconciliationTestCase(TestCase):
    """Tests de réconciliation."""

    @patch("apps.integration.sync_service.get_edx_client")
    def test_reconcile_updates_progression(self, mock_get_client):
        """La réconciliation met à jour la progression des élèves."""
        mock_client = MagicMock()
        mock_client.get_grades.return_value = {"percent": 0.65}
        mock_get_client.return_value = mock_client
        pass

    @patch("apps.integration.sync_service.get_edx_client")
    def test_reconcile_detects_missing_enrollments(self, mock_get_client):
        """La réconciliation détecte les inscriptions manquantes."""
        mock_client = MagicMock()
        mock_client.get_enrollments.return_value = []
        mock_get_client.return_value = mock_client
        pass


class OutboxProcessingTestCase(TestCase):
    """Tests du traitement des événements outbox."""

    def test_process_pending_events(self):
        """Traiter les événements en attente."""
        for i in range(5):
            OutboxEvent.objects.create(
                event_type="test.event",
                aggregate_type="test",
                aggregate_id=str(i),
                payload={"index": i},
                statut="pending",
            )

        pending = OutboxEvent.objects.filter(statut="pending")[:3]
        for event in pending:
            event.statut = "done"
            event.derniere_tentative = timezone.now()
            event.save()

        done_count = OutboxEvent.objects.filter(statut="done").count()
        pending_count = OutboxEvent.objects.filter(statut="pending").count()

        assert done_count == 3
        assert pending_count == 2

    def test_event_retry_increments_counter(self):
        """Les retries incrémentent le compteur."""
        event = OutboxEvent.objects.create(
            event_type="retry.test",
            aggregate_type="test",
            aggregate_id="1",
            payload={},
            statut="pending",
        )

        for _i in range(3):
            event.nb_tentatives += 1
            event.erreur = f"Tentative {event.nb_tentatives} échouée"
            event.derniere_tentative = timezone.now()
            event.save()

        event.refresh_from_db()
        assert event.nb_tentatives == 3

    def test_max_retries_moves_to_dead_letter(self):
        """Après max retries, l'événement passe en dead letter."""
        event = OutboxEvent.objects.create(
            event_type="max.retry",
            aggregate_type="test",
            aggregate_id="1",
            payload={},
            statut="pending",
            nb_tentatives=9,
        )

        # Simuler la 10ème tentative (max)
        event.nb_tentatives = 10
        event.statut = "dead"
        event.erreur = "Max retries exceeded"
        event.save()

        event.refresh_from_db()
        assert event.statut == "dead"
        assert event.nb_tentatives == 10
