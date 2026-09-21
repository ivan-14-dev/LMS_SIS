"""Model tests for notes."""

from decimal import Decimal

from apps.notes.models import RegleValidation
from django.test import SimpleTestCase


class NotesModelTestCase(SimpleTestCase):
    def test_validation_rule_reports_each_failed_criterion(self):
        rule = RegleValidation(
            seuil_moyenne=Decimal("10"),
            credits_minimum=Decimal("12"),
            max_matieres_echouees=1,
            note_eliminatoire=Decimal("5"),
        )

        result = rule.evaluer(
            moyenne=Decimal("9"),
            credits=Decimal("10"),
            matieres_echouees=2,
            note_minimale=Decimal("4"),
        )

        self.assertFalse(result["reussi"])
        self.assertEqual(
            result["motifs"],
            [
                "moyenne_insuffisante",
                "credits_insuffisants",
                "trop_de_matieres_echouees",
                "note_eliminatoire",
            ],
        )

    def test_validation_rule_evaluates_custom_criteria(self):
        rule = RegleValidation(
            seuil_moyenne=Decimal("10"),
            criteres={
                "assiduite": {"operator": "gte", "value": 80},
                "stage": {"operator": "in", "value": ["valide"]},
            },
        )

        result = rule.evaluer(
            moyenne=Decimal("12"),
            donnees={"assiduite": 75, "stage": "valide"},
        )

        self.assertEqual(result["motifs"], ["critere:assiduite"])

    def test_validation_rule_applies_tenant_policy_thresholds_and_financial_clearance(self):
        rule = RegleValidation(seuil_moyenne=Decimal("10"), credits_minimum=Decimal("0"))

        result = rule.evaluer(
            moyenne=Decimal("11"),
            donnees={"financial_clearance": False},
            policy={
                "thresholds": {"seuil_moyenne": Decimal("12")},
                "publication": {"requires_financial_clearance": True},
            },
        )

        self.assertEqual(
            result["motifs"],
            ["moyenne_insuffisante", "financial_clearance_required"],
        )
