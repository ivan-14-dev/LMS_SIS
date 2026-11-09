"""Publish only the explicit Studio revision reviewed by an administrator."""

import logging

import requests
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response

from .lms_diagnostics import unavailable_response

logger = logging.getLogger(__name__)


class PublicationRequestSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField()
    expected_revision = serializers.RegexField(r"^[a-f0-9]{24}$")
    confirm = serializers.BooleanField()

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != set(self.fields) or data.get("confirm") is not True:
            raise serializers.ValidationError(
                {"non_field_errors": ["Confirmez explicitement la révision exacte examinée dans Studio."]}
            )
        return super().to_internal_value(data)


def course_publication(request, mapping_id):
    from apps.integration.edx_client import get_edx_client
    from apps.integration.models import EdxCourseMapping

    values = None
    if request.method == "POST":
        serializer = PublicationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
    with transaction.atomic():
        mapping = get_object_or_404(EdxCourseMapping.objects.select_for_update(), pk=mapping_id)
        if not mapping.actif:
            logger.warning("Studio publication refused for inactive mapping_id=%s", mapping.pk)
            return Response({"error": "Cette association de cours est désactivée."}, status=status.HTTP_409_CONFLICT)
        try:
            client = get_edx_client()
            result = (
                client.get_course_revision(mapping.course_id)
                if values is None
                else client.publish_course(mapping.course_id, **values)
            )
        except ImproperlyConfigured:
            return unavailable_response()
        except requests.RequestException as error:
            logger.exception("Studio publication not confirmed mapping_id=%s", mapping.pk)
            if error.response is not None and error.response.status_code == 409:
                return Response(
                    {"error": "La révision ou les droits ont changé. Examinez à nouveau le cours dans Studio."},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(
                {"error": "Studio n'a pas confirmé la demande. Aucune publication n'est annoncée comme terminée."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError:
            logger.exception("Invalid Studio publication confirmation mapping_id=%s", mapping.pk)
            return Response(
                {"error": "Studio n'a pas confirmé l'identité et la révision demandées."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
    if values is not None:
        logger.info(
            "Studio publication confirmed actor_id=%s mapping_id=%s operation_id=%s revision=%s",
            request.user.pk,
            mapping.pk,
            values["operation_id"],
            values["expected_revision"],
        )
    return Response(result)
