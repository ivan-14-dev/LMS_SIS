"""Tests du service de synchronisation LMS - SIS Supérieur."""

import datetime
from unittest.mock import ANY, MagicMock, create_autospec, patch

import pytest
from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.edx_client import EdxClient
from apps.integration.models import EdxAccessIntent, EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent
from apps.integration.sync_service import SyncService
from apps.integration.tasks import _reconcile_lms_for_current_schema, _retry_course_create, _retry_user_sync
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.ue_ecue.models import ECUE, UE
from apps.utilisateurs.models import Utilisateur
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

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
        formation = Formation.objects.create(nom="Licence Informatique", code="LINFO", type="licence")
        maquette = MaquetteFormation.objects.create(formation=formation, annee_universitaire=annee)
        ue = UE.objects.create(
            maquette=maquette,
            code="UE1",
            nom="Programmation",
            credits_ects=6,
            semestre=semestre,
        )
        ecue = ECUE.objects.create(ue=ue, code="ECUE1", nom="Algorithmique", credits_ects=3)
        return ecue, annee


class SyncServiceUserTestCase(TenantTestCase):
    """Tests de synchronisation des utilisateurs."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "sync_test_user",
            "sync@test.com",
            TEST_USER_PASSWORD,
            first_name="Sync",
            last_name="Test",
            role="etudiant",
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_to_lms_creates_mapping(self, mock_get_client):
        """Synchroniser un utilisateur crée un mapping."""
        mock_client = create_autospec(EdxClient, instance=True)
        mock_client.create_user.return_value = {"id": 12345}
        mock_get_client.return_value = mock_client

        service = SyncService()
        mapping = service.sync_user_to_lms(self.user, role="student")

        assert mapping is not None
        assert mapping.user_id_edx == 12345
        assert mapping.user_sis == self.user
        assert mapping.actif
        mock_client.create_user.assert_called_once_with(
            username=mapping.username_edx,
            email=self.user.email,
            full_name="Sync Test",
            role="student",
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sis_administration_does_not_grant_global_lms_privileges(self, mock_get_client):
        self.user.is_staff = True
        self.user.is_superuser = True
        mock_client = create_autospec(EdxClient, instance=True)
        mock_client.create_user.return_value = {"id": 12345}
        mock_get_client.return_value = mock_client

        mapping = SyncService().sync_user_to_lms(self.user, role="teacher")

        mock_client.create_user.assert_called_once_with(
            username=mapping.username_edx,
            email=self.user.email,
            full_name="Sync Test",
            role="teacher",
        )

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
        assert mapping.username_edx == existing_mapping.username_edx
        mock_client.create_user.assert_not_called()
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

        outbox_event = OutboxEvent.objects.filter(event_type="user.sync", aggregate_id=str(self.user.id)).first()

        assert outbox_event is not None
        assert outbox_event.erreur == "API Error"
        assert outbox_event.payload["role"] == "teacher"

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_failure_not_enqueued_when_enqueue_failures_disabled(self, mock_get_client):
        """Le rejeu outbox (enqueue_failures=False) ne recrée pas d'événement."""
        mock_client = MagicMock()
        mock_client.create_user.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        service = SyncService(enqueue_failures=False)

        with pytest.raises(Exception, match="API Error"):
            service.sync_user_to_lms(self.user)

        assert not OutboxEvent.objects.filter(event_type="user.sync", aggregate_id=str(self.user.id)).exists()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_user_replay_does_not_update_mapping_after_reassignment(self, mock_get_client):
        foreign = type(self.tenant)(schema_name="user_replay_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        self.user.etablissement = self.tenant
        self.user.save(update_fields=["etablissement"])
        mapping = EdxUserMapping.objects.create(
            user_sis=self.user, username_edx=f"sis-u-{self.user.pk}", user_id_edx=11111
        )
        event = OutboxEvent.objects.create(
            event_type="user.sync",
            aggregate_type="user",
            aggregate_id=str(self.user.pk),
            payload={"role": "teacher"},
        )
        Utilisateur.objects.filter(pk=self.user.pk).update(etablissement=foreign, email="foreign@example.test")

        with pytest.raises(ValueError, match="université"):
            _retry_user_sync(SyncService(enqueue_failures=False), event)

        mock_get_client.return_value.update_user.assert_not_called()
        mock_get_client.return_value.create_user.assert_not_called()
        mapping.refresh_from_db()
        assert mapping.date_sync is None
        assert OutboxEvent.objects.count() == 1

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_rechecks_tenant_before_creating_mapping(self, mock_get_client):
        mock_get_client.return_value.create_user.return_value = {"id": 12345}
        foreign = type(self.tenant)(schema_name="user_create_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        self.user.etablissement = self.tenant
        self.user.save(update_fields=["etablissement"])
        Utilisateur.objects.filter(pk=self.user.pk).update(etablissement=foreign)

        with pytest.raises(ValueError, match="université"):
            SyncService(enqueue_failures=False).sync_user_to_lms(self.user)

        mock_get_client.return_value.create_user.assert_not_called()
        assert not EdxUserMapping.objects.filter(user_sis=self.user).exists()


class SyncServiceCourseTestCase(CourseFixtureMixin, TenantTestCase):
    """Tests de synchronisation des cours."""

    def test_manual_course_sync_rejects_foreign_sources_but_accepts_local_sources(self):
        admin = Utilisateur.objects.create_user(username="course-sync-admin", etablissement=self.tenant, is_staff=True)
        client = APIClient()
        client.defaults["SERVER_NAME"] = self.get_test_tenant_domain()
        client.force_authenticate(admin)
        ecue, annee = self._create_ecue_and_annee()
        foreign = type(self.tenant)(schema_name="course_sync_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_annee = AnneeUniversitaire.objects.create(
            universite=foreign,
            libelle="2024-2025",
            date_debut=datetime.date(2024, 9, 1),
            date_fin=datetime.date(2025, 6, 30),
        )
        payload = {"ecue_id": ecue.pk, "annee_id": annee.pk}
        with patch("apps.integration.api.SyncService") as service:
            service.return_value.sync_course_to_cms.return_value = MagicMock(course_id="course-v1:SIS+local+sis")
            assert client.post("/api/v1/integration/sync/course/", payload, format="json").status_code == 200
            service.return_value.sync_course_to_cms.reset_mock()
            response = client.post(
                "/api/v1/integration/sync/course/",
                {**payload, "annee_id": foreign_annee.pk},
                format="json",
            )
            assert response.status_code == 404
            semestre = ecue.ue.semestre
            semestre.annee_universitaire = foreign_annee
            semestre.save(update_fields=["annee_universitaire"])
            assert client.post("/api/v1/integration/sync/course/", payload, format="json").status_code == 404
            semestre.annee_universitaire = annee
            semestre.save(update_fields=["annee_universitaire"])
            maquette = ecue.ue.maquette
            maquette.annee_universitaire = foreign_annee
            maquette.save(update_fields=["annee_universitaire"])
            assert client.post("/api/v1/integration/sync/course/", payload, format="json").status_code == 404
            service.return_value.sync_course_to_cms.assert_not_called()

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

    @patch("apps.integration.sync_service.get_edx_client")
    def test_course_retry_rejects_rehomed_curriculum(self, mock_get_client):
        ecue, annee = self._create_ecue_and_annee()
        foreign = type(self.tenant)(schema_name="course_retry_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_annee = AnneeUniversitaire.objects.create(
            universite=foreign,
            libelle="2024-2025",
            date_debut=datetime.date(2024, 9, 1),
            date_fin=datetime.date(2025, 6, 30),
        )
        event = OutboxEvent.objects.create(
            event_type="course.create",
            aggregate_type="ecue",
            aggregate_id=str(ecue.pk),
            payload={"annee_universitaire_id": annee.pk, "display_name": "Algorithmique"},
        )
        maquette = ecue.ue.maquette
        maquette.annee_universitaire = foreign_annee
        maquette.save(update_fields=["annee_universitaire"])

        with pytest.raises(ValueError, match="année|université"):
            _retry_course_create(SyncService(enqueue_failures=False), event)

        mock_get_client.return_value.create_course.assert_not_called()
        assert not EdxCourseMapping.objects.filter(ecue=ecue).exists()


class EnrollmentFixtureMixin(CourseFixtureMixin):
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
        self.user_mapping = EdxUserMapping.objects.create(user_sis=self.user, username_edx="sis-u-etudiant-enroll")


class SyncServiceEnrollmentTestCase(EnrollmentFixtureMixin, TenantTestCase):
    """Tests de synchronisation des inscriptions."""

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_enrollment_to_lms(self, mock_get_client):
        """Inscrire un étudiant à un cours LMS."""
        mock_client = MagicMock()
        mock_client.set_course_access.return_value = {"id": 99999}
        mock_get_client.return_value = mock_client

        service = SyncService()
        enrollment = service.sync_enrollment_to_lms(self.etudiant, self.course_mapping)

        assert enrollment.enrollment_id == 99999
        assert enrollment.is_active
        mock_client.set_course_access.assert_called_once_with(
            self.course_mapping.course_id, self.user_mapping.username_edx,
            kind="enrollment", active=True, requested_at=ANY,
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_enrollment_failure_creates_outbox_event(self, mock_get_client):
        """En cas d'échec, l'événement outbox contient tout le contexte nécessaire au rejeu."""
        mock_client = MagicMock()
        mock_client.set_course_access.side_effect = Exception("LMS timeout")
        mock_get_client.return_value = mock_client

        service = SyncService()
        with pytest.raises(Exception, match="LMS timeout"):
            service.sync_enrollment_to_lms(self.etudiant, self.course_mapping)

        intent = EdxAccessIntent.objects.get(user=self.user, course=self.course_mapping, kind="enrollment")
        event = OutboxEvent.objects.get(event_type="access.set", aggregate_id=str(intent.pk))
        assert event.payload["requested_at"] == intent.requested_at.isoformat()
        assert event.statut == "pending" and "LMS timeout" in event.erreur

    @patch("apps.integration.sync_service.get_edx_client")
    def test_bulk_sync_enrollments(self, mock_get_client):
        """Inscrire plusieurs étudiants en une fois."""
        mock_client = create_autospec(EdxClient, instance=True)
        mock_client.set_course_access.return_value = {"id": 1}
        mock_get_client.return_value = mock_client

        service = SyncService()
        enrollments = service.bulk_sync_enrollments_to_lms([self.etudiant], self.course_mapping)

        assert len(enrollments) == 1
        assert enrollments[0].enrollment_id == 1
        mock_client.set_course_access.assert_called_once_with(
            self.course_mapping.course_id, self.user_mapping.username_edx,
            kind="enrollment", active=True, requested_at=ANY,
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_bulk_failure_keeps_confirmed_enrollments_and_can_be_replayed(self, get_client):
        other_user = Utilisateur.objects.create_user("another-enrollment", email="other@example.test")
        other = Etudiant.objects.create(
            user=other_user,
            universite=self.tenant,
            matricule="MATSYNC-OTHER",
            date_naissance="2002-01-01",
            lieu_naissance="Test",
            sexe="F",
        )
        EdxUserMapping.objects.create(user_sis=other_user, username_edx="another-lms-learner")
        client = create_autospec(EdxClient, instance=True)
        client.set_course_access.side_effect = [{}, RuntimeError("LMS unavailable")]
        get_client.return_value = client
        service = SyncService()
        with pytest.raises(RuntimeError, match="LMS unavailable"):
            service.bulk_sync_enrollments_to_lms([self.etudiant, other], self.course_mapping)
        confirmed = EdxEnrollment.objects.get(etudiant=self.etudiant, course=self.course_mapping)
        assert confirmed.is_active and confirmed.enrollment_id is None
        assert not EdxEnrollment.objects.filter(etudiant=other).exists()
        intent = EdxAccessIntent.objects.get(user=other_user, course=self.course_mapping, kind="enrollment")
        event = OutboxEvent.objects.get(event_type="access.set", aggregate_id=str(intent.pk))
        assert event.statut == "pending"
        client.set_course_access.side_effect = None
        client.set_course_access.return_value = {}
        replayed = service.bulk_sync_enrollments_to_lms([self.etudiant, other], self.course_mapping)
        assert len(replayed) == 2 and replayed[0].pk == confirmed.pk
        assert EdxEnrollment.objects.filter(course=self.course_mapping).count() == 2

    @patch("apps.integration.sync_service.get_edx_client")
    def test_bulk_does_not_silently_skip_a_missing_user_mapping(self, get_client):
        self.user_mapping.delete()
        get_client.return_value = create_autospec(EdxClient, instance=True)
        with pytest.raises(EdxUserMapping.DoesNotExist):
            SyncService().bulk_sync_enrollments_to_lms([self.etudiant], self.course_mapping)
        assert not EdxAccessIntent.objects.filter(user=self.user).exists()
        get_client.return_value.set_course_access.assert_not_called()


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
        self.user_mapping = EdxUserMapping.objects.create(user_sis=self.user, username_edx="sis-u-etudiant-grade")
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
        result = service.sync_grade_to_lms(self.etudiant, self.course_mapping, "sub1", 15, 20)

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
