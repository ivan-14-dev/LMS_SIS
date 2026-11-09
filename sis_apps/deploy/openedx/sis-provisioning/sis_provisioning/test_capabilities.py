from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .capabilities import CMSCapabilitiesView, LMSCapabilitiesView


class CapabilitiesTests(SimpleTestCase):
    def test_capabilities_only_report_existing_permissions_without_granting_rights(self):
        request = APIRequestFactory().get("/api/sis/v1/capabilities/")
        user = SimpleNamespace(
            is_authenticated=True, is_active=True,
            has_perm=lambda name: name == "sis_provisioning.provision_accounts",
        )
        force_authenticate(request, user=user)
        response = LMSCapabilitiesView.as_view()(request)
        assert response.status_code == 200
        assert response.data["contract"] == "sis-provisioning/v1"
        assert response.data["capabilities"] == {"accounts": True, "enrollments": False, "teaching": False}
        response = CMSCapabilitiesView.as_view()(request)
        assert response.data["capabilities"] == {"courses": False, "publication": False}

    def test_anonymous_or_inactive_service_never_reports_available_contract(self):
        request = APIRequestFactory().get("/api/sis/v1/capabilities/")
        assert LMSCapabilitiesView.as_view()(request).status_code in (401, 403)
        user = SimpleNamespace(is_authenticated=True, is_active=False, has_perm=lambda name: True)
        force_authenticate(request, user=user)
        response = LMSCapabilitiesView.as_view()(request)
        assert not any(response.data["capabilities"].values())
