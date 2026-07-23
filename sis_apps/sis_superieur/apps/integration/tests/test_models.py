"""Tests des modèles d'intégration LMS - SIS Supérieur."""
import pytest
from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError
from apps.integration.models import (
    EdxUserMapping, EdxCourseMapping, EdxEnrollment, EdxGradeLog, OutboxEvent
)
from apps.utilisateurs.models import Utilisateur


class EdxUserMappingTestCase(TestCase):
    """Tests pour EdxUserMapping."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            username='test_mapping_user',
            email='mapping@test.com',
            password='testpass123',
            role='etudiant'
        )

    def test_create_mapping(self):
        """Créer un mapping utilisateur SIS ↔ LMS."""
        mapping = EdxUserMapping.objects.create(
            user_sis=self.user,
            username_edx='edx-test-user-001'
        )
        self.assertEqual(mapping.username_edx, 'edx-test-user-001')
        self.assertTrue(mapping.actif)
        self.assertIsNone(mapping.user_id_edx)
        self.assertIsNone(mapping.date_sync)

    def test_mapping_str_representation(self):
        """Vérifier la représentation string du mapping."""
        mapping = EdxUserMapping.objects.create(
            user_sis=self.user,
            username_edx='edx-user-str-test'
        )
        expected = f"{self.user.username} ↔ edx-user-str-test"
        self.assertEqual(str(mapping), expected)

    def test_unique_username_edx(self):
        """Le username_edx doit être unique."""
        EdxUserMapping.objects.create(
            user_sis=self.user,
            username_edx='unique-edx-user'
        )
        user2 = Utilisateur.objects.create_user(
            username='test_user_2',
            email='test2@test.com',
            password='testpass123'
        )
        with self.assertRaises(IntegrityError):
            EdxUserMapping.objects.create(
                user_sis=user2,
                username_edx='unique-edx-user'  # Même username
            )

    def test_one_to_one_user_sis(self):
        """Un utilisateur SIS ne peut avoir qu'un seul mapping."""
        EdxUserMapping.objects.create(
            user_sis=self.user,
            username_edx='first-mapping'
        )
        with self.assertRaises(IntegrityError):
            EdxUserMapping.objects.create(
                user_sis=self.user,  # Même utilisateur
                username_edx='second-mapping'
            )

    def test_mapping_with_edx_id(self):
        """Créer un mapping avec l'ID utilisateur LMS."""
        mapping = EdxUserMapping.objects.create(
            user_sis=self.user,
            username_edx='edx-with-id',
            user_id_edx=12345,
            date_sync=timezone.now()
        )
        self.assertEqual(mapping.user_id_edx, 12345)
        self.assertIsNotNone(mapping.date_sync)

    def test_deactivate_mapping(self):
        """Désactiver un mapping."""
        mapping = EdxUserMapping.objects.create(
            user_sis=self.user,
            username_edx='to-deactivate',
            actif=True
        )
        mapping.actif = False
        mapping.save()
        mapping.refresh_from_db()
        self.assertFalse(mapping.actif)


