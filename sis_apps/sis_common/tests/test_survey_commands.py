from copy import deepcopy
from unittest import TestCase

from sis_common.survey_serializers import RespondCommand, SurveyCommand


class SurveyCommandTests(TestCase):
    def setUp(self):
        self.payload = {
            "titre": "Services",
            "politique": "nominative",
            "destinataires": [11, 12],
            "questionnaire": [
                {"id": "avis", "libelle": "Avis", "type": "texte"},
                {"id": "choix", "libelle": "Accueil", "type": "choix", "choix": ["Bien", "À améliorer"]},
            ],
        }

    def test_only_bounded_explicitly_nominative_questionnaires_are_accepted(self):
        assert SurveyCommand(data=self.payload).is_valid()
        for field, value in (
            ("politique", "anonyme"),
            ("anonyme", True),
            ("destinataires", [11, 11]),
            ("destinataires", list(range(1, 202))),
            ("destinataires", []),
            ("questionnaire", []),
            ("questionnaire", self.payload["questionnaire"] * 2),
            ("questionnaire", [{"id": f"q{index}", "libelle": "Avis", "type": "texte"} for index in range(21)]),
            ("questionnaire", [{"id": "q", "libelle": "Avis", "type": "choix", "choix": ["A", "A"]}]),
            ("questionnaire", [{"id": "q", "libelle": "Avis", "type": "texte", "choix": ["A", "B"]}]),
        ):
            with self.subTest(field=field, value=value):
                assert not SurveyCommand(data={**self.payload, field: value}).is_valid()
        payload = deepcopy(self.payload)
        del payload["politique"]
        assert not SurveyCommand(data=payload).is_valid()

    def test_answers_require_exact_questions_and_valid_single_choice(self):
        context = {"questionnaire": self.payload["questionnaire"]}
        for answers, valid in (
            ({"avis": "Bonjour", "choix": "Bien"}, True),
            ({"avis": " ", "choix": "Bien"}, False),
            ({"avis": "Bonjour", "choix": "Autre"}, False),
            ({"avis": "x" * 2001, "choix": "Bien"}, False),
            ({"avis": "Bonjour"}, False),
            ({"avis": "Bonjour", "choix": "Bien", "extra": "non"}, False),
        ):
            with self.subTest(answers=answers):
                command = RespondCommand(data={"politique": "nominative", "reponses": answers}, context=context)
                assert command.is_valid() is valid, command.errors
