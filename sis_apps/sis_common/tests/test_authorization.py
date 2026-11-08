from types import SimpleNamespace

from apps.utilisateurs.models import Utilisateur
from apps.utilisateurs.serializers import UtilisateurCreateSerializer, UtilisateurDetailSerializer
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from sis_common.authorization import (
    configured_permission_groups,
    has_business_permission,
    has_business_permission_or_role,
    permission_snapshot,
    request_has_business_access,
    user_in_configured_groups,
    validate_account_authorization_changes,
)


class FakeGroups:
    def __init__(self, names):
        self.names = names

    def filter(self, **_lookups):
        return self

    def order_by(self, _field):
        return self

    def values_list(self, _field, flat=False):
        return self.names if flat else [(name,) for name in self.names]


class FakeUser:
    is_authenticated = True
    is_superuser = False
    is_staff = False
    role = "custom_role"

    def __init__(self, permissions=(), attributes=None, groups=()):
        self.permissions = set(permissions)
        self.attributs_acces = attributes or {}
        self.groups = FakeGroups(groups)

    def has_perm(self, permission):
        return permission in self.permissions

    def get_all_permissions(self):
        return self.permissions


class FakeTenant:
    def __init__(self, configuration):
        self.configuration_academique = configuration


class FakeRequest:
    def __init__(self, user, configuration=None):
        self.user = user
        self.tenant = FakeTenant(configuration or {})


class PartnerAccountContractTests(SimpleTestCase):
    def test_partner_is_accepted_and_displayed_without_a_staff_or_learner_identity(self):
        create = UtilisateurCreateSerializer()
        role = create.fields["role"].run_validation("partenaire")
        user = Utilisateur(username="partner-contract", role=role)
        assert user.get_role_display() == "Partenaire"
        assert not user.is_staff and not user.is_superuser
        assert not any(
            getattr(user, flag, False) for flag in ("is_eleve", "is_etudiant", "is_enseignant", "is_parent", "is_admin")
        )
        for serializer_class in (UtilisateurCreateSerializer, UtilisateurDetailSerializer):
            field = serializer_class().fields["role"]
            for existing_role, label in Utilisateur.ROLE_CHOICES:
                assert field.run_validation(existing_role) == existing_role
                assert Utilisateur(role=existing_role).get_role_display() == label
            assert field.run_validation("institution_custom") == "institution_custom"
            for invalid in ("", None, "x" * 101):
                with self.assertRaises(ValidationError):
                    field.run_validation(invalid)

    def test_partner_role_does_not_bypass_authorization_change_validation(self):
        user = Utilisateur(role="partenaire")
        request = SimpleNamespace(user=user)
        default = Utilisateur._meta.get_field("role").default
        for instance, attrs in ((None, {"role": "partenaire"}), (user, {"role": "enseignant"})):
            with self.assertRaises(ValidationError):
                validate_account_authorization_changes(request, instance, attrs, attrs, default_role=default)
        for field in ("groups", "user_permissions", "attributs_acces"):
            attrs = {field: []}
            with self.assertRaises(ValidationError):
                validate_account_authorization_changes(request, user, attrs, attrs, default_role=default)
        validate_account_authorization_changes(
            request, user, {"role": "partenaire"}, {"role": "partenaire"}, default_role=default
        )


