"""Bindings and immutable policy snapshots for existing academic records."""

from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sis_common.institutional_profiles import preview_offering_result, validate_learning_offering


def validate_bound_offering(offering):
    validate_learning_offering(offering)
    if offering["assessment"]["mode"] == "numeric":
        scale = offering["assessment"]
        values = [Decimal(str(scale[key])) for key in ("minimum", "maximum", "pass_mark")]
        if any(value < 0 or value > Decimal("999.99") or value % Decimal("0.01") for value in values):
            raise ValidationError("La saisie actuelle accepte des barèmes de 0 à 999,99 avec au plus deux décimales.")


def offering_grade_result(evaluation, value, result, status):
    offering = evaluation.offre_configuration
    if not offering:
        if result:
            raise ValidationError("Les résultats non chiffrés exigent une évaluation rattachée à une offre.")
        return None
    mode = offering["assessment"]["mode"]
    if mode == "numeric":
        if result:
            raise ValidationError("Une évaluation chiffrée attend une note, pas un résultat par compétences.")
        payload = {"score": value}
    else:
        if value is not None:
            raise ValidationError("Une évaluation non chiffrée ne peut pas contenir de note numérique.")
        payload = result
    outcome = preview_offering_result(offering, payload)
    answers = payload["criteria"].values() if mode == "competency" else payload.values()
    if status != "presente" and any(answer is not None for answer in answers):
        raise ValidationError("Un résultat renseigné exige le statut Présentée.")
    return outcome


class ModelValidationSerializerMixin:
    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except ValidationError as error:
            raise serializers.ValidationError(
                error.message_dict if hasattr(error, "message_dict") else error.messages
            ) from error

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except ValidationError as error:
            raise serializers.ValidationError(
                error.message_dict if hasattr(error, "message_dict") else error.messages
            ) from error


class OfferingAssignmentSerializerMixin:
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "offre_code" not in attrs:
            return attrs
        code = attrs["offre_code"]
        if self.instance and code == self.instance.offre_code:
            return attrs
        if not code:
            attrs["offre_configuration"] = {}
            return attrs
        tenant = getattr(self.context.get("request"), "tenant", None)
        offerings = (getattr(tenant, "configuration_academique", {}) or {}).get("learning_offerings", [])
        offering = next((item for item in offerings if item["code"] == code), None)
        if offering is None:
            raise serializers.ValidationError({"offre_code": "Cette offre n'existe pas dans l'établissement courant."})
        try:
            validate_bound_offering(offering)
        except ValidationError as error:
            raise serializers.ValidationError({"offre_code": error.messages}) from error
        attrs["offre_configuration"] = deepcopy(offering)
        return attrs


class OfferingCatalogueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Aucun établissement associé à ce domaine."}, status=404)
        return Response((tenant.configuration_academique or {}).get("learning_offerings", []))


class OfferingSnapshotModel(models.Model):
    offre_configuration = models.JSONField(default=dict, blank=True, editable=False)
    offering_parent_path = ""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self._state.adding:
                parent = self
                for name in self.offering_parent_path.split("."):
                    parent = getattr(parent, name)
                parent = type(parent).objects.select_for_update().get(pk=parent.pk)
                self.offre_configuration = deepcopy(parent.offre_configuration)
                if self.offre_configuration:
                    validate_bound_offering(self.offre_configuration)
                    if hasattr(self, "bareme") and self.offre_configuration["assessment"]["mode"] == "numeric":
                        self.bareme = Decimal(str(self.offre_configuration["assessment"]["maximum"]))
            else:
                original = type(self).objects.select_for_update().get(pk=self.pk)
                if self.offre_configuration != original.offre_configuration:
                    raise ValidationError(
                        {"offre_configuration": "Les règles historisées ne peuvent pas être modifiées."}
                    )
                parent_field = self.offering_parent_path.split(".")[0]
                if original.offre_configuration and (
                    getattr(self, f"{parent_field}_id") != getattr(original, f"{parent_field}_id")
                ):
                    raise ValidationError(
                        {parent_field: "Le rattachement d'un dossier avec règles historisées est figé."}
                    )
                if original.offre_configuration and hasattr(self, "bareme") and self.bareme != original.bareme:
                    raise ValidationError(
                        {"bareme": "Le barème de cette évaluation est historisé et ne peut pas changer."}
                    )
            return super().save(*args, **kwargs)


class OfferingGradeModel(models.Model):
    resultat = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

    @property
    def resultat_offre(self):
        return offering_grade_result(self.evaluation, self.valeur, self.resultat, self.statut)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            original = type(self).objects.select_related("evaluation").get(pk=self.pk)
            if original.evaluation_id != self.evaluation_id and (
                original.evaluation.offre_configuration or self.evaluation.offre_configuration
            ):
                raise ValidationError(
                    {"evaluation": "Un résultat rattaché à une offre ne peut pas changer d'évaluation."}
                )
        offering_grade_result(self.evaluation, self.valeur, self.resultat, self.statut)
        return super().save(*args, **kwargs)
