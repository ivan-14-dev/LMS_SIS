"""HTTP regressions for both variants using isolated real tenant schemas."""

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django_tenants.utils import get_public_schema_name, get_tenant_domain_model, get_tenant_model, schema_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from sis_common.local_authentication import TENANT_CLAIM

PASSWORD = "local-jwt-isolated-test-value"


class LocalJWTTenantIsolationTests(TenantAPITestCase):
    peer_domain = "local-jwt-peer.example.test"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with schema_context(get_public_schema_name()):
            cls.peer = get_tenant_model()(schema_name="local_jwt_peer_test")
            cls.setup_tenant(cls.peer)
            cls.peer.save(verbosity=0)
            get_tenant_domain_model().objects.create(tenant=cls.peer, domain=cls.peer_domain)

    @classmethod
    def tearDownClass(cls):
        try:
            with schema_context(cls.peer.schema_name):
                # Collect tenant-local relations before dropping their tables.
                get_tenant_model().objects.filter(pk=cls.peer.pk).delete()
                cls.peer._drop_schema(force_drop=True)
        finally:
            super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            "local-jwt-student",
            password=PASSWORD,
            etablissement=self.tenant,
            role="eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant",
        )

    def login(self, client, username):
        response = client.post("/api/v1/auth/token/", {"username": username, "password": PASSWORD})
        assert response.status_code == 200, response.data
        return response.data

    def test_login_access_rotation_and_revocation_keep_tenant_binding(self):
        pair = self.login(self.client, self.user.username)
        expected = f"{settings.TENANT_MODEL}:{self.tenant.pk}"
        initial_refresh = RefreshToken(pair["refresh"])
        assert initial_refresh[TENANT_CLAIM] == AccessToken(pair["access"])[TENANT_CLAIM] == expected
        stored = OutstandingToken.objects.get(jti=initial_refresh["jti"])
        assert RefreshToken(stored.token)[TENANT_CLAIM] == expected
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair['access']}")
        profile = self.client.get("/api/v1/utilisateurs/comptes/me/")
        assert profile.status_code == 200, profile.data
        assert profile.data["username"] == self.user.username

        rotated = self.client.post("/api/v1/auth/token/refresh/", {"refresh": pair["refresh"]})
        assert rotated.status_code == 200, rotated.data
        assert RefreshToken(rotated.data["refresh"])[TENANT_CLAIM] == expected
        assert AccessToken(rotated.data["access"])[TENANT_CLAIM] == expected
        assert BlacklistedToken.objects.filter(token__jti=initial_refresh["jti"]).exists()
        assert self.client.post("/api/v1/auth/token/refresh/", {"refresh": pair["refresh"]}).status_code == 401

    def test_host_selected_peer_staff_with_same_user_id_cannot_accept_student_tokens(self):
        pair = self.login(self.client, self.user.username)
        with override_settings(ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, self.peer_domain]):
            try:
                connection.set_tenant(self.peer)
                staff = get_user_model().objects.create_user(
                    "local-jwt-staff",
                    pk=self.user.pk,
                    password=PASSWORD,
                    etablissement=self.peer,
                    role="direction",
                    is_staff=True,
                    is_superuser=True,
                )
                assert staff.pk == self.user.pk
                peer_client = APIClient(SERVER_NAME=self.peer_domain)
                peer_pair = self.login(peer_client, staff.username)
                peer_client.credentials(HTTP_AUTHORIZATION=f"Bearer {peer_pair['access']}")
                profile = peer_client.get("/api/v1/utilisateurs/comptes/me/")
                assert profile.status_code == 200, profile.data
                assert profile.data["username"] == staff.username

                peer_client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair['access']}")
                assert peer_client.get("/api/v1/utilisateurs/comptes/me/").status_code == 401
                peer_client.credentials()
                assert peer_client.post("/api/v1/auth/token/refresh/", {"refresh": pair["refresh"]}).status_code == 401
                assert not OutstandingToken.objects.filter(
                    jti=RefreshToken(pair["refresh"], verify=False)["jti"]
                ).exists()
                refreshed = self.client.post("/api/v1/auth/token/refresh/", {"refresh": pair["refresh"]})
                assert refreshed.status_code == 200, refreshed.data
            finally:
                connection.set_tenant(self.tenant)
