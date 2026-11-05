"""Versioned learning-offer configuration shared by both SIS variants."""

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from rest_framework import serializers, status
from rest_framework.response import Response

CALENDARS = {
    "annual": "Année scolaire",
    "semester": "Semestres",
    "session": "Sessions courtes",
    "continuous": "Entrées continues / rythme libre",
}
ASSESSMENT_MODES = {
    "numeric": "Notes chiffrées",
    "competency": "Compétences",
    "pass_fail": "Validé / non validé",
}
NUMERIC_ASSESSMENT = {"mode": "numeric", "minimum": 0, "maximum": 20, "pass_mark": 10}
COMPETENCY_ASSESSMENT = {
    "mode": "competency",
    "criteria": [{"code": "competence_1", "label": "Compétence à personnaliser"}],
}
PROFILES = {
    "primary": {
        "label": "École primaire",
        "calendar": "annual",
        "assessment": COMPETENCY_ASSESSMENT,
        "credits": None,
        "terminology": {"learner": "Élève", "educator": "Enseignant", "group": "Classe"},
    },
    "secondary": {
        "label": "Collège / lycée",
        "calendar": "annual",
        "assessment": NUMERIC_ASSESSMENT,
        "credits": None,
        "terminology": {"learner": "Élève", "educator": "Enseignant", "group": "Classe"},
    },
    "higher_education": {
        "label": "Université / grande école",
        "calendar": "semester",
        "assessment": NUMERIC_ASSESSMENT,
        "credits": {"system": "ECTS", "target": 60},
        "terminology": {"learner": "Étudiant", "educator": "Enseignant", "group": "Promotion"},
    },
    "vocational": {
        "label": "Formation professionnelle",
        "calendar": "session",
        "assessment": COMPETENCY_ASSESSMENT,
        "credits": None,
        "terminology": {"learner": "Stagiaire", "educator": "Formateur", "group": "Groupe"},
    },
    "custom": {
        "label": "Profil personnalisé",
        "calendar": "continuous",
        "assessment": {"mode": "pass_fail"},
        "credits": None,
        "terminology": {"learner": "Apprenant", "educator": "Formateur", "group": "Groupe"},
    },
}


def institutional_profile_schema():
    return {
        "profiles": [
            {
                "code": code,
                "label": profile["label"],
                "template": {"code": code, "profile": code, "version": 1, **deepcopy(profile)},
            }
            for code, profile in PROFILES.items()
        ],
        "calendars": [{"code": code, "label": label} for code, label in CALENDARS.items()],
        "assessment_modes": [{"code": code, "label": label} for code, label in ASSESSMENT_MODES.items()],
        "assessment_templates": {
            "numeric": deepcopy(NUMERIC_ASSESSMENT),
            "competency": deepcopy(COMPETENCY_ASSESSMENT),
            "pass_fail": {"mode": "pass_fail"},
        },
    }


def _object(value, keys, path):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValidationError(f"{path} exige les champs : {', '.join(sorted(keys))}.")


def _label(value, path):
    if not isinstance(value, str) or not value.strip() or len(value) > 240:
        raise ValidationError(f"{path} exige un libellé de 1 à 240 caractères.")


def _code(value, path):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value):
        raise ValidationError(f"{path} exige un code de 1 à 64 caractères : lettres minuscules, chiffres, _ ou -.")


def _number(value, path):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)) or len(str(value)) > 64:
        raise ValidationError(f"{path} doit être un nombre fini.")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationError(f"{path} doit être un nombre fini.") from exc
    if not result.is_finite():
        raise ValidationError(f"{path} doit être un nombre fini.")
    return result


