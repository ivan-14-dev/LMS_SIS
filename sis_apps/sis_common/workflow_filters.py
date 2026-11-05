"""Validated filters shared by audit lists, summaries and exports."""

from rest_framework import serializers

PRIVATE_WORKFLOW_MODELS = [
    "reclamation",
    "accessdelegation",
    "signatureapproval",
    "signaturemandate",
    "documentarchive",
    "archiverevocation",
]

EVENT_FILTERS = {
    "action": "action",
    "app_label": "app_label",
    "model": "model",
    "actor": "actor_id",
    "date_debut": "created_at__date__gte",
    "date_fin": "created_at__date__lte",
}


class EventFiltersSerializer(serializers.Serializer):
    action = serializers.CharField(required=False)
    app_label = serializers.CharField(required=False)
    model = serializers.CharField(required=False)
    actor = serializers.IntegerField(min_value=1, required=False)
    date_debut = serializers.DateField(required=False)
    date_fin = serializers.DateField(required=False)

    def validate(self, attrs):
        if attrs.get("date_debut") and attrs.get("date_fin") and attrs["date_debut"] > attrs["date_fin"]:
            raise serializers.ValidationError({"date_fin": "La fin doit suivre le début."})
        return attrs


def validated_event_filters(values):
    if not isinstance(values, dict):
        raise serializers.ValidationError({"filters": "Un objet de filtres est attendu."})
    cleaned = {key: value for key, value in values.items() if value != ""}
    serializer = EventFiltersSerializer(data=cleaned)
    serializer.is_valid(raise_exception=True)
    return {**cleaned, **serializer.validated_data}


def filter_events(queryset, values):
    values = validated_event_filters(values)
    return queryset.filter(**{field: values[name] for name, field in EVENT_FILTERS.items() if name in values})
