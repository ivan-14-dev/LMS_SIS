"""Shared API guards for academic archives and their dependent records."""

from django.db import connection, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError


def ensure_academic_open(instance=None, data=None, paths=()):
    periods = {}
    for path in paths:
        for proposed in (False, True):
            if not path:
                value = instance
            else:
                root, *children = path.split(".")
                value = getattr(instance, root, None)
                if proposed and data is not None:
                    value = data.get(root, value)
                for child in children:
                    if value is not None:
                        value = getattr(value, child)
            if value is not None and value.pk:
                periods[(value._meta.label_lower, value.pk)] = value
    for key in sorted(periods):
        value = periods[key]
        queryset = type(value).objects
        if connection.in_atomic_block:
            if connection.vendor == "postgresql":
                # Shared guards allow parallel writes but still block calendar closure.
                quote = connection.ops.quote_name
                metadata = value._meta
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT {quote(metadata.pk.column)} FROM {quote(metadata.db_table)} "
                        f"WHERE {quote(metadata.pk.column)} = %s FOR SHARE",
                        [value.pk],
                    )
                queryset = queryset.using(connection.alias)
            else:
                queryset = queryset.select_for_update()
        current = queryset.get(pk=value.pk)
        closed_field = "cloturee" if hasattr(current, "cloturee") else "cloture"
        if getattr(current, closed_field):
            raise ValidationError(
                {"calendrier": "Cette opération concerne une année, une période ou une session clôturée."}
            )


class AcademicLifecycleMixin:
    academic_period_paths = ()

    def get_object(self):
        instance = super().get_object()
        if connection.in_atomic_block and self.request.method not in ("GET", "HEAD", "OPTIONS"):
            instance = type(instance).objects.select_for_update().get(pk=instance.pk)
        return instance

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        ensure_academic_open(self.get_object(), paths=self.academic_period_paths)
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as error:
            raise ValidationError(
                {"detail": "Ce dossier possède des données conservées. Archivez-le au lieu de le supprimer."}
            ) from error

    def save_academic(self, serializer, **kwargs):
        if "" in self.academic_period_paths:
            for field in ("cloturee", "cloture", "en_cours"):
                if field in serializer.validated_data and serializer.validated_data[field] != getattr(
                    serializer.instance, field, False
                ):
                    raise ValidationError({field: "Utilisez l'action d'activation, de clôture ou de réouverture."})
        ensure_academic_open(serializer.instance, serializer.validated_data, self.academic_period_paths)
        return serializer.save(**kwargs)

    def perform_create(self, serializer):
        self.save_academic(serializer)

    def perform_update(self, serializer):
        self.save_academic(serializer)