def validate_learning_offering(value):
    _object(
        value,
        ("code", "label", "profile", "version", "calendar", "assessment", "credits", "terminology"),
        "Offre",
    )
    _code(value["code"], "Offre.code")
    _label(value["label"], "Offre.label")
    if not isinstance(value["profile"], str) or value["profile"] not in PROFILES:
        raise ValidationError("Le profil de l'offre est inconnu.")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValidationError("La version de profil n'est pas prise en charge.")
    if not isinstance(value["calendar"], str) or value["calendar"] not in CALENDARS:
        raise ValidationError("Le calendrier de l'offre est inconnu.")
    _object(value["terminology"], ("learner", "educator", "group"), "Terminologie")
    for key, label in value["terminology"].items():
        _label(label, f"Terminologie.{key}")

    assessment = value["assessment"]
    mode = assessment.get("mode") if isinstance(assessment, dict) else None
    if not isinstance(mode, str) or mode not in ASSESSMENT_MODES:
        raise ValidationError("Le mode d'évaluation est inconnu.")
    if mode == "numeric":
        _object(assessment, ("mode", "minimum", "maximum", "pass_mark"), "Évaluation chiffrée")
        minimum, maximum, pass_mark = (
            _number(assessment[key], f"Évaluation.{key}") for key in ("minimum", "maximum", "pass_mark")
        )
        if minimum >= maximum or not minimum <= pass_mark <= maximum:
            raise ValidationError("Le barème ou le seuil de réussite de l'offre est invalide.")
    elif mode == "competency":
        _object(assessment, ("mode", "criteria"), "Évaluation par compétences")
        criteria = assessment["criteria"]
        if not isinstance(criteria, list) or not criteria:
            raise ValidationError("Définissez au moins une compétence.")
        codes = set()
        for criterion in criteria:
            _object(criterion, ("code", "label"), "Compétence")
            _code(criterion["code"], "Compétence.code")
            _label(criterion["label"], "Compétence.label")
            if criterion["code"] in codes:
                raise ValidationError("Les codes des compétences doivent être uniques dans une offre.")
            codes.add(criterion["code"])
    else:
        _object(assessment, ("mode",), "Évaluation validé / non validé")

    credits = value["credits"]
    if credits is not None:
        _object(credits, ("system", "target"), "Crédits")
        _label(credits["system"], "Crédits.system")
        if _number(credits["target"], "Crédits.target") <= 0:
            raise ValidationError("Le nombre de crédits visés doit être strictement positif.")


def validate_bound_offering(offering):
    validate_learning_offering(offering)
    if offering["assessment"]["mode"] == "numeric":
        scale = offering["assessment"]
        values = [Decimal(str(scale[key])) for key in ("minimum", "maximum", "pass_mark")]
        if any(value < 0 or value > Decimal("999.99") or value % Decimal("0.01") for value in values):
            raise ValidationError("La saisie actuelle accepte des barèmes de 0 à 999,99 avec au plus deux décimales.")


def validate_learning_offerings(value):
    if not isinstance(value, list):
        raise ValidationError("learning_offerings doit être une liste.")
    codes = set()
    for offering in value:
        validate_learning_offering(offering)
        if offering["code"] in codes:
            raise ValidationError("Chaque offre doit avoir un code unique dans l'établissement.")
        codes.add(offering["code"])


def preview_offering_result(offering, result):
    """Simulate a policy without writing grades, credits or official decisions."""
    validate_learning_offering(offering)
    assessment = offering["assessment"]
    mode = assessment["mode"]
    if mode == "numeric":
        _object(result, ("score",), "Résultat chiffré")
        if result["score"] is None:
            return {"status": "incomplete", "detail": "Aucune note renseignée."}
        score = _number(result["score"], "Note")
        if not _number(assessment["minimum"], "Minimum") <= score <= _number(assessment["maximum"], "Maximum"):
            raise ValidationError("La note est hors du barème de cette offre.")
        passed = score >= _number(assessment["pass_mark"], "Seuil")
    elif mode == "competency":
        _object(result, ("criteria",), "Résultat par compétences")
        values = result["criteria"]
        codes = {criterion["code"] for criterion in assessment["criteria"]}
        if not isinstance(values, dict) or set(values) - codes:
            raise ValidationError("Le résultat contient des compétences inconnues.")
        if any(value is not None and type(value) is not bool for value in values.values()):
            raise ValidationError("Une compétence attend true, false ou null.")
        if any(values.get(code) is None for code in codes):
            return {"status": "incomplete", "detail": "Toutes les compétences doivent être renseignées."}
        passed = all(values.values())
    else:
        _object(result, ("passed",), "Résultat validé / non validé")
        if result["passed"] is None:
            return {"status": "incomplete", "detail": "Aucune décision renseignée."}
        if type(result["passed"]) is not bool:
            raise ValidationError("La décision attend true, false ou null.")
        passed = result["passed"]
    return {
        "status": "passed" if passed else "failed",
        "detail": "Critères satisfaits." if passed else "Critères non satisfaits.",
    }


class OfferingPreviewSerializer(serializers.Serializer):
    offering = serializers.JSONField(validators=[validate_learning_offering])
    result = serializers.JSONField()

    def validate(self, attrs):
        attrs["preview"] = preview_offering_result(attrs["offering"], attrs["result"])
        return attrs


class OfferingPreviewMixin:
    http_method_names = ["post", "options"]

    def post(self, request):
        if self.get_tenant(request) is None:
            return Response(
                {"detail": "Aucun établissement n'est associé à ce domaine."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = OfferingPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data["preview"])
