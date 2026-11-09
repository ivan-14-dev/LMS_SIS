from contextlib import contextmanager, nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from sis_common import notification_channels


class NotificationEmailDeliveryTests(TestCase):
    def setUp(self):
        self.recipient = SimpleNamespace(
            email="recipient@example.test",
            preferences_notification={},
            is_active=True,
            etablissement_id=7,
        )
        self.notification = SimpleNamespace(
            id=13,
            recipient=self.recipient,
            category="exam",
            title="Résultat disponible",
            message="Consultez votre résultat.",
            metadata={"delivery": {"email": {"status": "queued", "attempts": 0}}},
            event=SimpleNamespace(tenant_id=7),
            save=Mock(),
        )
        self.model = Mock()
        self.model.objects.select_related.return_value.get.return_value = self.notification
        self.model.objects.select_for_update.return_value = self.model.objects
        self.model.objects.get.return_value = self.notification
        self.active_schemas = []

        @contextmanager
        def tenant_scope(schema_name):
            self.active_schemas.append(schema_name)
            try:
                yield
            finally:
                self.active_schemas.pop()

        patches = {
            "schema_context": {"side_effect": tenant_scope},
            "_core_model": {"return_value": self.model},
            "_now_iso": {"return_value": "2026-11-06T12:00:00+00:00"},
            "send_mail": {"return_value": 1},
            "transaction.atomic": {"return_value": nullcontext()},
        }
        for name, options in patches.items():
            patcher = patch(f"sis_common.notification_channels.{name}", **options)
            setattr(self, name.replace(".", "_"), patcher.start())
            self.addCleanup(patcher.stop)
        patcher = patch.object(
            notification_channels,
            "settings",
            SimpleNamespace(
                DEFAULT_FROM_EMAIL="notifications@example.test",
                EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                EMAIL_HOST="smtp.example.test",
            ),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_acknowledged_email_targets_only_current_recipient_within_tenant(self):
        self.recipient.email = "updated-recipient@example.test"

        def send(*args, **kwargs):
            self.assertEqual(self.active_schemas, ["school_a"])
            return 1

        def lookup(**kwargs):
            self.assertEqual(self.active_schemas, ["school_a"])
            return self.notification

        self.send_mail.side_effect = send
        self.model.objects.select_related.return_value.get.side_effect = lookup

        result = notification_channels.send_notification_email("school_a", 13)

        self.assertEqual(result, {"status": "sent"})
        self.schema_context.assert_called_once_with("school_a")
        self.model.objects.select_related.return_value.get.assert_called_once_with(pk=13)
        self.send_mail.assert_called_once_with(
            self.notification.title,
            self.notification.message,
            "notifications@example.test",
            ["updated-recipient@example.test"],
            fail_silently=False,
        )
        self.assertEqual(self.notification.metadata["delivery"]["email"]["status"], "sent")
        assert self.notification.save.call_count == 2
        self.assertEqual(self.active_schemas, [])

    def test_zero_acknowledgement_raises_without_recording_success(self):
        self.send_mail.return_value = 0

        with self.assertRaisesRegex(RuntimeError, "pas confirmé"):
            notification_channels.send_notification_email("school_a", 13)

        self.assertEqual(self.notification.metadata["delivery"]["email"]["status"], "failed")
        self.assertEqual(self.active_schemas, [])

    def test_ambiguous_smtp_failure_requires_reconciliation_and_is_never_resent(self):
        self.send_mail.side_effect = OSError("Backend indisponible.")

        assert notification_channels.send_notification_email("school_a", 13) == {"status": "uncertain"}
        assert notification_channels.send_notification_email("school_a", 13) == {"status": "uncertain"}

        self.assertEqual(self.notification.metadata["delivery"]["email"]["status"], "uncertain")
        self.send_mail.assert_called_once()
        self.assertEqual(self.active_schemas, [])

    def test_missing_address_skips_without_backend_call(self):
        self.recipient.email = ""

        result = notification_channels.send_notification_email("school_a", 13)

        self.assertEqual(result, {"status": "skipped"})
        self.assertEqual(self.notification.metadata["delivery"]["email"]["status"], "skipped")
        self.send_mail.assert_not_called()

    def test_channel_revocation_is_rechecked_after_unacknowledged_send(self):
        self.send_mail.return_value = 0
        with self.assertRaises(RuntimeError):
            notification_channels.send_notification_email("school_a", 13)
        self.recipient.preferences_notification = {"categories": {"exam": {"email": False}}}

        result = notification_channels.send_notification_email("school_a", 13)

        self.assertEqual(result, {"status": "skipped"})
        self.assertEqual(self.notification.metadata["delivery"]["email"]["status"], "skipped")
        self.send_mail.assert_called_once()

    def test_missing_notification_in_requested_tenant_never_calls_backend(self):
        self.model.objects.select_related.return_value.get.side_effect = LookupError("Notification absente.")

        with self.assertRaisesRegex(LookupError, "Notification absente"):
            notification_channels.send_notification_email("school_b", 13)

        self.schema_context.assert_called_once_with("school_b")
        self.model.objects.select_related.return_value.get.assert_called_once_with(pk=13)
        self.send_mail.assert_not_called()
        self.notification.save.assert_not_called()
        self.assertEqual(self.active_schemas, [])

    def test_zero_acknowledgement_retries_then_fails_at_task_limit(self):
        from apps.core.tasks import dispatch_notification_email
        from celery.exceptions import Retry

        self.send_mail.return_value = 0
        task = dispatch_notification_email._get_current_object()
        for retries, expected_status in ((0, "retrying"), (task.max_retries, "failed")):
            with self.subTest(retries=retries):
                task.push_request(retries=retries)
                try:
                    with patch.object(task, "retry", side_effect=Retry()) as retry:
                        expected_error = Retry if expected_status == "retrying" else RuntimeError
                        with self.assertRaises(expected_error):
                            task.run(13, "school_a")
                        if expected_status == "retrying":
                            retry.assert_called_once()
                            self.assertIsInstance(retry.call_args.kwargs["exc"], RuntimeError)
                        else:
                            retry.assert_not_called()
                finally:
                    task.pop_request()
                delivery = self.notification.metadata["delivery"]["email"]
                self.assertEqual(delivery["status"], expected_status)
                self.assertEqual(delivery["attempts"], retries + 1)
                self.assertIn("pas confirmé", delivery["last_error"])

    def test_acknowledged_retry_clears_previous_failure(self):
        from apps.core.tasks import dispatch_notification_email
        from celery.exceptions import Retry

        task = dispatch_notification_email._get_current_object()
        self.send_mail.return_value = 0
        task.push_request(retries=0)
        try:
            with patch.object(task, "retry", side_effect=Retry()), self.assertRaises(Retry):
                task.run(13, "school_a")
        finally:
            task.pop_request()

        self.send_mail.return_value = 1
        task.push_request(retries=1)
        try:
            result = task.run(13, "school_a")
        finally:
            task.pop_request()

        self.assertEqual(result, {"status": "sent"})
        delivery = self.notification.metadata["delivery"]["email"]
        self.assertEqual(delivery["status"], "sent")
        self.assertEqual(delivery["attempts"], 2)
        self.assertNotIn("last_error", delivery)

    def test_replayed_acknowledged_job_does_not_send_twice(self):
        assert notification_channels.send_notification_email("school_a", 13) == {"status": "sent"}
        assert notification_channels.send_notification_email("school_a", 13) == {"status": "sent"}
        self.send_mail.assert_called_once()

    def test_console_backend_is_not_a_delivery(self):
        with patch.object(notification_channels.settings, "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"):
            assert notification_channels.send_notification_email("school_a", 13) == {"status": "not_configured"}
        self.send_mail.assert_not_called()

    def test_worker_retry_cannot_downgrade_an_ambiguous_persisted_claim(self):
        self.notification.metadata["delivery"]["email"]["status"] = "sending"
        notification_channels.update_notification_channel_status(
            "school_a", 13, "email", "retrying", attempts=2, error="Database error after SMTP acknowledgement."
        )
        assert self.notification.metadata["delivery"]["email"]["status"] == "sending"
        assert notification_channels.send_notification_email("school_a", 13) == {"status": "uncertain"}
        self.send_mail.assert_not_called()

    def test_disabled_or_foreign_recipient_is_not_contacted(self):
        for inactive, tenant_id in ((True, 7), (False, 99)):
            self.recipient.is_active = not inactive
            self.recipient.etablissement_id = tenant_id
            assert notification_channels.send_notification_email("school_a", 13) == {"status": "skipped"}
        self.send_mail.assert_not_called()
