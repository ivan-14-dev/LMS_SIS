from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone
from sis_common.academic_configuration import (
    academic_configuration_schema,
    catalog_label,
    default_academic_configuration,
    merge_academic_configuration,
    resolve_financial_workflow,
    resolve_exam_result_workflow,
    resolve_submission_window_settings,
    resolve_validation_policy,
    validate_academic_configuration,
    workflow_transition_allowed,
)
from sis_common.submission_windows import get_submission_window_notification_content


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
                "formats": ["csv", "xlsx"],
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
        schema = academic_configuration_schema("superieur")

        self.assertIn({"code": "financial", "label": "Financier"}, schema["dimension_axes"])
        self.assertIn({"code": "pdf", "label": "PDF"}, schema["report_export_formats"])
        self.assertIn(
            {"code": "exam_grades", "label": "Notes d'épreuves / examens"},
            schema["import_template_types"],
        )
        self.assertIn(
            {"code": "evaluation", "label": "Évaluations / sujets"},
            schema["submission_window_types"],
        )
        self.assertIn(
            {"code": "doyen", "label": "Doyen de faculté"},
            schema["submission_window_recipient_roles"],
        )
        self.assertIn(
            {"code": "object_label", "label": "Libellé de l'évaluation / épreuve"},
            schema["submission_window_template_variables"],
        )
        self.assertIn(
            {"code": "warning", "label": "Avertissement"},
            schema["submission_window_severities"],
        )
        self.assertIn(
            {"code": "email", "label": "Email"},
            schema["submission_window_notification_channels"],
        )
        payments_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "financial_payments"
        )
        averages_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "averages_ecue"
        )
        exam_results_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "exam_results"
        )

        self.assertEqual(payments_dataset["label"], "Paiements")
        self.assertIn({"code": "rubrique", "label": "Rubrique"}, payments_dataset["allowed_filters"])
        self.assertIn({"code": "moyenne", "label": "Moyenne"}, averages_dataset["fields"])
        self.assertIn({"code": "ecue", "label": "ECUE"}, exam_results_dataset["fields"])
        self.assertNotIn("bulletins", {dataset["code"] for dataset in schema["report_datasets"]})

    def test_secondary_schema_exposes_bulletins_without_university_average_datasets(self):
        schema = academic_configuration_schema("secondaire")
        dataset_codes = {dataset["code"] for dataset in schema["report_datasets"]}
        bulletins_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "bulletins"
        )
        exam_results_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "exam_results"
        )

        self.assertIn("bulletins", dataset_codes)
        self.assertIn("exam_results", dataset_codes)
        self.assertNotIn("averages_ecue", dataset_codes)
        self.assertIn({"code": "moyenne_generale", "label": "Moyenne générale"}, bulletins_dataset["fields"])
        self.assertIn({"code": "pdf", "label": "PDF"}, exam_results_dataset["export_formats"])

    def test_default_configuration_includes_reusable_permission_groups(self):
        configuration = default_academic_configuration()
        codes = {group["code"] for group in configuration["permission_groups"]}

        self.assertIn("exam_manager_secondary", codes)
        self.assertIn("exam_manager_superieur", codes)
        self.assertIn("finance_manager_secondary", codes)
        self.assertIn("finance_manager_superieur", codes)
        self.assertIn("attendance_manager_secondary", codes)
        self.assertIn("boarding_manager_secondary", codes)
        self.assertIn("canteen_manager_secondary", codes)
        self.assertIn("class_manager_secondary", codes)
        self.assertIn("class_council_manager_secondary", codes)
        self.assertIn("club_manager_secondary", codes)
        self.assertIn("ects_manager_superieur", codes)
        self.assertIn("enterprise_relations_manager_superieur", codes)
        self.assertIn("health_manager_secondary", codes)
        self.assertIn("jury_manager_superieur", codes)
        self.assertIn("library_manager_secondary", codes)
        self.assertIn("memoire_manager_superieur", codes)
        self.assertIn("mobility_manager_superieur", codes)
        self.assertIn("curriculum_manager_superieur", codes)
        self.assertIn("registration_manager_superieur", codes)
        self.assertIn("research_manager_superieur", codes)
        self.assertIn("retake_manager_superieur", codes)
        self.assertIn("schedule_manager_secondary", codes)
        self.assertIn("stage_manager_secondary", codes)
        self.assertIn("student_manager_secondary", codes)
        self.assertIn("student_manager_superieur", codes)
        self.assertIn("transport_manager_secondary", codes)
        self.assertIn("document_signatory_superieur", codes)

    def test_default_configuration_includes_strict_continuous_assessment_import_template(self):
        configuration = default_academic_configuration()
        template = next(
            item
            for item in configuration["import_templates"]
            if item["code"] == "continuous_assessment_grades"
        )

        self.assertEqual(
            template["columns"],
            ["matricule", "note", "appreciation", "statut"],
        )
        self.assertTrue(template["strict_columns"])

    def test_submission_window_settings_are_merged_with_defaults(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"default_close_offset_hours": 12, "reminder_hours": [6, 1]}
        }

        settings = resolve_submission_window_settings(configuration, "evaluation")

        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["default_open_offset_hours"], 0)
        self.assertEqual(settings["default_close_offset_hours"], 12)
        self.assertEqual(settings["reminder_hours"], [6, 1])
        self.assertTrue(settings["notify_assigned_users"])
        self.assertEqual(settings["recipient_role_codes"], [])
        self.assertEqual(settings["recipient_group_codes"], [])
        self.assertEqual(settings["title_template"], "Clôture de soumission imminente")
        self.assertIn("{object_label}", settings["message_template"])
        self.assertEqual(settings["notification_category"], "submission_deadline")
        self.assertEqual(settings["notification_severity"], "warning")
        self.assertEqual(settings["notification_channels"], ["in_app"])

    def test_invalid_submission_window_configuration_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"reminder_hours": ["24h"]},
        }

        with self.assertRaises(ValidationError):
            validate_academic_configuration(configuration)

    def test_invalid_submission_window_recipient_configuration_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"recipient_group_codes": ["", "finance_manager_secondary"]},
        }

        with self.assertRaises(ValidationError):
            validate_academic_configuration(configuration)

    def test_invalid_submission_window_template_configuration_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"title_template": ""},
        }

        with self.assertRaises(ValidationError):
            validate_academic_configuration(configuration)

    def test_invalid_submission_window_notification_configuration_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"notification_severity": "urgent", "notification_channels": ["fax"]},
        }

        with self.assertRaises(ValidationError):
            validate_academic_configuration(configuration)

    def test_submission_window_notification_content_uses_configured_templates(self):
        class DummySubmissionObject:
            def __init__(self, fin_soumission):
                self.fin_soumission = fin_soumission

            def __str__(self):
                return "DS Math 6e A"

        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {
                "reminder_hours": [24],
                "title_template": "Rappel {object_type}",
                "message_template": "{object_label} ferme dans {threshold_hours}h le {deadline}",
                "notification_category": "custom_deadline",
                "notification_severity": "critical",
                "notification_channels": ["in_app", "email"],
            }
        }
        instance = DummySubmissionObject(timezone.now() + timedelta(hours=3))

        notification = get_submission_window_notification_content(instance, configuration, "evaluation")

        self.assertEqual(notification["title"], "Rappel évaluation")
        self.assertIn("DS Math 6e A", notification["message"])
        self.assertEqual(notification["category"], "custom_deadline")
        self.assertEqual(notification["severity"], "critical")
        self.assertEqual(notification["channels"], ["in_app", "email"])

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

    def test_resolve_exam_result_workflow_prefers_matching_variant(self):
        configuration = default_academic_configuration()

        workflow = resolve_exam_result_workflow(
            configuration,
            {"scope": "tenant", "context": {"tenant_id": 7}},
            variant="secondaire",
        )

        self.assertEqual(workflow["code"], "default_secondary_exam_results")

        superior_workflow = resolve_exam_result_workflow(
            configuration,
            {"scope": "tenant", "context": {"tenant_id": 7}},
            variant="superieur",
        )

        self.assertEqual(superior_workflow["code"], "default_superior_exam_results")
