from django.test import SimpleTestCase
from sis_common.authorization import (
    configured_permission_groups,
    has_business_permission,
    has_business_permission_or_role,
    permission_snapshot,
    request_has_business_access,
    user_in_configured_groups,
)


class FakeGroups:
    def __init__(self, names):
        self.names = names

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


class AuthorizationTests(SimpleTestCase):
    def test_permission_scope_requires_context(self):
        permission = "notes.view_note"
        user = FakeUser(
            permissions=[permission],
            attributes={"permission_scopes": {permission: {"classes": [1, 2]}}},
        )

        self.assertFalse(has_business_permission(user, permission))
        self.assertTrue(has_business_permission(user, permission, {"classes": 2}))
        self.assertFalse(has_business_permission(user, permission, {"classes": 3}))

    def test_dynamic_permission_precedes_legacy_role_fallback(self):
        permission = "notes.change_reglevalidation"
        user = FakeUser(permissions=[permission])

        self.assertTrue(has_business_permission_or_role(user, permission, ("direction",)))

        legacy_user = FakeUser()
        legacy_user.role = "direction"
        self.assertTrue(has_business_permission_or_role(legacy_user, permission, ("direction",)))

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

        self.assertEqual(configured_permission_groups(user, configuration), ["finance_manager"])

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

        self.assertEqual(snapshot["groups"], ["finance_manager", "staff"])

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

        self.assertTrue(user_in_configured_groups(user, configuration, ("academic_admin_superieur",)))
        self.assertFalse(user_in_configured_groups(user, configuration, ("finance_manager_superieur",)))

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

        self.assertTrue(
            has_business_permission_or_role(
                user,
                "releves.change_transcript",
                configuration=configuration,
                tenant_group_codes=("document_signatory_superieur",),
            )
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

        self.assertTrue(
            request_has_business_access(
                request,
                "examens.view_convocationexamen",
                tenant_group_codes=("exam_manager_secondary",),
            )
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

        self.assertTrue(
            request_has_business_access(
                request,
                "memoires.change_jurymemoire",
                tenant_group_codes=("memoire_manager_superieur",),
            )
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

        self.assertTrue(
            request_has_business_access(
                request,
                "etudiants.change_inscriptionadministrative",
                tenant_group_codes=("student_manager_superieur",),
            )
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

        self.assertTrue(
            request_has_business_access(
                request,
                "recherche.change_these",
                tenant_group_codes=("research_manager_superieur",),
            )
        )

    def test_request_helper_supports_legacy_read_roles(self):
        request = FakeRequest(FakeUser())
        request.user.role = "parent"

        self.assertTrue(
            request_has_business_access(
                request,
                "notes.view_note",
                ("parent",),
            )
        )

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

        self.assertTrue(
            request_has_business_access(
                request,
                "etudiants.view_etudiant",
                tenant_group_codes=("portal_admin",),
            )
        )
