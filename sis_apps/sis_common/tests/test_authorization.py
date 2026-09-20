from django.test import SimpleTestCase
from sis_common.authorization import (
    has_business_permission,
    has_business_permission_or_role,
)


class FakeUser:
    is_authenticated = True
    is_superuser = False
    is_staff = False
    role = "custom_role"

    def __init__(self, permissions=(), attributes=None):
        self.permissions = set(permissions)
        self.attributs_acces = attributes or {}

    def has_perm(self, permission):
        return permission in self.permissions


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
