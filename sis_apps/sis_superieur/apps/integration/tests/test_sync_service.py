"""Tests du service de synchronisation LMS - SIS Supérieur."""

import datetime
from unittest.mock import MagicMock, patch

import pytest
from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.models import EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent
from apps.integration.sync_service import SyncService
from apps.integration.tasks import _reconcile_lms_for_current_schema
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.ue_ecue.models import ECUE, UE
from apps.utilisateurs.models import Utilisateur
from django.utils import timezone

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class CourseFixtureMixin:
    """Construit le graphe d'objets minimal requis pour obtenir un ``ECUE``."""

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


class SyncServiceUserTestCase(TenantTestCase):
    """Tests de synchronisation des utilisateurs."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "sync_test_user", "sync@test.com", TEST_USER_PASSWORD,
            first_name="Sync",
            last_name="Test",
            role="etudiant",
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_to_lms_creates_mapping(self, mock_get_client):
        """Synchroniser un utilisateur crée un mapping."""
        mock_client = MagicMock()
        mock_client.create_user.return_value = {"id": 12345}
        mock_get_client.return_value = mock_client

        service = SyncService()
        mapping = service.sync_user_to_lms(self.user, role="student")

        assert mapping is not None
        assert mapping.user_id_edx == 12345
        assert mapping.user_sis == self.user
        assert mapping.actif
        mock_client.create_user.assert_called_once()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_to_lms_updates_existing_mapping(self, mock_get_client):
        """Synchroniser un utilisateur existant met à jour le mapping."""
        existing_mapping = EdxUserMapping.objects.create(
            user_sis=self.user, username_edx=f"sis-u-{self.user.id}", user_id_edx=11111
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


class SyncServiceCourseTestCase(CourseFixtureMixin, TenantTestCase):
    """Tests de synchronisation des cours."""

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_course_to_cms(self, mock_get_client):
        """Synchroniser un cours vers le CMS."""
        mock_client = MagicMock()
        mock_client.create_course.return_value = {
            "id": "course-v1:SIS-U+ECUE1+2023",
            "display_name": "Algorithmique",
        }
        mock_get_client.return_value = mock_client

        ecue, annee = self._create_ecue_and_annee()
        service = SyncService()
        mapping = service.sync_course_to_cms(ecue, annee, "Algorithmique")

        assert mapping.ecue == ecue
        assert mapping.course_name == "Algorithmique"
        mock_client.create_course.assert_called_once()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_course_to_cms_failure_creates_outbox_event(self, mock_get_client):
        """En cas d'échec, un événement outbox rejouable est créé."""
        mock_client = MagicMock()
        mock_client.create_course.side_effect = Exception("CMS unreachable")
        mock_get_client.return_value = mock_client

        ecue, annee = self._create_ecue_and_annee()
        service = SyncService()
        with pytest.raises(Exception, match="CMS unreachable"):
            service.sync_course_to_cms(ecue, annee, "Algorithmique")

        event = OutboxEvent.objects.get(event_type="course.create", aggregate_id=str(ecue.id))
        assert event.payload["annee_universitaire_id"] == annee.id
        assert event.payload["display_name"] == "Algorithmique"


