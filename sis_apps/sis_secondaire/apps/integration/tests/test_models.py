"""Tests des modèles d'intégration - SIS Secondaire."""

import pytest
from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.models import EdxCourseMapping, EdxEnrollment, EdxGradeLog, EdxUserMapping, OutboxEvent
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.db import IntegrityError
from django.utils import timezone

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class EdxUserMappingModelTestCase(TenantTestCase):
    """Tests pour EdxUserMapping."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            username="eleve_test",
            email="eleve@test.com",
            password="testpass123",
            first_name="Jean",
            last_name="Dupont",
            role="etudiant",
        )

    def test_create_mapping(self):
        """Créer un mapping utilisateur EdX."""
        mapping = EdxUserMapping.objects.create(
            user_sis=self.user, username_edx="sis-s-eleve_test", user_id_edx=12345
        )
        assert mapping.username_edx == "sis-s-eleve_test"
        assert mapping.user_id_edx == 12345
        assert mapping.actif

    def test_str_representation(self):
        """Le __str__ affiche le mapping."""
        mapping = EdxUserMapping.objects.create(
            user_sis=self.user, username_edx="sis-s-eleve_test"
        )
        assert "eleve_test" in str(mapping)
        assert "sis-s-eleve_test" in str(mapping)

    def test_username_edx_unique(self):
        """Le username EdX doit être unique."""
        EdxUserMapping.objects.create(
            user_sis=self.user, username_edx="unique-username"
        )
        user2 = Utilisateur.objects.create_user(
            username="autre_eleve",
            email="autre@test.com",
            password="test",
            role="etudiant",
        )
        with pytest.raises(IntegrityError):
            EdxUserMapping.objects.create(
                user_sis=user2, username_edx="unique-username"
            )

    def test_one_to_one_constraint(self):
        """Un utilisateur SIS ne peut avoir qu'un seul mapping."""
        EdxUserMapping.objects.create(user_sis=self.user, username_edx="first-mapping")
        with pytest.raises(IntegrityError):
            EdxUserMapping.objects.create(
                user_sis=self.user, username_edx="second-mapping"
            )

    def test_cascade_delete(self):
        """La suppression de l'utilisateur SIS supprime le mapping."""
        EdxUserMapping.objects.create(user_sis=self.user, username_edx="to-delete")
        self.user.delete()
        assert EdxUserMapping.objects.count() == 0


class OutboxEventModelTestCase(TenantTestCase):
    """Tests pour OutboxEvent."""

    def test_create_event(self):
        """Créer un événement outbox."""
        event = OutboxEvent.objects.create(
            event_type="eleve.created",
            aggregate_type="eleve",
            aggregate_id="123",
            payload={"eleve_id": 123, "matricule": "ELV000001"},
        )
        assert event.statut == "pending"
        assert event.nb_tentatives == 0
        assert event.derniere_tentative is None

    def test_event_status_transitions(self):
        """Tester les transitions d'état."""
        event = OutboxEvent.objects.create(
            event_type="test.event", aggregate_type="test", aggregate_id="1", payload={}
        )

        # pending -> processing
        event.statut = "processing"
        event.save()
        assert event.statut == "processing"

        # processing -> done
        event.statut = "done"
        event.derniere_tentative = timezone.now()
        event.save()
        assert event.statut == "done"

    def test_retry_increments_counter(self):
        """Les retries incrémentent le compteur."""
        event = OutboxEvent.objects.create(
            event_type="retry.test",
            aggregate_type="test",
            aggregate_id="1",
            payload={},
            nb_tentatives=2,
        )

        event.nb_tentatives += 1
        event.erreur = "Connexion échouée"
        event.save()

        event.refresh_from_db()
        assert event.nb_tentatives == 3
        assert event.erreur == "Connexion échouée"

    def test_ordering_by_created_at(self):
        """Les événements sont triés par date de création (décroissant)."""
        event1 = OutboxEvent.objects.create(
            event_type="first", aggregate_type="test", aggregate_id="1", payload={}
        )
        event2 = OutboxEvent.objects.create(
            event_type="second", aggregate_type="test", aggregate_id="2", payload={}
        )

        events = list(OutboxEvent.objects.all())
        assert events[0] == event2  # Plus récent en premier
        assert events[1] == event1

    def test_filter_by_status(self):
        """Filtrer les événements par statut."""
        for i in range(3):
            OutboxEvent.objects.create(
                event_type="pending.event",
                aggregate_type="test",
                aggregate_id=str(i),
                payload={},
                statut="pending",
            )

        OutboxEvent.objects.create(
            event_type="done.event",
            aggregate_type="test",
            aggregate_id="done",
            payload={},
            statut="done",
        )

        pending = OutboxEvent.objects.filter(statut="pending")
        done = OutboxEvent.objects.filter(statut="done")

        assert pending.count() == 3
        assert done.count() == 1


class EdxEnrollmentModelTestCase(TenantTestCase):
    """Tests pour EdxEnrollment."""

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
        classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
        )
        matiere = Matiere.objects.create(
            etablissement=self.tenant, code="MATH", nom="Mathématiques"
        )
        self.course_mapping = EdxCourseMapping.objects.create(
            matiere=matiere,
            classe=classe,
            course_id="course-v1:SIS+MATH001+2024",
            course_name="Mathématiques",
        )
        user = Utilisateur.objects.create_user(
            "eleve_enroll_model", "eleve_enroll_model@test.com", TEST_USER_PASSWORD, role="eleve"
        )
        self.eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=user,
            matricule="MATMODEL1",
            date_naissance="2008-01-01",
            lieu_naissance="Paris",
            sexe="M",
            date_inscription="2023-09-01",
        )

    def test_default_progression(self):
        """La progression par défaut est 0."""
        enrollment = EdxEnrollment.objects.create(eleve=self.eleve, course=self.course_mapping)
        assert enrollment.progression == 0

    def test_is_active_default(self):
        """is_active est True par défaut."""
        enrollment = EdxEnrollment.objects.create(eleve=self.eleve, course=self.course_mapping)
        assert enrollment.is_active is True


class EdxGradeLogModelTestCase(TenantTestCase):
    """Tests pour EdxGradeLog."""

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
        classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=annee,
            niveau=niveau,
            nom="Terminale S",
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
        user = Utilisateur.objects.create_user(
            "eleve_grade_model", "eleve_grade_model@test.com", TEST_USER_PASSWORD, role="eleve"
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=user,
            matricule="MATMODEL2",
            date_naissance="2008-01-01",
            lieu_naissance="Paris",
            sexe="M",
            date_inscription="2023-09-01",
        )
        self.enrollment = EdxEnrollment.objects.create(eleve=eleve, course=course_mapping)

    def test_imported_to_sis_default(self):
        """imported_to_sis est False par défaut."""
        grade_log = EdxGradeLog.objects.create(
            enrollment=self.enrollment,
            subsection_id="block-v1:sub1",
            score=15,
            timestamp_lms=timezone.now(),
        )
        assert grade_log.imported_to_sis is False

    def test_ordering_by_timestamp(self):
        """Les logs sont triés par timestamp (décroissant)."""
        older = EdxGradeLog.objects.create(
            enrollment=self.enrollment,
            subsection_id="block-v1:sub1",
            score=10,
            timestamp_lms=timezone.now() - timezone.timedelta(days=1),
        )
        newer = EdxGradeLog.objects.create(
            enrollment=self.enrollment,
            subsection_id="block-v1:sub2",
            score=12,
            timestamp_lms=timezone.now(),
        )

        logs = list(EdxGradeLog.objects.all())

        assert logs[0] == newer
        assert logs[1] == older
