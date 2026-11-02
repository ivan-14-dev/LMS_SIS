from django.core.exceptions import ValidationError
from rest_framework import serializers

from sis_common.learning_offerings import offering_grade_result


class GradeLearnerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    matricule = serializers.CharField(read_only=True)
    nom = serializers.CharField(source="user.get_full_name", read_only=True)


def validate_assessment_scale(attrs, instance):
    for name, default in (("bareme", 20), ("coefficient", 1)):
        value = attrs.get(name, getattr(instance, name, default))
        if value <= 0:
            raise serializers.ValidationError({name: "La valeur doit être strictement positive."})


def validate_offering_grade(evaluation, value, result, status):
    try:
        return offering_grade_result(evaluation, value, result, status)
    except ValidationError as error:
        raise serializers.ValidationError({"resultat": error.messages}) from error


def ensure_numeric_import(evaluation):
    if evaluation.offre_configuration.get("assessment", {}).get("mode", "numeric") != "numeric":
        raise serializers.ValidationError(
            {
                "evaluation": (
                    "L'import Excel de notes est réservé aux évaluations chiffrées. "
                    "Utilisez la saisie des résultats."
                )
            }
        )


def validate_grade_batch(items, learner_field, evaluation):
    seen = set()
    for item in items:
        learner = item[learner_field]
        if learner in seen:
            raise serializers.ValidationError({learner_field: "Un apprenant ne peut apparaître qu'une fois par lot."})
        seen.add(learner)
        value = item["valeur"]
        bareme = evaluation.bareme
        if value is not None and not 0 <= value <= bareme:
            raise serializers.ValidationError({"valeur": f"La note doit être comprise entre 0 et {bareme}."})
        validate_offering_grade(evaluation, value, item.get("resultat", {}), item.get("statut", "presente"))
