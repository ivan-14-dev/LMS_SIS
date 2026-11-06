from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from sis_common.session_security import list_active_sessions


@pytest.mark.parametrize("role", ["direction", "eleve", "doyen", "etudiant"])
def test_session_list_excludes_expired_tokens_without_db(role):
    now = timezone.now()
    user = SimpleNamespace(pk=7, role=role)
    expired = SimpleNamespace(id=1, jti="expired", created_at=now, expires_at=now - timedelta(seconds=1))
    active = SimpleNamespace(id=2, jti="active", created_at=now, expires_at=now + timedelta(days=1))

    def filter_tokens(**kwargs):
        cutoff = kwargs.get("expires_at__gt", now - timedelta(days=1))
        return SimpleNamespace(order_by=lambda _: [token for token in (expired, active) if token.expires_at > cutoff])

    with (
        patch("sis_common.session_security.timezone.now", return_value=now),
        patch.object(OutstandingToken.objects, "filter", side_effect=filter_tokens) as outstanding_filter,
        patch.object(BlacklistedToken.objects, "filter", return_value=Mock(values_list=Mock(return_value=[2]))),
    ):
        sessions = list_active_sessions(user)

    assert sessions == [
        {"jti": "active", "created_at": now, "expires_at": active.expires_at, "revoked": True}
    ]
    outstanding_filter.assert_called_once_with(user=user, expires_at__gt=now)


class SessionSecurityTests(TenantAPITestCase):
    def test_staff_and_learner_session_lists_exclude_expired_refresh_tokens(self):
        staff_role, learner_role = (
            ("direction", "eleve") if settings.SIS_VARIANT == "secondaire" else ("doyen", "etudiant")
        )
        for index, role in enumerate((staff_role, learner_role)):
            user = get_user_model().objects.create_user(
                f"session-list-{index}",
                f"session-list-{index}@example.test",
                "test-only-password",
                role=role,
                is_staff=index == 0,
                etablissement=self.tenant,
            )
            expired = RefreshToken.for_user(user)
            active = RefreshToken.for_user(user)
            OutstandingToken.objects.filter(jti=expired["jti"]).update(
                expires_at=timezone.now() - timedelta(seconds=1)
            )
            if index == 0:
                BlacklistedToken.objects.create(token=OutstandingToken.objects.get(jti=active["jti"]))

            sessions = list_active_sessions(user)

            assert [session["jti"] for session in sessions] == [str(active["jti"])]
            assert sessions[0]["revoked"] is (index == 0)
