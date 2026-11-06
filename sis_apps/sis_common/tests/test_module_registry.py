from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from rest_framework.exceptions import PermissionDenied, ValidationError

from sis_common.module_registry import effective_modules, module_snapshot, require_module, validate_module_changes


class ModuleActivationFlagTests(TestCase):
    def test_non_boolean_persisted_flags_do_not_enable_a_module(self):
        tenant = SimpleNamespace(pk=11)
        for value in ("false", "true", 1, 0, None, [], ["enabled"], {}, {"enabled": True}):
            with self.subTest(value=value):
                configuration = SimpleNamespace(revision=1, enabled={"sis.complaints": value})
                with patch("sis_common.module_registry.module_configuration", return_value=configuration):
                    snapshot = module_snapshot(tenant)
                    self.assertIs(snapshot["enabled"]["sis.complaints"], False)
                    manifest = next(item for item in snapshot["modules"] if item["identifier"] == "sis.complaints")
                    self.assertIs(manifest["enabled"], False)
                    with self.assertRaises(PermissionDenied):
                        require_module(tenant, "sis.complaints")
                    require_module(tenant, "sis.delegations")

    def test_invalid_dependency_requires_explicit_boolean_reactivation(self):
        tenant = SimpleNamespace(pk=11)
        for value in ("false", 1, ["enabled"], {"enabled": True}):
            with self.subTest(value=value):
                current = {"core.notifications": value, "sis.complaints": True, "sis.delegations": True}
                configuration = SimpleNamespace(revision=1, enabled=current)
                with patch("sis_common.module_registry.module_configuration", return_value=configuration):
                    for identifier in ("core.notifications", "sis.complaints", "sis.delegations"):
                        self.assertIs(module_snapshot(tenant)["enabled"][identifier], False)
                        with self.assertRaises(PermissionDenied):
                            require_module(tenant, identifier)
                    with self.assertRaises(ValidationError):
                        validate_module_changes(current, {"sis.complaints": True})
                    configuration.enabled = validate_module_changes(current, {"core.notifications": True})
                    for identifier in ("core.notifications", "sis.complaints", "sis.delegations"):
                        self.assertIs(module_snapshot(tenant)["enabled"][identifier], True)
                        require_module(tenant, identifier)
                self.assertEqual(current["core.notifications"], value)

    def test_boolean_deactivation_and_reactivation_preserve_other_module_flags(self):
        current = validate_module_changes({}, {"sis.complaints": False, "sis.delegations": False})
        self.assertIs(effective_modules(current)["sis.complaints"], False)
        restored = validate_module_changes(current, {"sis.complaints": True})
        self.assertIs(effective_modules(restored)["sis.complaints"], True)
        self.assertIs(effective_modules(restored)["sis.delegations"], False)
        self.assertIs(current["sis.complaints"], False)
