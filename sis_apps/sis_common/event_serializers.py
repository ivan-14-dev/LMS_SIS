"""Bounded commands shared by the two institutional agendas."""

from datetime import UTC, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from sis_common.event_models import InstitutionalEventBase


class StrictCommand(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError({"detail": "Champs inconnus interdits."})
        return super().to_internal_value(data)


class AwareDateTime(serializers.DateTimeField):
    def to_internal_value(self, value):
        try:
            parsed = parse_datetime(value) if isinstance(value, str) else value
        except ValueError:
            parsed = None
        if parsed is None or not hasattr(parsed, "utcoffset") or timezone.is_naive(parsed):
            raise serializers.ValidationError("Indiquez une date ISO 8601 avec fuseau explicite.")
        return super().to_internal_value(value)


class IntervalCommand(StrictCommand):
    debut = AwareDateTime()
    fin = AwareDateTime()
    max_days = 7

    def validate(self, attrs):
        start, end = attrs["debut"].astimezone(UTC), attrs["fin"].astimezone(UTC)
        if not start < end <= start + timedelta(days=self.max_days):
            raise serializers.ValidationError({"fin": f"Intervalle positif limité à {self.max_days} jours."})
        return attrs


class CalendarQuery(IntervalCommand):
    max_days = 93
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)


class EventCommand(IntervalCommand):
    titre = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=5000, allow_blank=True, default="")
    type = serializers.ChoiceField(choices=InstitutionalEventBase.TYPES)
    salle = serializers.IntegerField(min_value=1)
    effectif = serializers.IntegerField(min_value=1)
    participants = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=200)

    def validate_participants(self, values):
        if len(set(values)) != len(values):
            raise serializers.ValidationError("Les participants doivent être distincts.")
        return values

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if len(attrs["participants"]) > attrs["effectif"]:
            raise serializers.ValidationError({"effectif": "L'effectif doit inclure tous les participants invités."})
        return attrs


class UpdateEventCommand(EventCommand):
    version = serializers.IntegerField(min_value=1)


class VersionCommand(StrictCommand):
    version = serializers.IntegerField(min_value=1)
