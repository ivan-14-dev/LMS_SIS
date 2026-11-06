"""API tests for portail_parent."""

from types import SimpleNamespace
from unittest.mock import patch

from apps.eleves.models import Eleve, EleveTuteur, Tuteur
from apps.etablissement.models import Etablissement
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.portail_parent.api import PortailParentViewSet
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate


class PortailParentAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/apprenant/tableau_bord/")

        assert match.url_name == "portail-apprenant-tableau-bord"

    def test_bulletins_route_is_registered(self):
        match = resolve("/api/v1/portail/apprenant/bulletins/")

        assert match.url_name == "portail-apprenant-bulletins"

    @patch("apps.portail_parent.api.is_current_tenant_user", return_value=True)
    def test_direct_parent_access_requires_parent_role_and_tenant_profile(self, tenant_access):
        from apps.portail_parent.api import IsParent

        user = SimpleNamespace(
            role="parent", is_authenticated=True, tuteur_profile=SimpleNamespace(etablissement_id=7)
        )
        request = SimpleNamespace(user=user, tenant=SimpleNamespace(pk=7))
        permission = IsParent()
        self.assertTrue(permission.has_permission(request, None))
        user.tuteur_profile.etablissement_id = 8
        self.assertFalse(permission.has_permission(request, None))
        user.tuteur_profile.etablissement_id = 7
        user.role = "eleve"
        self.assertFalse(permission.has_permission(request, None))
        user.role = "parent"
        tenant_access.return_value = False
        self.assertFalse(permission.has_permission(request, None))


class ParentAffiliationTestCase(TenantAPITestCase):
    def test_direct_parent_routes_exclude_other_tenant_and_revoked_children(self):
        parent = Utilisateur.objects.create_user(
            username="parent_links", role="parent", etablissement=self.tenant
        )
        guardian = Tuteur.objects.create(
            user=parent, etablissement=self.tenant, nom="Parent", prenom="Test",
            lien_parente="tuteur_legal", telephone="0100000000", email="parent@example.test",
        )
        other_tenant = Etablissement(
            schema_name="portal_other", nom="Autre", type="college",
            adresse="1 avenue", code_postal="75000", ville="Paris",
            telephone="0100000000", email="other@example.test",
        )
        other_tenant.auto_create_schema = False
        with schema_context("public"):
            other_tenant.save()

        def child(username, owner):
            user = Utilisateur.objects.create_user(
                username=username, role="eleve", etablissement=owner
            )
            return Eleve.objects.create(
                user=user, etablissement=owner, matricule=username,
                date_naissance="2014-01-01", date_inscription="2026-09-01", sexe="F",
            )

        own = child("child_own", self.tenant)
        outside = child("child_outside", other_tenant)
        revoked = child("child_revoked", self.tenant)
        EleveTuteur.objects.create(tuteur=guardian, eleve=own, autorise_acces_portail=True)
        EleveTuteur.objects.create(tuteur=guardian, eleve=outside, autorise_acces_portail=True)
        EleveTuteur.objects.create(tuteur=guardian, eleve=revoked, autorise_acces_portail=False)

        def call(action, **params):
            request = APIRequestFactory().get("/", params)
            request.tenant = self.tenant
            force_authenticate(request, user=parent)
            return PortailParentViewSet.as_view({"get": action})(request)

        dashboard = call("tableau_bord")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual([item["id"] for item in dashboard.data["enfants"]], [own.pk])
        self.assertEqual(call("enfant_detail", enfant_id=own.pk).status_code, 200)
        self.assertEqual(call("enfant_detail", enfant_id=outside.pk).status_code, 404)
        self.assertEqual(call("enfant_detail", enfant_id=revoked.pk).status_code, 404)
