from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from sis_common.academic_configuration import (
    catalog_label,
    default_academic_configuration,
    merge_academic_configuration,
    validate_academic_configuration,
)


class AcademicConfigurationTests(SimpleTestCase):
    def test_partial_updates_preserve_nested_configuration(self):
        current = default_academic_configuration()
        current["catalogs"]["formation_levels"] = [{"code": "foundation", "label": "Foundation"}]

        merged = merge_academic_configuration(
            current,
            {"grading_scale": {"maximum": 100, "pass_mark": 50}},
        )

        self.assertEqual(merged["grading_scale"]["minimum"], 0)
        self.assertEqual(merged["grading_scale"]["maximum"], 100)
        self.assertEqual(merged["catalogs"]["formation_levels"][0]["code"], "foundation")

    def test_custom_catalogs_are_validated_and_resolved(self):
        configuration = default_academic_configuration()
        configuration["catalogs"]["formation_types"] = [{"code": "bootcamp", "label": "Bootcamp"}]

        validate_academic_configuration(configuration)

        self.assertEqual(
            catalog_label(configuration, "formation_types", "bootcamp"),
            "Bootcamp",
        )

    def test_duplicate_catalog_codes_are_rejected(self):
        configuration = default_academic_configuration()
        configuration["catalogs"]["subject_types"] = [
            {"code": "core", "label": "Core"},
            {"code": "core", "label": "Duplicate"},
        ]

        with self.assertRaises(ValidationError):
            validate_academic_configuration(configuration)

    def test_invalid_grading_scale_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["grading_scale"] = {
            "minimum": 20,
            "maximum": 10,
            "pass_mark": 15,
        }

        with self.assertRaises(ValidationError):
            validate_academic_configuration(configuration)