class AuthorizationTests(SimpleTestCase):
    def test_staff_does_not_grant_business_permissions(self):
        for role, permission in (
            ("enseignant", "paiements.change_paiement"),
            ("comptable", "notes.change_note"),
        ):
            for staff in (False, True):
                user = FakeUser()
                user.role = role
                user.is_staff = staff
                assert not has_business_permission_or_role(user, permission)

    def test_staff_keeps_explicit_permissions_and_their_constraints(self):
        permission = "notes.change_note"
        user = FakeUser(
            permissions=[permission],
            attributes={"permission_scopes": {permission: {"classes": [2]}}},
        )
        user.is_staff = True
        user.role = "direction"
        assert not has_business_permission_or_role(user, permission, ("direction",))
        assert not has_business_permission_or_role(user, permission, ("direction",), context={"classes": 3})
        assert has_business_permission_or_role(user, permission, ("direction",), context={"classes": 2})

    def test_superuser_business_access_does_not_require_staff(self):
        user = FakeUser()
        user.is_superuser = True
        assert has_business_permission_or_role(user, "notes.change_note")

    def test_permission_scope_requires_context(self):
        permission = "notes.view_note"
        user = FakeUser(
            permissions=[permission],
            attributes={"permission_scopes": {permission: {"classes": [1, 2]}}},
        )

        assert not has_business_permission(user, permission)
        assert has_business_permission(user, permission, {"classes": 2})
        assert not has_business_permission(user, permission, {"classes": 3})

    def test_dynamic_permission_precedes_legacy_role_fallback(self):
        permission = "notes.change_reglevalidation"
        user = FakeUser(permissions=[permission])

        assert has_business_permission_or_role(user, permission, ("direction",))

        legacy_user = FakeUser()
        legacy_user.role = "direction"
        assert has_business_permission_or_role(legacy_user, permission, ("direction",))

    def test_configured_permission_groups_are_resolved_from_permissions_and_attributes(self):
        configuration = {
            "permission_groups": [
                {
                    "code": "finance_manager",
                    "label": "Finance",
                    "permissions": ["paiements.view_paiement", "paiements.change_paiement"],
                    "attributes": {"domains": ["finance"]},
                }
            ]
        }
        user = FakeUser(
            permissions=["paiements.view_paiement", "paiements.change_paiement"],
            attributes={"domains": ["finance"]},
        )

        assert configured_permission_groups(user, configuration) == ["finance_manager"]

    def test_permission_snapshot_merges_django_and_configured_groups(self):
        configuration = {
            "permission_groups": [
                {
                    "code": "finance_manager",
                    "label": "Finance",
                    "permissions": ["paiements.view_paiement"],
                    "attributes": {"domains": ["finance"]},
                }
            ]
        }
        user = FakeUser(
            permissions=["paiements.view_paiement"],
            attributes={"domains": ["finance"]},
            groups=["staff"],
        )

        snapshot = permission_snapshot(user, configuration)

        assert snapshot["groups"] == ["finance_manager", "staff"]

    def test_user_in_configured_groups_supports_backend_authorization(self):
        configuration = {
            "permission_groups": [
                {
                    "code": "academic_admin_superieur",
                    "label": "Admin",
                    "permissions": ["utilisateurs.view_utilisateur"],
                    "attributes": {"campus": ["centre"]},
                }
            ]
        }
        user = FakeUser(
            permissions=["utilisateurs.view_utilisateur"],
            attributes={"campus": "centre"},
        )

        assert user_in_configured_groups(user, configuration, ("academic_admin_superieur",))
        assert not user_in_configured_groups(user, configuration, ("finance_manager_superieur",))

    def test_tenant_group_can_authorize_when_permission_is_missing(self):
        configuration = {
            "permission_groups": [
                {
                    "code": "document_signatory_superieur",
                    "label": "Signataire",
                    "permissions": ["diplomes.change_cessiondiplome"],
                    "attributes": {},
                }
            ]
        }
        user = FakeUser(permissions=["diplomes.change_cessiondiplome"])

        assert has_business_permission_or_role(
            user,
            "releves.change_transcript",
            configuration=configuration,
            tenant_group_codes=("document_signatory_superieur",),
        )

    def test_request_helper_reads_tenant_configuration(self):
        configuration = {
            "permission_groups": [
                {
                    "code": "exam_manager_secondary",
                    "label": "Examens",
                    "permissions": ["examens.change_sessionexamen"],
                    "attributes": {},
                }
            ]
        }
        request = FakeRequest(
            FakeUser(permissions=["examens.change_sessionexamen"]),
            configuration,
        )

        assert request_has_business_access(
            request, "examens.view_convocationexamen", tenant_group_codes=("exam_manager_secondary",)
        )

    def test_request_helper_supports_new_workflow_groups(self):
        configuration = {
            "permission_groups": [
                {
                    "code": "memoire_manager_superieur",
                    "label": "Mémoires",
                    "permissions": ["memoires.change_memoire"],
                    "attributes": {},
                }
            ]
        }
        request = FakeRequest(
            FakeUser(permissions=["memoires.change_memoire"]),
            configuration,
        )

        assert request_has_business_access(
            request, "memoires.change_jurymemoire", tenant_group_codes=("memoire_manager_superieur",)
        )

    def test_request_helper_supports_core_management_groups(self):
        configuration = {
            "permission_groups": [
                {
                    "code": "student_manager_superieur",
                    "label": "Étudiants",
                    "permissions": ["etudiants.change_etudiant"],
                    "attributes": {},
                }
            ]
        }
        request = FakeRequest(
            FakeUser(permissions=["etudiants.change_etudiant"]),
            configuration,
        )

        assert request_has_business_access(
            request, "etudiants.change_inscriptionadministrative", tenant_group_codes=("student_manager_superieur",)
        )

    def test_request_helper_supports_remaining_management_groups(self):
        configuration = {
            "permission_groups": [
                {
                    "code": "research_manager_superieur",
                    "label": "Recherche",
                    "permissions": ["recherche.change_laboratoire"],
                    "attributes": {},
                }
            ]
        }
        request = FakeRequest(
            FakeUser(permissions=["recherche.change_laboratoire"]),
            configuration,
        )

        assert request_has_business_access(
            request, "recherche.change_these", tenant_group_codes=("research_manager_superieur",)
        )

    def test_request_helper_supports_legacy_read_roles(self):
        request = FakeRequest(FakeUser())
        request.user.role = "parent"

        assert request_has_business_access(request, "notes.view_note", ("parent",))

    def test_request_helper_supports_portal_group_access(self):
        configuration = {
            "permission_groups": [
                {
                    "code": "portal_admin",
                    "label": "Portail",
                    "permissions": ["formations.view_formation"],
                    "attributes": {"facultes": [4]},
                }
            ]
        }
        request = FakeRequest(
            FakeUser(
                permissions=["formations.view_formation"],
                attributes={"facultes": [4]},
            ),
            configuration,
        )

        assert request_has_business_access(request, "etudiants.view_etudiant", tenant_group_codes=("portal_admin",))
