"""Core serializers et mixins pour SIS Supérieur."""
from rest_framework import serializers


class TimestampMixin(serializers.Serializer):
    """Mixin pour les champs timestamp."""
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class AuditMixin(serializers.Serializer):
    """Mixin pour les champs d'audit."""
    created_by = serializers.CharField(source='created_by.get_full_name', read_only=True)
    modified_by = serializers.CharField(source='modified_by.get_full_name', read_only=True)


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
