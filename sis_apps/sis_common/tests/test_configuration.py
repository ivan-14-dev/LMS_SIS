from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from sis_common.academic_configuration import (
    academic_configuration_schema,
    catalog_label,
    default_academic_configuration,
    merge_academic_configuration,
    resolve_exam_result_workflow,
    resolve_financial_workflow,
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

        assert merged["grading_scale"]["minimum"] == 0
        assert merged["grading_scale"]["maximum"] == 100
        assert merged["catalogs"]["formation_levels"][0]["code"] == "foundation"

    def test_custom_catalogs_are_validated_and_resolved(self):
        configuration = default_academic_configuration()
        configuration["catalogs"]["formation_types"] = [{"code": "bootcamp", "label": "Bootcamp"}]

        validate_academic_configuration(configuration)

        assert catalog_label(configuration, "formation_types", "bootcamp") == "Bootcamp"

    def test_duplicate_catalog_codes_are_rejected(self):
        configuration = default_academic_configuration()
        configuration["catalogs"]["subject_types"] = [
            {"code": "core", "label": "Core"},
            {"code": "core", "label": "Duplicate"},
        ]

        with pytest.raises(ValidationError):
            validate_academic_configuration(configuration)

    def test_invalid_grading_scale_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["grading_scale"] = {
            "minimum": 20,
            "maximum": 10,
            "pass_mark": 15,
        }

        with pytest.raises(ValidationError):
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

        with pytest.raises(ValidationError):
            validate_academic_configuration(configuration)

    def test_academic_configuration_schema_exposes_supported_dimensions_and_datasets(self):
        schema = academic_configuration_schema("superieur")

        assert {"code": "financial", "label": "Financier"} in schema["dimension_axes"]
        assert {"code": "pdf", "label": "PDF"} in schema["report_export_formats"]
        assert {"code": "exam_grades", "label": "Notes d'épreuves / examens"} in schema["import_template_types"]
        assert {"code": "evaluation", "label": "Évaluations / sujets"} in schema["submission_window_types"]
        assert {"code": "doyen", "label": "Doyen de faculté"} in schema["submission_window_recipient_roles"]
        assert {"code": "object_label", "label": "Libellé de l'évaluation / épreuve"} in schema["submission_window_template_variables"]
        assert {"code": "warning", "label": "Avertissement"} in schema["submission_window_severities"]
        assert {"code": "email", "label": "Email"} in schema["submission_window_notification_channels"]
        payments_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "financial_payments"
        )
        averages_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "averages_ecue"
        )
        exam_results_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "exam_results"
        )

        assert payments_dataset["label"] == "Paiements"
        assert {"code": "rubrique", "label": "Rubrique"} in payments_dataset["allowed_filters"]
        assert {"code": "moyenne", "label": "Moyenne"} in averages_dataset["fields"]
        assert {"code": "ecue", "label": "ECUE"} in exam_results_dataset["fields"]
        assert "bulletins" not in {dataset["code"] for dataset in schema["report_datasets"]}

    def test_secondary_schema_exposes_bulletins_without_university_average_datasets(self):
        schema = academic_configuration_schema("secondaire")
        dataset_codes = {dataset["code"] for dataset in schema["report_datasets"]}
        bulletins_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "bulletins"
        )
        exam_results_dataset = next(
            dataset for dataset in schema["report_datasets"] if dataset["code"] == "exam_results"
        )

        assert "bulletins" in dataset_codes
        assert "exam_results" in dataset_codes
        assert "averages_ecue" not in dataset_codes
        assert {"code": "moyenne_generale", "label": "Moyenne générale"} in bulletins_dataset["fields"]
        assert {"code": "pdf", "label": "PDF"} in exam_results_dataset["export_formats"]

    def test_default_configuration_includes_reusable_permission_groups(self):
        configuration = default_academic_configuration()
        codes = {group["code"] for group in configuration["permission_groups"]}

        assert "exam_manager_secondary" in codes
        assert "exam_manager_superieur" in codes
        assert "finance_manager_secondary" in codes
        assert "finance_manager_superieur" in codes
        assert "attendance_manager_secondary" in codes
        assert "boarding_manager_secondary" in codes
        assert "canteen_manager_secondary" in codes
        assert "class_manager_secondary" in codes
        assert "class_council_manager_secondary" in codes
        assert "club_manager_secondary" in codes
        assert "ects_manager_superieur" in codes
        assert "enterprise_relations_manager_superieur" in codes
        assert "health_manager_secondary" in codes
        assert "jury_manager_superieur" in codes
        assert "library_manager_secondary" in codes
        assert "memoire_manager_superieur" in codes
        assert "mobility_manager_superieur" in codes
        assert "curriculum_manager_superieur" in codes
        assert "registration_manager_superieur" in codes
        assert "research_manager_superieur" in codes
        assert "retake_manager_superieur" in codes
        assert "schedule_manager_secondary" in codes
        assert "stage_manager_secondary" in codes
        assert "student_manager_secondary" in codes
        assert "student_manager_superieur" in codes
        assert "transport_manager_secondary" in codes
        assert "document_signatory_superieur" in codes

    def test_default_configuration_includes_strict_continuous_assessment_import_template(self):
        configuration = default_academic_configuration()
        template = next(
            item
            for item in configuration["import_templates"]
            if item["code"] == "continuous_assessment_grades"
        )

        assert template["columns"] == ["matricule", "note", "appreciation", "statut"]
        assert template["strict_columns"]

    def test_submission_window_settings_are_merged_with_defaults(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"default_close_offset_hours": 12, "reminder_hours": [6, 1]}
        }

        settings = resolve_submission_window_settings(configuration, "evaluation")

        assert settings["enabled"]
        assert settings["default_open_offset_hours"] == 0
        assert settings["default_close_offset_hours"] == 12
        assert settings["reminder_hours"] == [6, 1]
        assert settings["notify_assigned_users"]
        assert settings["recipient_role_codes"] == []
        assert settings["recipient_group_codes"] == []
        assert settings["title_template"] == "Clôture de soumission imminente"
        assert "{object_label}" in settings["message_template"]
        assert settings["notification_category"] == "submission_deadline"
        assert settings["notification_severity"] == "warning"
        assert settings["notification_channels"] == ["in_app"]
        assert settings["sms_gateway_url"] == ""
        assert settings["webhook_urls"] == []

    def test_invalid_submission_window_configuration_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"reminder_hours": ["24h"]},
        }

        with pytest.raises(ValidationError):
            validate_academic_configuration(configuration)

    def test_invalid_submission_window_recipient_configuration_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"recipient_group_codes": ["", "finance_manager_secondary"]},
        }

        with pytest.raises(ValidationError):
            validate_academic_configuration(configuration)

    def test_invalid_submission_window_template_configuration_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"title_template": ""},
        }

        with pytest.raises(ValidationError):
            validate_academic_configuration(configuration)

    def test_invalid_submission_window_notification_configuration_is_rejected(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"notification_severity": "urgent", "notification_channels": ["fax"]},
        }

        with pytest.raises(ValidationError):
            validate_academic_configuration(configuration)

    def test_invalid_submission_window_channel_endpoints_are_rejected(self):
        configuration = default_academic_configuration()
        configuration["submission_windows"] = {
            "evaluation": {"sms_gateway_url": "notaurl", "webhook_urls": ["https://valid.example/hook", ""]},
        }

        with pytest.raises(ValidationError):
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
                "sms_gateway_url": "https://sms.example.test/send",
                "webhook_urls": ["https://hooks.example.test/deadline"],
            }
        }
        instance = DummySubmissionObject(timezone.now() + timedelta(hours=3))

        notification = get_submission_window_notification_content(instance, configuration, "evaluation")

        assert notification["title"] == "Rappel évaluation"
        assert "DS Math 6e A" in notification["message"]
        assert notification["category"] == "custom_deadline"
        assert notification["severity"] == "critical"
        assert notification["channels"] == ["in_app", "email"]
        assert notification["sms_gateway_url"] == "https://sms.example.test/send"
        assert notification["webhook_urls"] == ["https://hooks.example.test/deadline"]

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

        assert policy["code"] == "class-specific"

    def test_financial_workflow_transition_must_match_configuration(self):
        configuration = default_academic_configuration()
        workflow = resolve_financial_workflow(
            configuration,
            {"scope": "tenant", "context": {"tenant_id": 1}},
        )

        assert workflow_transition_allowed(workflow, "valider", "en_attente", "valide")
        assert not workflow_transition_allowed(workflow, "valider", "valide", "rembourse")

    def test_resolve_exam_result_workflow_prefers_matching_variant(self):
        configuration = default_academic_configuration()

        workflow = resolve_exam_result_workflow(
            configuration,
            {"scope": "tenant", "context": {"tenant_id": 7}},
            variant="secondaire",
        )

        assert workflow["code"] == "default_secondary_exam_results"

        superior_workflow = resolve_exam_result_workflow(
            configuration,
            {"scope": "tenant", "context": {"tenant_id": 7}},
            variant="superieur",
        )

        assert superior_workflow["code"] == "default_superior_exam_results"
