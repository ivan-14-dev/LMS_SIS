"""Tests du service de synchronisation LMS - SIS Secondaire."""

from unittest.mock import MagicMock, patch

import pytest
from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.models import EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent
from apps.integration.sync_service import SyncService
from apps.integration.tasks import _reconcile_lms_for_current_schema
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.utils import timezone

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class SyncServiceUserTestCase(TenantTestCase):
    """Tests de synchronisation des utilisateurs."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "sync_test_eleve", "sync_eleve@test.com", TEST_USER_PASSWORD,
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
            service.sync_user_to_lms(self.user, role="teacher")

        outbox_event = OutboxEvent.objects.filter(
            event_type="user.sync", aggregate_id=str(self.user.id)
        ).first()

        assert outbox_event is not None
        assert outbox_event.payload["error"] == "API Error"
        assert outbox_event.payload["role"] == "teacher"

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_failure_not_enqueued_when_enqueue_failures_disabled(
        self, mock_get_client
    ):
        """Le rejeu outbox (enqueue_failures=False) ne recrée pas d'événement."""
        mock_client = MagicMock()
        mock_client.create_user.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        service = SyncService(enqueue_failures=False)

        with pytest.raises(Exception, match="API Error"):
            service.sync_user_to_lms(self.user)

        assert not OutboxEvent.objects.filter(
            event_type="user.sync", aggregate_id=str(self.user.id)
        ).exists()


