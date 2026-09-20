"""Model tests for notes."""

from decimal import Decimal

from apps.notes.models import RegleValidation
from django.test import SimpleTestCase


class NotesModelTestCase(SimpleTestCase):
    def test_validation_rule_accepts_configured_thresholds(self):
        rule = RegleValidation(
            seuil_moyenne=Decimal("12"),
            credits_minimum=Decimal("30"),
            max_ecues_echoues=2,
            note_eliminatoire=Decimal("5"),
        )

        result = rule.evaluer(
            moyenne=Decimal("13"),
            credits=Decimal("30"),
            ecues_echoues=1,
            note_minimale=Decimal("8"),
        )

        self.assertEqual(result, {"reussi": True, "motifs": []})

    def test_validation_rule_requires_custom_criterion_data(self):
        rule = RegleValidation(
            seuil_moyenne=Decimal("10"),
            credits_minimum=Decimal("0"),
            criteres={"memoire": {"operator": "eq", "value": "valide"}},
        )

        result = rule.evaluer(moyenne=Decimal("12"))

        self.assertEqual(result["motifs"], ["critere:memoire"])

    def test_validation_rule_applies_policy_overrides_and_financial_clearance(self):
        rule = RegleValidation(seuil_moyenne=Decimal("10"), credits_minimum=Decimal("30"))

        result = rule.evaluer(
            moyenne=Decimal("11"),
            credits=Decimal("29"),
            donnees={"financial_clearance": False},
            policy={
                "thresholds": {"seuil_moyenne": Decimal("12"), "credits_minimum": Decimal("30")},
                "publication": {"requires_financial_clearance": True},
            },
        )

        self.assertEqual(
            result["motifs"],
            ["moyenne_insuffisante", "credits_insuffisants", "financial_clearance_required"],
        )
