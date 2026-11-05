"""Tests du service de synchronisation LMS - SIS Secondaire."""

from unittest.mock import ANY, MagicMock, create_autospec, patch

import pytest
from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.edx_client import EdxClient
from apps.integration.models import EdxAccessIntent, EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent
from apps.integration.sync_service import SyncService
from apps.integration.tasks import _reconcile_lms_for_current_schema, _retry_course_create
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class SyncServiceUserTestCase(TenantTestCase):
    """Tests de synchronisation des utilisateurs."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "sync_test_eleve",
            "sync_eleve@test.com",
            TEST_USER_PASSWORD,
            first_name="Marie",
            last_name="Martin",
            role="etudiant",
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_user_to_lms_creates_mapping(self, mock_get_client):
        """Synchroniser un utilisateur crée un mapping."""
        mock_client = create_autospec(EdxClient, instance=True)
        mock_client.create_user.return_value = {"id": 22222}
        mock_get_client.return_value = mock_client

        service = SyncService()
        mapping = service.sync_user_to_lms(self.user, role="student")

        assert mapping is not None
        assert mapping.user_id_edx == 22222
        assert mapping.user_sis == self.user
        assert mapping.actif
        mock_client.create_user.assert_called_once_with(
            username=mapping.username_edx,
            email=self.user.email,
            full_name="Marie Martin",
            role="student",
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sis_administration_does_not_grant_global_lms_privileges(self, mock_get_client):
        self.user.is_staff = True
        self.user.is_superuser = True
        mock_client = create_autospec(EdxClient, instance=True)
        mock_client.create_user.return_value = {"id": 22222}
        mock_get_client.return_value = mock_client

        mapping = SyncService().sync_user_to_lms(self.user, role="teacher")

        mock_client.create_user.assert_called_once_with(
            username=mapping.username_edx,
            email=self.user.email,
            full_name="Marie Martin",
            role="teacher",
        )

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
        assert outbox_event.payload["error"] == "API Error"
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


class SyncServiceCourseTestCase(TenantTestCase):
    """Tests de synchronisation des cours (matière/classe)."""

    def setUp(self):
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        niveau = Niveau.objects.create(etablissement=self.tenant, code="tale", libelle="Terminale")
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
        )
        self.matiere = Matiere.objects.create(etablissement=self.tenant, code="MATH", nom="Mathématiques")

    def test_manual_course_sync_rejects_foreign_sources_but_accepts_local_sources(self):
        admin = Utilisateur.objects.create_user(username="course-sync-admin", etablissement=self.tenant, is_staff=True)
        client = APIClient()
        client.defaults["SERVER_NAME"] = self.get_test_tenant_domain()
        client.force_authenticate(admin)
        foreign = type(self.tenant)(schema_name="course_sync_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        payload = {"matiere_id": self.matiere.pk, "classe_id": self.classe.pk}
        with patch("apps.integration.api.SyncService") as service:
            service.return_value.sync_course_to_cms.return_value = MagicMock(
                course_id="course-v1:SIS+local+sis", course_name="Local"
            )
            assert client.post("/api/v1/integration/sync/course/", payload, format="json").status_code == 200
            service.return_value.sync_course_to_cms.reset_mock()
            self.matiere.etablissement = foreign
            self.matiere.save(update_fields=["etablissement"])
            assert client.post("/api/v1/integration/sync/course/", payload, format="json").status_code == 404
            self.matiere.etablissement = self.tenant
            self.matiere.save(update_fields=["etablissement"])
            self.classe.etablissement = foreign
            self.classe.save(update_fields=["etablissement"])
            assert client.post("/api/v1/integration/sync/course/", payload, format="json").status_code == 404
            self.classe.etablissement = self.tenant
            self.classe.save(update_fields=["etablissement"])
            annee = self.classe.annee_scolaire
            annee.etablissement = foreign
            annee.save(update_fields=["etablissement"])
            assert client.post("/api/v1/integration/sync/course/", payload, format="json").status_code == 404
            annee.etablissement = self.tenant
            annee.save(update_fields=["etablissement"])
            niveau = self.classe.niveau
            niveau.etablissement = foreign
            niveau.save(update_fields=["etablissement"])
            assert client.post("/api/v1/integration/sync/course/", payload, format="json").status_code == 404
            service.return_value.sync_course_to_cms.assert_not_called()

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
        mapping = service.sync_course_to_cms(self.matiere, self.classe, "Mathématiques - Terminale S")

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

        event = OutboxEvent.objects.get(event_type="course.create", aggregate_id=str(self.matiere.id))
        assert event.payload["classe_id"] == self.classe.id
        assert event.payload["display_name"] == "Mathématiques"

    @patch("apps.integration.sync_service.get_edx_client")
    def test_course_retry_rejects_rehomed_class_level(self, mock_get_client):
        foreign = type(self.tenant)(schema_name="course_retry_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        event = OutboxEvent.objects.create(
            event_type="course.create",
            aggregate_type="matiere",
            aggregate_id=str(self.matiere.pk),
            payload={"classe_id": self.classe.pk, "display_name": "Mathématiques"},
        )
        niveau = self.classe.niveau
        niveau.etablissement = foreign
        niveau.save(update_fields=["etablissement"])

        with pytest.raises(ValueError, match="établissement"):
            _retry_course_create(SyncService(enqueue_failures=False), event)

        mock_get_client.return_value.create_course.assert_not_called()
        assert not EdxCourseMapping.objects.filter(matiere=self.matiere, classe=self.classe).exists()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_course_sync_keeps_shared_subject_and_class_with_local_ancestors(self, mock_get_client):
        self.matiere.etablissement = None
        self.matiere.save(update_fields=["etablissement"])
        self.classe.etablissement = None
        self.classe.save(update_fields=["etablissement"])
        mock_get_client.return_value.create_course.return_value = {
            "id": "course-v1:SIS+shared+sis",
            "display_name": "Mathématiques",
        }

        mapping = SyncService().sync_course_to_cms(self.matiere, self.classe, "Mathématiques")

        assert mapping.course_id == "course-v1:SIS+shared+sis"
        mock_get_client.return_value.create_course.assert_called_once()


class EnrollmentFixtureMixin:
    def setUp(self):
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        niveau = Niveau.objects.create(etablissement=self.tenant, code="tale", libelle="Terminale")
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
        )
        self.matiere = Matiere.objects.create(etablissement=self.tenant, code="MATH", nom="Mathématiques")
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
        self.user_mapping = EdxUserMapping.objects.create(user_sis=self.user, username_edx="sis-s-eleve-enroll")


class SyncServiceEnrollmentTestCase(EnrollmentFixtureMixin, TenantTestCase):
    """Tests de synchronisation des inscriptions élèves."""

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_enrollment_to_lms(self, mock_get_client):
        """Inscrire un élève à un cours LMS."""
        mock_client = MagicMock()
        mock_client.set_course_access.return_value = {"id": 88888}
        mock_get_client.return_value = mock_client

        service = SyncService()
        enrollment = service.sync_enrollment_to_lms(self.eleve, self.course_mapping)

        assert enrollment.enrollment_id == 88888
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
            service.sync_enrollment_to_lms(self.eleve, self.course_mapping)

        intent = EdxAccessIntent.objects.get(user=self.user, course=self.course_mapping, kind="enrollment")
        event = OutboxEvent.objects.get(event_type="access.set", aggregate_id=str(intent.pk))
        assert event.payload["requested_at"] == intent.requested_at.isoformat()
        assert event.statut == "pending" and "LMS timeout" in event.erreur

    @patch("apps.integration.sync_service.get_edx_client")
    def test_bulk_sync_enrollments_for_class(self, mock_get_client):
        """Inscrire tous les élèves d'une classe à un cours."""
        mock_client = create_autospec(EdxClient, instance=True)
        mock_client.set_course_access.return_value = {"id": 1}
        mock_get_client.return_value = mock_client

        service = SyncService()
        enrollments = service.bulk_sync_enrollments_to_lms([self.eleve], self.course_mapping)

        assert len(enrollments) == 1
        assert enrollments[0].enrollment_id == 1
        mock_client.set_course_access.assert_called_once_with(
            self.course_mapping.course_id, self.user_mapping.username_edx,
            kind="enrollment", active=True, requested_at=ANY,
        )

    @patch("apps.integration.sync_service.get_edx_client")
    def test_bulk_failure_keeps_confirmed_enrollments_and_can_be_replayed(self, get_client):
        other_user = Utilisateur.objects.create_user("another-enrollment", email="other@example.test")
        other = Eleve.objects.create(
            user=other_user,
            etablissement=self.tenant,
            matricule="MATSYNC-OTHER",
            date_naissance="2008-01-01",
            lieu_naissance="Test",
            sexe="F",
            date_inscription="2023-09-01",
        )
        EdxUserMapping.objects.create(user_sis=other_user, username_edx="another-lms-learner")
        client = create_autospec(EdxClient, instance=True)
        client.set_course_access.side_effect = [{}, RuntimeError("LMS unavailable")]
        get_client.return_value = client
        service = SyncService()
        with pytest.raises(RuntimeError, match="LMS unavailable"):
            service.bulk_sync_enrollments_to_lms([self.eleve, other], self.course_mapping)
        confirmed = EdxEnrollment.objects.get(eleve=self.eleve, course=self.course_mapping)
        assert confirmed.is_active and confirmed.enrollment_id is None
        assert not EdxEnrollment.objects.filter(eleve=other).exists()
        intent = EdxAccessIntent.objects.get(user=other_user, course=self.course_mapping, kind="enrollment")
        event = OutboxEvent.objects.get(event_type="access.set", aggregate_id=str(intent.pk))
        assert event.statut == "pending"
        client.set_course_access.side_effect = None
        client.set_course_access.return_value = {}
        replayed = service.bulk_sync_enrollments_to_lms([self.eleve, other], self.course_mapping)
        assert len(replayed) == 2 and replayed[0].pk == confirmed.pk
        assert EdxEnrollment.objects.filter(course=self.course_mapping).count() == 2

    @patch("apps.integration.sync_service.get_edx_client")
    def test_bulk_does_not_silently_skip_a_missing_user_mapping(self, get_client):
        self.user_mapping.delete()
        get_client.return_value = create_autospec(EdxClient, instance=True)
        with pytest.raises(EdxUserMapping.DoesNotExist):
            SyncService().bulk_sync_enrollments_to_lms([self.eleve], self.course_mapping)
        assert not EdxAccessIntent.objects.filter(user=self.user).exists()
        get_client.return_value.set_course_access.assert_not_called()


class SyncServiceGradeTestCase(TenantTestCase):
    """Tests de synchronisation des notes."""

    def setUp(self):
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        niveau = Niveau.objects.create(etablissement=self.tenant, code="tale", libelle="Terminale")
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
        )
        self.matiere = Matiere.objects.create(etablissement=self.tenant, code="MATH", nom="Mathématiques")
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
        self.user_mapping = EdxUserMapping.objects.create(user_sis=self.user, username_edx="sis-s-eleve-grade")
        self.enrollment = EdxEnrollment.objects.create(eleve=self.eleve, course=self.course_mapping, is_active=True)

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
        niveau = Niveau.objects.create(etablissement=self.tenant, code="tale", libelle="Terminale")
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
        )
        self.matiere = Matiere.objects.create(etablissement=self.tenant, code="MATH", nom="Mathématiques")
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
        EdxUserMapping.objects.create(user_sis=self.user_ok, username_edx="sis-s-eleve-reconcile-ok")
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
    def test_reconcile_skips_enrollment_without_mapping_without_raising(self, mock_get_client):
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
