from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from sis_common.academic_configuration import (
    academic_configuration_schema,
    catalog_label,
    default_academic_configuration,
    merge_academic_configuration,
    resolve_financial_workflow,
    resolve_validation_policy,
    validate_academic_configuration,
    workflow_transition_allowed,
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

    def test_extended_metamodel_sections_are_valid(self):
        configuration = default_academic_configuration()
        configuration["permission_groups"] = [
            {
                "code": "finance_manager",
                "label": "Gestion financière",
                "permissions": ["paiements.view_paiement", "paiements.change_paiement"],
                "attributes": {"domains": ["finance"]},
            }
        ]
        configuration["validation_policies"] = [
            {
                "code": "lmd-fr",
                "label": "LMD francophone",
                "scope": "semester",
                "thresholds": {"minimum_average": 10, "minimum_credits": 30},
                "criteria": {"financial_status": {"operator": "in", "value": ["ok", "waived"]}},
                "publication": {"requires_financial_clearance": True},
            }
        ]
        configuration["financial_workflows"] = [
            {
                "code": "fees",
                "label": "Paiements",
                "scope": "academic_year",
                "steps": [
                    {"code": "submitted", "label": "Soumis"},
                    {"code": "validated", "label": "Validé", "terminal": True},
                ],
            }
        ]
        configuration["reports"] = [
            {
                "code": "payments",
                "label": "Paiements validés",
                "dataset": "financial_payments",
                "fields": ["numero", "montant"],
                "allowed_filters": ["annee", "statut"],
                "required_permissions": ["paiements.view_paiement"],
            }
        ]

        validate_academic_configuration(configuration)

    def test_invalid_report_dataset_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["reports"] = [
            {
                "code": "legacy",
                "label": "Legacy",
                "dataset": "unsupported",
                "fields": ["numero"],
                "allowed_filters": [],
            }
        ]

        with self.assertRaises(ValidationError):
            validate_academic_configuration(configuration)

    def test_academic_configuration_schema_exposes_supported_dimensions_and_datasets(self):
        schema = academic_configuration_schema()

        self.assertIn({"code": "financial", "label": "Financier"}, schema["dimension_axes"])
        self.assertIn({"code": "financial_payments", "label": "Paiements"}, schema["report_datasets"])

    def test_default_configuration_includes_reusable_permission_groups(self):
        configuration = default_academic_configuration()
        codes = {group["code"] for group in configuration["permission_groups"]}

        self.assertIn("exam_manager_secondary", codes)
        self.assertIn("exam_manager_superieur", codes)
        self.assertIn("finance_manager_secondary", codes)
        self.assertIn("finance_manager_superieur", codes)
        self.assertIn("attendance_manager_secondary", codes)
        self.assertIn("class_manager_secondary", codes)
        self.assertIn("class_council_manager_secondary", codes)
        self.assertIn("jury_manager_superieur", codes)
        self.assertIn("memoire_manager_superieur", codes)
        self.assertIn("mobility_manager_superieur", codes)
        self.assertIn("registration_manager_superieur", codes)
        self.assertIn("retake_manager_superieur", codes)
        self.assertIn("schedule_manager_secondary", codes)
        self.assertIn("stage_manager_secondary", codes)
        self.assertIn("student_manager_secondary", codes)
        self.assertIn("student_manager_superieur", codes)
        self.assertIn("document_signatory_superieur", codes)

    def test_resolve_validation_policy_prefers_most_specific_target(self):
        configuration = default_academic_configuration()
        configuration["validation_policies"] = [
            {
                "code": "tenant",
                "label": "Tenant",
                "scope": "tenant",
                "thresholds": {"seuil_moyenne": 10},
            },
            {
                "code": "class-specific",
                "label": "Classe",
                "scope": "class",
                "targets": {"class_id": 42},
                "thresholds": {"seuil_moyenne": 12},
            },
        ]

        policy = resolve_validation_policy(
            configuration,
            [
                {"scope": "class", "context": {"class_id": 42}},
                {"scope": "tenant", "context": {"tenant_id": 7}},
            ],
        )

        self.assertEqual(policy["code"], "class-specific")

    def test_financial_workflow_transition_must_match_configuration(self):
        configuration = default_academic_configuration()
        workflow = resolve_financial_workflow(
            configuration,
            {"scope": "tenant", "context": {"tenant_id": 1}},
        )

        self.assertTrue(workflow_transition_allowed(workflow, "valider", "en_attente", "valide"))
        self.assertFalse(workflow_transition_allowed(workflow, "valider", "valide", "rembourse"))