class OutboxEventTestCase(TestCase):
    """Tests pour OutboxEvent (pattern outbox)."""

    def test_create_pending_event(self):
        """Créer un événement en attente."""
        event = OutboxEvent.objects.create(
            event_type='user.sync',
            aggregate_type='user',
            aggregate_id='123',
            payload={'action': 'create', 'username': 'test'}
        )
        self.assertEqual(event.statut, 'pending')
        self.assertEqual(event.nb_tentatives, 0)
        self.assertIsNone(event.derniere_tentative)
        self.assertEqual(event.erreur, '')

    def test_event_str_representation(self):
        """Vérifier la représentation string de l'événement."""
        event = OutboxEvent.objects.create(
            event_type='enrollment.create',
            aggregate_type='etudiant',
            aggregate_id='456',
            payload={}
        )
        expected = 'enrollment.create - etudiant#456'
        self.assertEqual(str(event), expected)

    def test_event_status_transitions(self):
        """Tester les transitions de statut."""
        event = OutboxEvent.objects.create(
            event_type='grade.update',
            aggregate_type='note',
            aggregate_id='789',
            payload={'score': 15}
        )
        
        # pending → processing
        event.statut = 'processing'
        event.save()
        self.assertEqual(event.statut, 'processing')
        
        # processing → done
        event.statut = 'done'
        event.derniere_tentative = timezone.now()
        event.save()
        self.assertEqual(event.statut, 'done')

    def test_event_failure_and_retry(self):
        """Tester l'échec et la réessai."""
        event = OutboxEvent.objects.create(
            event_type='course.create',
            aggregate_type='ecue',
            aggregate_id='101',
            payload={}
        )
        
        # Simuler un échec
        event.statut = 'failed'
        event.nb_tentatives = 1
        event.erreur = 'Connection timeout'
        event.derniere_tentative = timezone.now()
        event.save()
        
        self.assertEqual(event.nb_tentatives, 1)
        self.assertIn('timeout', event.erreur.lower())

    def test_dead_letter_after_max_retries(self):
        """Après 5 échecs, passer en dead letter."""
        event = OutboxEvent.objects.create(
            event_type='sync.failed',
            aggregate_type='user',
            aggregate_id='999',
            payload={},
            nb_tentatives=5,
            statut='failed'
        )
        
        # Logique de passage en dead letter
        if event.nb_tentatives >= 5:
            event.statut = 'dead'
            event.save()
        
        self.assertEqual(event.statut, 'dead')

    def test_event_ordering(self):
        """Les événements sont ordonnés par date de création (desc)."""
        event1 = OutboxEvent.objects.create(
            event_type='event1', aggregate_type='test', aggregate_id='1', payload={}
        )
        event2 = OutboxEvent.objects.create(
            event_type='event2', aggregate_type='test', aggregate_id='2', payload={}
        )
        
        events = list(OutboxEvent.objects.all())
        self.assertEqual(events[0], event2)  # Plus récent en premier
        self.assertEqual(events[1], event1)

    def test_index_on_statut_created_at(self):
        """Vérifier que l'index existe (via Meta)."""
        indexes = OutboxEvent._meta.indexes
        index_fields = [idx.fields for idx in indexes]
        self.assertIn(['statut', 'created_at'], index_fields)


class IntegrationModelRelationsTestCase(TestCase):
    """Tests des relations entre modèles d'intégration."""

    def test_cascade_delete_user_mapping(self):
        """Supprimer un utilisateur supprime son mapping."""
        user = Utilisateur.objects.create_user(
            username='cascade_user',
            email='cascade@test.com',
            password='testpass123'
        )
        EdxUserMapping.objects.create(
            user_sis=user,
            username_edx='cascade-edx-user'
        )
        
        user_id = user.id
        user.delete()
        
        # Le mapping doit être supprimé aussi
        self.assertFalse(
            EdxUserMapping.objects.filter(user_sis_id=user_id).exists()
        )


class OutboxEventManagerTestCase(TestCase):
    """Tests pour les requêtes sur OutboxEvent."""

    def test_filter_pending_events(self):
        """Filtrer les événements en attente."""
        OutboxEvent.objects.create(
            event_type='pending1', aggregate_type='test', aggregate_id='1',
            payload={}, statut='pending'
        )
        OutboxEvent.objects.create(
            event_type='done1', aggregate_type='test', aggregate_id='2',
            payload={}, statut='done'
        )
        OutboxEvent.objects.create(
            event_type='pending2', aggregate_type='test', aggregate_id='3',
            payload={}, statut='pending'
        )
        
        pending = OutboxEvent.objects.filter(statut='pending')
        self.assertEqual(pending.count(), 2)

    def test_batch_process_events(self):
        """Traiter un lot d'événements."""
        for i in range(10):
            OutboxEvent.objects.create(
                event_type=f'batch{i}',
                aggregate_type='test',
                aggregate_id=str(i),
                payload={},
                statut='pending'
            )
        
        # Récupérer les 5 premiers
        batch = OutboxEvent.objects.filter(statut='pending')[:5]
        self.assertEqual(len(batch), 5)