class SyncServiceEnrollmentTestCase(CourseFixtureMixin, TenantTestCase):
    """Tests de synchronisation des inscriptions."""

    def setUp(self):
        ecue, annee = self._create_ecue_and_annee()
        self.course_mapping = EdxCourseMapping.objects.create(
            ecue=ecue, course_id="course-v1:SIS-U+ECUE1+2023", course_name="Algorithmique"
        )
        self.user = Utilisateur.objects.create_user(
            "etudiant_enroll", "etudiant_enroll@test.com", TEST_USER_PASSWORD, role="etudiant"
        )
        self.etudiant = Etudiant.objects.create(
            universite=self.tenant,
            user=self.user,
            matricule="MATSYNC1",
            date_naissance="2002-01-01",
            lieu_naissance="Paris",
            sexe="F",
            adresse="1 rue des Tests",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        self.user_mapping = EdxUserMapping.objects.create(
            user_sis=self.user, username_edx="sis-u-etudiant-enroll"
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_enrollment_to_lms(self, mock_get_client):
        """Inscrire un étudiant à un cours LMS."""
        mock_client = MagicMock()
        mock_client.enroll_user.return_value = {"id": 99999}
        mock_get_client.return_value = mock_client

        service = SyncService()
        enrollment = service.sync_enrollment_to_lms(
            self.etudiant, self.course_mapping, mode="honor"
        )

        assert enrollment.enrollment_id == 99999
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
            service.sync_enrollment_to_lms(self.etudiant, self.course_mapping, mode="honor")

        event = OutboxEvent.objects.get(
            event_type="enrollment.create", aggregate_id=str(self.etudiant.id)
        )
        assert event.payload["course_mapping_id"] == self.course_mapping.id
        assert event.payload["mode"] == "honor"

    @patch("apps.integration.sync_service.get_edx_client")
    def test_bulk_sync_enrollments(self, mock_get_client):
        """Inscrire plusieurs étudiants en une fois."""
        mock_client = MagicMock()
        mock_client.bulk_enroll.return_value = [{"id": 1}]
        mock_get_client.return_value = mock_client

        service = SyncService()
        enrollments = service.bulk_sync_enrollments_to_lms(
            [self.etudiant], self.course_mapping
        )

        assert len(enrollments) == 1
        assert enrollments[0].enrollment_id == 1
        mock_client.bulk_enroll.assert_called_once_with(
            self.course_mapping.course_id, [self.user_mapping.username_edx], mode="audit"
        )


class SyncServiceGradeTestCase(CourseFixtureMixin, TenantTestCase):
    """Tests de synchronisation des notes."""

    def setUp(self):
        ecue, annee = self._create_ecue_and_annee()
        self.course_mapping = EdxCourseMapping.objects.create(
            ecue=ecue, course_id="course-v1:SIS-U+ECUE1+2023", course_name="Algorithmique"
        )
        self.user = Utilisateur.objects.create_user(
            "etudiant_grade", "etudiant_grade@test.com", TEST_USER_PASSWORD, role="etudiant"
        )
        self.etudiant = Etudiant.objects.create(
            universite=self.tenant,
            user=self.user,
            matricule="MATSYNC2",
            date_naissance="2002-01-01",
            lieu_naissance="Paris",
            sexe="F",
            adresse="1 rue des Tests",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        self.user_mapping = EdxUserMapping.objects.create(
            user_sis=self.user, username_edx="sis-u-etudiant-grade"
        )
        self.enrollment = EdxEnrollment.objects.create(
            etudiant=self.etudiant, course=self.course_mapping, is_active=True
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_import_grades_from_lms(self, mock_get_client):
        """Importer les notes depuis le LMS met à jour la progression."""
        mock_client = MagicMock()
        mock_client.get_grades.return_value = {"percent": 0.85}
        mock_get_client.return_value = mock_client

        service = SyncService()
        count = service.import_grades_from_lms(self.course_mapping)

        assert count == 1
        self.enrollment.refresh_from_db()
        assert self.enrollment.progression == 85
        assert self.enrollment.last_sync is not None

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_grade_to_lms_posts_score(self, mock_get_client):
        """Envoyer une note vers le LMS transmet le bon utilisateur EdX."""
        mock_client = MagicMock()
        mock_client.post_grade.return_value = {"success": True}
        mock_get_client.return_value = mock_client

        service = SyncService()
        result = service.sync_grade_to_lms(
            self.etudiant, self.course_mapping, "sub1", 15, 20
        )

        assert result == {"success": True}
        mock_client.post_grade.assert_called_once_with(
            self.course_mapping.course_id, self.user_mapping.username_edx, "sub1", 15, 20
        )


class SyncServiceReconciliationTestCase(CourseFixtureMixin, TenantTestCase):
    """Tests de réconciliation."""

    def setUp(self):
        ecue, annee = self._create_ecue_and_annee()
        self.course_mapping = EdxCourseMapping.objects.create(
            ecue=ecue, course_id="course-v1:SIS-U+ECUE1+2023", course_name="Algorithmique"
        )
        self.user = Utilisateur.objects.create_user(
            "etudiant_reconcile", "etudiant_reconcile@test.com", TEST_USER_PASSWORD, role="etudiant"
        )
        self.etudiant = Etudiant.objects.create(
            universite=self.tenant,
            user=self.user,
            matricule="MATREC1",
            date_naissance="2002-01-01",
            lieu_naissance="Paris",
            sexe="F",
            adresse="1 rue des Tests",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        EdxUserMapping.objects.create(user_sis=self.user, username_edx="sis-u-reconcile")
        self.enrollment = EdxEnrollment.objects.create(
            etudiant=self.etudiant, course=self.course_mapping, is_active=True
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_reconcile_updates_progression(self, mock_get_client):
        """La réconciliation met à jour la progression."""
        mock_client = MagicMock()
        mock_client.get_grades.return_value = {"percent": 0.75}
        mock_get_client.return_value = mock_client

        _reconcile_lms_for_current_schema()

        self.enrollment.refresh_from_db()
        assert self.enrollment.progression == 75
        mock_client.get_grades.assert_called_once()


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
            event.erreur = f"Attempt {event.nb_tentatives} failed"
            event.derniere_tentative = timezone.now()
            event.save()

        event.refresh_from_db()
        assert event.nb_tentatives == 3
