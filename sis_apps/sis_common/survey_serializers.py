"""Bounded commands; never silently accept an anonymity or overwrite option."""

from rest_framework import serializers


class StrictCommand(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError(
                {"detail": "Champs inconnus : " + ", ".join(sorted(set(data) - set(self.fields)))}
            )
        return super().to_internal_value(data)


class QuestionCommand(StrictCommand):
    id = serializers.RegexField(r"^[a-zA-Z][a-zA-Z0-9_-]{0,39}$", max_length=40)
    libelle = serializers.CharField(max_length=300)
    type = serializers.ChoiceField(choices=["texte", "choix"])
    choix = serializers.ListField(child=serializers.CharField(max_length=120), max_length=10, default=list)

    def validate(self, attrs):
        options = attrs["choix"]
        if attrs["type"] == "texte" and options:
            raise serializers.ValidationError({"choix": "Une question texte ne comporte pas de choix."})
        if attrs["type"] == "choix" and (len(options) < 2 or len(set(options)) != len(options)):
            raise serializers.ValidationError({"choix": "Deux à dix choix distincts sont requis."})
        return attrs


class SurveyCommand(StrictCommand):
    titre = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=3000, allow_blank=True, default="")
    politique = serializers.ChoiceField(choices=["nominative"])
    questionnaire = QuestionCommand(many=True, min_length=1, max_length=20)
    destinataires = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=200)

    def validate_questionnaire(self, questions):
        if len({question["id"] for question in questions}) != len(questions):
            raise serializers.ValidationError("Les identifiants de questions doivent être distincts.")
        return questions

    def validate_destinataires(self, users):
        if len(set(users)) != len(users):
            raise serializers.ValidationError("Un destinataire ne peut être sélectionné deux fois.")
        return users


class VersionCommand(StrictCommand):
    version = serializers.IntegerField(min_value=1)


class ConfigureCommand(SurveyCommand):
    version = serializers.IntegerField(min_value=1)


class RevokeCommand(VersionCommand):
    destinataire = serializers.IntegerField(min_value=1)


class RespondCommand(StrictCommand):
    politique = serializers.ChoiceField(choices=["nominative"])
    reponses = serializers.DictField(child=serializers.CharField(max_length=2000))

    def validate_reponses(self, answers):
        questions = self.context["questionnaire"]
        if set(answers) != {question["id"] for question in questions}:
            raise serializers.ValidationError("Répondez à toutes les questions, sans ajouter de question.")
        for question in questions:
            if question["type"] == "choix" and answers[question["id"]] not in question["choix"]:
                raise serializers.ValidationError({question["id"]: "Choisissez une des réponses proposées."})
        return answers
