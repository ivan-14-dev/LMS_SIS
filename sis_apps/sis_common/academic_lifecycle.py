"""Shared API guards for academic archives and their dependent records."""

from django.db import connection, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import PermissionDenied, ValidationError

from sis_common.event_occupancy import EventOccupancyGuard, occupancy_lock


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

    def check_grading_conflict(self, instance=None, data=None):
        if self.request.method in ("GET", "HEAD", "OPTIONS") or self.request.user.is_superuser:
            return
        model = type(instance) if instance is not None else self.get_queryset().model
        if model._meta.label_lower == "notes.evaluation" and instance is not None:
            if self.eligible_lms_learners(instance).filter(user_id=self.request.user.pk).exists():
                raise PermissionDenied("Vous ne pouvez pas gérer une évaluation à laquelle vous êtes inscrit.")
        if model._meta.label_lower == "notes.note":
            for name in ("eleve", "etudiant"):
                learner = (data or {}).get(name, getattr(instance, name, None))
                if learner is not None and learner.user_id == self.request.user.pk:
                    raise PermissionDenied("Vous ne pouvez pas saisir, modifier ou supprimer votre propre note.")

    def lock_event_occupancy(self):
        # These APIs are tenant-bound, including shared academic parents.
        # Lock before the object/parent rows, not only inside model.save().
        if issubclass(self.get_queryset().model, EventOccupancyGuard):
            occupancy_lock()

    def get_object(self):
        writing = connection.in_atomic_block and self.request.method not in ("GET", "HEAD", "OPTIONS")
        if writing:
            self.lock_event_occupancy()
        instance = super().get_object()
        if writing:
            instance = type(instance).objects.select_for_update().get(pk=instance.pk)
        self.check_grading_conflict(instance)
        return instance

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        self.lock_event_occupancy()
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        self.lock_event_occupancy()
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        self.lock_event_occupancy()
        ensure_academic_open(self.get_object(), paths=self.academic_period_paths)
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as error:
            raise ValidationError(
                {"detail": "Ce dossier possède des données conservées. Archivez-le au lieu de le supprimer."}
            ) from error

    def save_academic(self, serializer, **kwargs):
        self.check_grading_conflict(serializer.instance, serializer.validated_data)
        if connection.in_atomic_block:
            self.lock_event_occupancy()
        if "" in self.academic_period_paths:
            for field in ("cloturee", "cloture", "en_cours"):
                if field in serializer.validated_data and serializer.validated_data[field] != getattr(
                    serializer.instance, field, False
                ):
                    raise ValidationError({field: "Utilisez l'action d'activation, de clôture ou de réouverture."})
        ensure_academic_open(serializer.instance, serializer.validated_data, self.academic_period_paths)
        if serializer.instance and "" in self.academic_period_paths:
            periods = getattr(serializer.instance, "periodes", None)
            if periods is None:
                periods = getattr(serializer.instance, "semestres", None)
            if periods is not None:
                start = serializer.validated_data.get("date_debut")
                end = serializer.validated_data.get("date_fin")
                if start and start > serializer.instance.date_debut and periods.filter(date_debut__lt=start).exists():
                    raise ValidationError({"date_debut": "Le début doit précéder les périodes existantes."})
                if end and end < serializer.instance.date_fin and periods.filter(date_fin__gt=end).exists():
                    raise ValidationError({"date_fin": "La fin doit suivre les périodes existantes."})
        return serializer.save(**kwargs)

    def perform_create(self, serializer):
        self.save_academic(serializer)

    def perform_update(self, serializer):
        self.save_academic(serializer)
