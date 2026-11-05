from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context


class InstitutionalBrandingTests(TenantAPITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "branding-learner",
            etablissement=self.tenant,
            role="eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant",
        )
        self.client.force_authenticate(self.user)
        self.url = "/api/v1/utilisateurs/comptes/me/"

    def test_learner_reads_only_presentation_identity_without_administrative_configuration(self):
        self.tenant.couleur_primaire = "#16A34A"
        self.tenant.logo = "logos/institution.png"
        self.tenant.save(update_fields=["couleur_primaire", "logo"])
        response = self.client.get(self.url)
        assert response.status_code == 200, response.data
        assert response.data["branding"] == {
            "id": self.tenant.pk,
            "name": self.tenant.nom,
            "primary_color": "#16A34A",
            "logo": f"http://{self.get_test_tenant_domain()}/media/logos/institution.png",
        }
        assert "configuration_academique" not in response.data
        assert self.client.get("/api/v1/etablissement/current/").status_code == 403
        response = self.client.patch(
            "/api/v1/utilisateurs/comptes/update_profile/",
            {"branding": {"primary_color": "#FF0000"}},
            format="json",
        )
        assert response.status_code == 200
        self.tenant.refresh_from_db()
        assert self.tenant.couleur_primaire == "#16A34A"

    def test_cross_tenant_and_anonymous_identity_access_are_rejected(self):
        other = type(self.tenant)(schema_name="branding_other")
        self.setup_tenant(other)
        other.auto_create_schema = False
        with schema_context("public"):
            other.save()
        self.user.etablissement = other
        self.user.save(update_fields=["etablissement"])
        assert self.client.get(self.url).status_code == 403
        self.client.force_authenticate(None)
        assert self.client.get(self.url).status_code in (401, 403)
