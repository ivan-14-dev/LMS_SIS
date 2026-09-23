"""Tests des tâches Celery d'intégration (outbox, réconciliation) - SIS Secondaire."""

from unittest.mock import MagicMock, patch

from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.models import EdxCourseMapping, EdxUserMapping, OutboxEvent
from apps.integration.tasks import OUTBOX_MAX_ATTEMPTS, publish_outbox_events
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class PublishOutboxEventsTaskTestCase(TenantTestCase):
    """Tests du rejeu réel des événements outbox par ``publish_outbox_events``."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "outbox_user", "outbox_user@test.com", TEST_USER_PASSWORD, role="eleve"
        )

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
        # Le rejeu ne doit pas créer un second événement outbox dupliqué.
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
        mock_client.create_course.return_value = {"id": "course-v1:SIS+MATH001+2024"}
        mock_get_client.return_value = mock_client

        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        niveau = Niveau.objects.create(
            etablissement=self.tenant, code="tale", libelle="Terminale"
        )
        classe = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=annee, niveau=niveau, nom="Terminale S"
        )
        matiere = Matiere.objects.create(
            etablissement=self.tenant, code="MATH", nom="Mathématiques"
        )
        event = OutboxEvent.objects.create(
            event_type="course.create",
            aggregate_type="matiere",
            aggregate_id=str(matiere.id),
            payload={
                "error": "CMS unreachable",
                "classe_id": classe.id,
                "display_name": "Mathématiques",
            },
            statut="pending",
        )

        publish_outbox_events()

        event.refresh_from_db()
        assert event.statut == "done"
        assert EdxCourseMapping.objects.filter(matiere=matiere, classe=classe).exists()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_enrollment_create_event_is_replayed(self, mock_get_client):
        """Un événement enrollment.create rejoué avec succès inscrit l'élève."""
        mock_client = MagicMock()
        mock_client.enroll_user.return_value = {"id": 999}
        mock_get_client.return_value = mock_client

        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        niveau = Niveau.objects.create(
            etablissement=self.tenant, code="tale", libelle="Terminale"
        )
        classe = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=annee, niveau=niveau, nom="Terminale S"
        )
        matiere = Matiere.objects.create(
            etablissement=self.tenant, code="MATH", nom="Mathématiques"
        )
        course_mapping = EdxCourseMapping.objects.create(
            matiere=matiere,
            classe=classe,
            course_id="course-v1:SIS+MATH001+2024",
            course_name="Mathématiques",
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=self.user,
            matricule="MATOUTBOX1",
            date_naissance="2008-01-01",
            lieu_naissance="Paris",
            sexe="M",
            date_inscription="2023-09-01",
        )
        EdxUserMapping.objects.create(user_sis=self.user, username_edx="sis-s-outbox-eleve")
        event = OutboxEvent.objects.create(
            event_type="enrollment.create",
            aggregate_type="eleve",
            aggregate_id=str(eleve.id),
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
            course_mapping.course_id, "sis-s-outbox-eleve", mode="honor"
        )
