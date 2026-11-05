"""Validation shared by the two examination result APIs."""

from rest_framework import serializers


class ExamDefinitionValidationMixin:
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and self.instance.resultats.exists():
            for field in ("session", "matiere", "ecue", "bareme", "classes", "nombre_corrections"):
                if field not in attrs:
                    continue
                old = getattr(self.instance, field)
                changed = (
                    set(old.values_list("pk", flat=True)) != {item.pk for item in attrs[field]}
                    if field == "classes"
                    else old != attrs[field]
                )
                if changed:
                    raise serializers.ValidationError(
                        {field: "Cette épreuve possède des résultats. Sa définition académique est conservée."}
                    )
        return attrs


class ExamResultValidationMixin:
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "statut" in self.initial_data:
            raise serializers.ValidationError(
                {"statut": "Utilisez les actions de soumission, vérification, validation ou publication."}
            )
        if self.instance:
            for field in ("epreuve", "eleve", "etudiant"):
                if field in attrs and attrs[field].pk != getattr(self.instance, f"{field}_id"):
                    raise serializers.ValidationError(
                        {field: "Le rattachement d'un résultat existant ne peut pas être modifié."}
                    )
        exam = attrs.get("epreuve", getattr(self.instance, "epreuve", None))
        grade = attrs.get("note", getattr(self.instance, "note", None))
        if exam and grade is not None and not 0 <= grade <= exam.bareme:
            raise serializers.ValidationError({"note": "La note doit respecter le barème de l'épreuve."})
        return attrs