class SyncServiceCourseTestCase(TenantTestCase):
    """Tests de synchronisation des cours (matière/classe)."""

    def setUp(self):
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        niveau = Niveau.objects.create(
            etablissement=self.tenant, code="tale", libelle="Terminale"
        )
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
        )
        self.matiere = Matiere.objects.create(
            etablissement=self.tenant, code="MATH", nom="Mathématiques"
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_course_to_cms(self, mock_get_client):
        """Synchroniser un cours vers le CMS."""
        mock_client = MagicMock()
        mock_client.create_course.return_value = {
            "id": "course-v1:SIS+MATH001+2024",
            "display_name": "Mathématiques - Terminale S",
        }
        mock_get_client.return_value = mock_client

        service = SyncService()
        mapping = service.sync_course_to_cms(
            self.matiere, self.classe, "Mathématiques - Terminale S"
        )

        assert mapping.matiere == self.matiere
        assert mapping.classe == self.classe
        assert mapping.course_name == "Mathématiques - Terminale S"
        mock_client.create_course.assert_called_once()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_course_to_cms_failure_creates_outbox_event(self, mock_get_client):
        """En cas d'échec, un événement outbox rejouable est créé."""
        mock_client = MagicMock()
        mock_client.create_course.side_effect = Exception("CMS unreachable")
        mock_get_client.return_value = mock_client

        service = SyncService()
        with pytest.raises(Exception, match="CMS unreachable"):
            service.sync_course_to_cms(self.matiere, self.classe, "Mathématiques")

        event = OutboxEvent.objects.get(
            event_type="course.create", aggregate_id=str(self.matiere.id)
        )
        assert event.payload["classe_id"] == self.classe.id
        assert event.payload["display_name"] == "Mathématiques"


class SyncServiceEnrollmentTestCase(TenantTestCase):
    """Tests de synchronisation des inscriptions élèves."""

    def setUp(self):
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        niveau = Niveau.objects.create(
            etablissement=self.tenant, code="tale", libelle="Terminale"
        )
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
        )
        self.matiere = Matiere.objects.create(
            etablissement=self.tenant, code="MATH", nom="Mathématiques"
        )
        self.course_mapping = EdxCourseMapping.objects.create(
            matiere=self.matiere,
            classe=self.classe,
            course_id="course-v1:SIS+MATH001+2024",
            course_name="Mathématiques",
        )
        self.user = Utilisateur.objects.create_user(
            "eleve_enroll", "eleve_enroll@test.com", TEST_USER_PASSWORD, role="eleve"
        )
        self.eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=self.user,
            matricule="MATSYNC1",
            date_naissance="2008-01-01",
            lieu_naissance="Paris",
            sexe="M",
            date_inscription="2023-09-01",
        )
        self.user_mapping = EdxUserMapping.objects.create(
            user_sis=self.user, username_edx="sis-s-eleve-enroll"
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_enrollment_to_lms(self, mock_get_client):
        """Inscrire un élève à un cours LMS."""
        mock_client = MagicMock()
        mock_client.enroll_user.return_value = {"id": 88888}
        mock_get_client.return_value = mock_client

        service = SyncService()
        enrollment = service.sync_enrollment_to_lms(
            self.eleve, self.course_mapping, mode="honor"
        )

        assert enrollment.enrollment_id == 88888
        assert enrollment.is_active
        mock_client.enroll_user.assert_called_once_with(
            self.course_mapping.course_id, self.user_mapping.username_edx, mode="honor"
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_enrollment_failure_creates_outbox_event(self, mock_get_client):
        """En cas d'échec, l'événement outbox contient tout le contexte nécessaire au rejeu."""
        mock_client = MagicMock()
        mock_client.enroll_user.side_effect = Exception("LMS timeout")
        mock_get_client.return_value = mock_client

        service = SyncService()
        with pytest.raises(Exception, match="LMS timeout"):
            service.sync_enrollment_to_lms(self.eleve, self.course_mapping, mode="honor")

        event = OutboxEvent.objects.get(
            event_type="enrollment.create", aggregate_id=str(self.eleve.id)
        )
        assert event.payload["course_mapping_id"] == self.course_mapping.id
        assert event.payload["mode"] == "honor"

    @patch("apps.integration.sync_service.get_edx_client")
    def test_bulk_sync_enrollments_for_class(self, mock_get_client):
        """Inscrire tous les élèves d'une classe à un cours."""
        mock_client = MagicMock()
        mock_client.bulk_enroll.return_value = [{"id": 1}]
        mock_get_client.return_value = mock_client

        service = SyncService()
        enrollments = service.bulk_sync_enrollments_to_lms(
            [self.eleve], self.course_mapping
        )

        assert len(enrollments) == 1
        assert enrollments[0].enrollment_id == 1
        mock_client.bulk_enroll.assert_called_once_with(
            self.course_mapping.course_id, [self.user_mapping.username_edx], mode="audit"
        )


class SyncServiceGradeTestCase(TenantTestCase):
    """Tests de synchronisation des notes."""

    def setUp(self):
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        niveau = Niveau.objects.create(
            etablissement=self.tenant, code="tale", libelle="Terminale"
        )
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
        )
        self.matiere = Matiere.objects.create(
            etablissement=self.tenant, code="MATH", nom="Mathématiques"
        )
        self.course_mapping = EdxCourseMapping.objects.create(
            matiere=self.matiere,
            classe=self.classe,
            course_id="course-v1:SIS+MATH001+2024",
            course_name="Mathématiques",
        )
        self.user = Utilisateur.objects.create_user(
            "eleve_grade", "eleve_grade@test.com", TEST_USER_PASSWORD, role="eleve"
        )
        self.eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=self.user,
            matricule="MATSYNC2",
            date_naissance="2008-01-01",
            lieu_naissance="Paris",
            sexe="M",
            date_inscription="2023-09-01",
        )
        self.user_mapping = EdxUserMapping.objects.create(
            user_sis=self.user, username_edx="sis-s-eleve-grade"
        )
        self.enrollment = EdxEnrollment.objects.create(
            eleve=self.eleve, course=self.course_mapping, is_active=True
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_import_grades_from_lms(self, mock_get_client):
        """Importer les notes depuis le LMS met à jour la progression."""
        mock_client = MagicMock()
        mock_client.get_grades.return_value = {"percent": 0.75}
        mock_get_client.return_value = mock_client

        service = SyncService()
        count = service.import_grades_from_lms(self.course_mapping)

        assert count == 1
        self.enrollment.refresh_from_db()
        assert self.enrollment.progression == 75
        assert self.enrollment.last_sync is not None

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_grade_to_lms_posts_score(self, mock_get_client):
        """Envoyer une note vers le LMS transmet le bon utilisateur EdX."""
        mock_client = MagicMock()
        mock_client.post_grade.return_value = {"success": True}
        mock_get_client.return_value = mock_client

        service = SyncService()
        result = service.sync_grade_to_lms(self.eleve, self.course_mapping, "sub1", 15, 20)

        assert result == {"success": True}
        mock_client.post_grade.assert_called_once_with(
            self.course_mapping.course_id, self.user_mapping.username_edx, "sub1", 15, 20
        )


class SyncServiceReconciliationTestCase(TenantTestCase):
    """Tests de réconciliation."""

    def setUp(self):
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        niveau = Niveau.objects.create(
            etablissement=self.tenant, code="tale", libelle="Terminale"
        )
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
        )
        self.matiere = Matiere.objects.create(
            etablissement=self.tenant, code="MATH", nom="Mathématiques"
        )
        self.course_mapping = EdxCourseMapping.objects.create(
            matiere=self.matiere,
            classe=self.classe,
            course_id="course-v1:SIS+MATH001+2024",
            course_name="Mathématiques",
        )
        self.user_ok = Utilisateur.objects.create_user(
            "eleve_reconcile_ok", "eleve_reconcile_ok@test.com", TEST_USER_PASSWORD, role="eleve"
        )
        self.eleve_ok = Eleve.objects.create(
            etablissement=self.tenant,
            user=self.user_ok,
            matricule="MATREC1",
            date_naissance="2008-01-01",
            lieu_naissance="Paris",
            sexe="M",
            date_inscription="2023-09-01",
        )
        EdxUserMapping.objects.create(
            user_sis=self.user_ok, username_edx="sis-s-eleve-reconcile-ok"
        )
        self.enrollment_ok = EdxEnrollment.objects.create(
            eleve=self.eleve_ok, course=self.course_mapping, is_active=True
        )

        self.user_missing_mapping = Utilisateur.objects.create_user(
            "eleve_reconcile_missing", "eleve_reconcile_missing@test.com", TEST_USER_PASSWORD, role="eleve"
        )
        self.eleve_missing_mapping = Eleve.objects.create(
            etablissement=self.tenant,
            user=self.user_missing_mapping,
            matricule="MATREC2",
            date_naissance="2008-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2023-09-01",
        )
        # Pas de EdxUserMapping pour cet élève : simule une inscription LMS
        # incomplète que la réconciliation doit ignorer sans planter.
        self.enrollment_missing_mapping = EdxEnrollment.objects.create(
            eleve=self.eleve_missing_mapping, course=self.course_mapping, is_active=True
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_reconcile_updates_progression(self, mock_get_client):
        """La réconciliation met à jour la progression des élèves synchronisés."""
        mock_client = MagicMock()
        mock_client.get_grades.return_value = {"percent": 0.65}
        mock_get_client.return_value = mock_client

        _reconcile_lms_for_current_schema()

        self.enrollment_ok.refresh_from_db()
        assert self.enrollment_ok.progression == 65
        mock_client.get_grades.assert_called_once()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_reconcile_skips_enrollment_without_mapping_without_raising(
        self, mock_get_client
    ):
        """Une inscription sans mapping EdX est ignorée, pas de propagation d'erreur."""
        mock_client = MagicMock()
        mock_client.get_grades.return_value = {"percent": 0.65}
        mock_get_client.return_value = mock_client

        _reconcile_lms_for_current_schema()

        self.enrollment_missing_mapping.refresh_from_db()
        assert self.enrollment_missing_mapping.progression == 0
        assert self.enrollment_missing_mapping.last_sync is None
        # L'inscription valide continue d'être traitée malgré l'échec de l'autre.
        self.enrollment_ok.refresh_from_db()
        assert self.enrollment_ok.progression == 65


class OutboxProcessingTestCase(TenantTestCase):
    """Tests du traitement des événements outbox (utilitaires bas niveau)."""

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
