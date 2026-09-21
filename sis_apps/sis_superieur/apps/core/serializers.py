"""Core serializers et mixins pour SIS Supérieur."""

from apps.core.models import WorkflowEvent, WorkflowNotification
from rest_framework import serializers

from sis_common.notification_channels import delivery_channels, delivery_last_errors, delivery_status_summary


class TimestampMixin(serializers.Serializer):
    """Mixin pour les champs timestamp."""

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class AuditMixin(serializers.Serializer):
    """Mixin pour les champs d'audit."""

    created_by = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )
    modified_by = serializers.CharField(
        source="modified_by.get_full_name", read_only=True
    )


class PaginatedResponseSerializer(serializers.Serializer):
    """Serializer pour les réponses paginées."""

    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = serializers.ListField()


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer pour les réponses d'erreur."""

    error = serializers.CharField()
    detail = serializers.CharField(required=False)
    code = serializers.CharField(required=False)


class SuccessResponseSerializer(serializers.Serializer):
    """Serializer pour les réponses de succès."""

    detail = serializers.CharField()
    id = serializers.IntegerField(required=False)


class WorkflowEventSerializer(serializers.ModelSerializer):
    """Serializer des événements de workflow."""

    actor_nom = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowEvent
        fields = [
            "id",
            "app_label",
            "model",
            "object_id",
            "object_repr",
            "action",
            "title",
            "message",
            "metadata",
            "tenant_id",
            "request_id",
            "actor_nom",
            "created_at",
        ]

    def get_actor_nom(self, obj):
        return obj.actor.get_full_name() if obj.actor else ""


class WorkflowNotificationSerializer(serializers.ModelSerializer):
    """Serializer des notifications de workflow."""

    event = WorkflowEventSerializer(read_only=True)
    delivery_channels = serializers.SerializerMethodField()
    delivery_status_summary = serializers.SerializerMethodField()
    delivery_last_errors = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowNotification
        fields = [
            "id",
            "category",
            "title",
            "message",
            "metadata",
            "delivery_channels",
            "delivery_status_summary",
            "delivery_last_errors",
            "is_read",
            "read_at",
            "created_at",
            "event",
        ]

    def get_delivery_channels(self, obj):
        return delivery_channels(obj.metadata)

    def get_delivery_status_summary(self, obj):
        return delivery_status_summary(obj.metadata)

    def get_delivery_last_errors(self, obj):
        return delivery_last_errors(obj.metadata)
