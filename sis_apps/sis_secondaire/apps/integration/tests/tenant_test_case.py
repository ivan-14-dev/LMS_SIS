"""Shared tenant-schema aware test-case bases for tests that write to the DB.

``apps.integration`` (and the models it references, such as
``apps.utilisateurs.Utilisateur``) live in ``TENANT_APPS`` and therefore only
have real tables inside a tenant's Postgres schema, never in ``public``. Tests
that create these objects must run inside a real tenant schema, which is what
``django_tenants.test.cases.FastTenantTestCase`` provides: it creates (once,
reused across test classes for speed) a dedicated ``fast_test`` tenant schema,
migrates it and switches the connection to it for the duration of the test.
"""

from django_tenants.test.cases import FastTenantTestCase
from rest_framework.test import APIClient


class TenantTestCase(FastTenantTestCase):
    """``FastTenantTestCase`` pre-populated with the establishment's required fields."""

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.nom = "Établissement de test"
        tenant.type = "college"
        tenant.adresse = "1 rue des Tests"
        tenant.code_postal = "75000"
        tenant.ville = "Paris"
        tenant.telephone = "0100000000"
        tenant.email = "contact@test-etablissement.example"


class TenantAPITestCase(TenantTestCase):
    """``TenantTestCase`` with a DRF ``APIClient`` for view-level tests.

    ``django_tenants``' ``TenantMainMiddleware`` resolves the active tenant (and
    therefore the schema used for the request) from the ``Host`` header via the
    ``Domain`` model. The Django test client defaults to ``testserver``, which
    doesn't match the tenant's test domain, so every request would 404 and
    fall back to the public schema. Binding the client's default ``SERVER_NAME``
    to the tenant's test domain keeps requests routed to the right tenant.
    """

    client_class = APIClient

    def _pre_setup(self):
        super()._pre_setup()
        self.client.defaults["SERVER_NAME"] = self.get_test_tenant_domain()
