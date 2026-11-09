"""Protect only legacy structures that already have a practical dossier."""

from contextlib import contextmanager
from contextvars import ContextVar

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.deletion import ProtectedError
from django.db.models.signals import pre_delete
from rest_framework.response import Response

COMMON = {
    "date_debut", "date_fin", "entreprise_id", "missions", "horaires", "statut", "date_signature_complete",
}
SECONDARY = {
    "eleve_id", "maitre_stage_etablissement_id", "duree_heures",
    "tuteur_entreprise", "telephone_tuteur", "email_tuteur",
}
UPPER = {"etudiant_id", "offre_id", "maitre_stage_id", "tuteur_pedagogique_id"}
_checked_bulk_update = ContextVar("practical_checked_legacy_bulk_update", default=False)


def protected_error():
    return ValidationError("Structure liée à un dossier pratique protégé.", code="structure_protegee")


def structural_fields(model):
    if model._meta.model_name == "offrestage":
        return {"formation_id", "entreprise_id"}
    return COMMON | (SECONDARY if settings.SIS_VARIANT == "secondaire" else UPPER)


@contextmanager
def locked_legacy(queryset):
    with transaction.atomic():
        convention_model = apps.get_model("stages", "ConventionStage")
        conventions = (
            convention_model.objects.filter(offre_id__in=queryset.values("pk"))
            if queryset.model._meta.model_name == "offrestage" else queryset
        )
        field = "eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant"
        learner_model = convention_model._meta.get_field(field).remote_field.model
        ids = list(conventions.order_by().values_list(f"{field}_id", flat=True))
        list(learner_model.objects.filter(pk__in=ids).order_by("pk").select_for_update())
        list(conventions.order_by("pk").select_for_update())
        yield list(queryset.order_by("pk").select_for_update())


def is_linked(instance):
    dossiers = apps.get_model("stages", "DossierPratique").objects
    if instance._meta.model_name == "offrestage":
        return dossiers.filter(convention__offre_id=instance.pk).exists()
    return dossiers.filter(convention_id=instance.pk).exists()


class ProtectedLegacyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if _checked_bulk_update.get():
            return super().update(**kwargs)
        names = {self.model._meta.get_field(name).attname: value for name, value in kwargs.items()}
        relevant = structural_fields(self.model) & names.keys()
        if not relevant:
            return super().update(**kwargs)
        with locked_legacy(self) as rows:
            for row in rows:
                if is_linked(row) and any(getattr(row, name) != names[name] for name in relevant):
                    raise protected_error()
            return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        names = {self.model._meta.get_field(name).attname for name in fields}
        relevant = structural_fields(self.model) & names
        if not relevant:
            return super().bulk_update(objs, fields, batch_size=batch_size)
        objs = tuple(objs)
        with locked_legacy(self.filter(pk__in=[obj.pk for obj in objs])) as rows:
            protected = {row.pk: row for row in rows if is_linked(row)}
            for obj in objs:
                previous = protected.get(obj.pk)
                if previous and any(getattr(obj, name) != getattr(previous, name) for name in relevant):
                    raise protected_error()
            # Django emits CASE expressions; compare real values before entering its bulk path.
            token = _checked_bulk_update.set(True)
            try:
                return super().bulk_update(objs, fields, batch_size=batch_size)
            finally:
                _checked_bulk_update.reset(token)

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False,
                    update_fields=None, unique_fields=None):
        options = {
            "batch_size": batch_size, "ignore_conflicts": ignore_conflicts,
            "update_conflicts": update_conflicts, "update_fields": update_fields, "unique_fields": unique_fields,
        }
        names = {self.model._meta.get_field(name).attname for name in (update_fields or [])}
        relevant = structural_fields(self.model) & names
        if not update_conflicts or not relevant or not unique_fields:
            return super().bulk_create(objs, **options)
        objs = tuple(objs)
        keys = [
            self.model._meta.pk.attname if name == "pk" else self.model._meta.get_field(name).attname
            for name in unique_fields
        ]
        candidates = {}
        selection = models.Q(pk__in=[])
        for obj in objs:
            values = tuple(getattr(obj, name) for name in keys)
            if all(value is not None for value in values):
                candidates.setdefault(values, []).append(obj)
                selection |= models.Q(**dict(zip(keys, values, strict=True)))
        # Upserts ignore QuerySet filters, so inspect conflicts on the whole model.
        queryset = self.model._default_manager.using(self.db).filter(selection)
        with locked_legacy(queryset) as rows:
            for row in rows:
                if is_linked(row):
                    for obj in candidates[tuple(getattr(row, name) for name in keys)]:
                        if any(getattr(obj, name) != getattr(row, name) for name in relevant):
                            raise protected_error()
            return super().bulk_create(objs, **options)

    def delete(self):
        with locked_legacy(self) as rows:
            if any(is_linked(row) for row in rows):
                raise protected_error()
            return super().delete()


class ProtectedLegacyBase(models.Model):
    objects = ProtectedLegacyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self._state.adding:
            return super().save(*args, **kwargs)
        with locked_legacy(type(self).objects.filter(pk=self.pk)) as rows:
            if rows and is_linked(rows[0]):
                requested = kwargs.get("update_fields")
                fields = structural_fields(type(self))
                if requested is not None:
                    fields &= {self._meta.get_field(name).attname for name in requested}
                if any(getattr(self, name) != getattr(rows[0], name) for name in fields):
                    raise protected_error()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with locked_legacy(type(self).objects.filter(pk=self.pk)) as rows:
            if rows and is_linked(rows[0]):
                raise protected_error()
            return super().delete(*args, **kwargs)


class PracticalLegacyAPIMixin:
    def handle_exception(self, exc):
        if (
            isinstance(exc, ValidationError) and getattr(exc, "code", None) == "structure_protegee"
        ) or (
            isinstance(exc, ProtectedError)
            and any(obj._meta.app_label == "stages" and "pratique" in obj._meta.model_name
                    for obj in exc.protected_objects)
        ):
            return Response({
                "detail": "Structure liée à un dossier pratique protégé.", "code": "structure_protegee",
                "errors": {}, "current_version": None, "criteres_non_satisfaits": [],
            }, status=409)
        return super().handle_exception(exc)


def reject_practical_delete(sender, instance, **kwargs):
    raise protected_error()


def reject_linked_delete(sender, instance, **kwargs):
    if is_linked(instance):
        raise protected_error()


def connect_practical_guards():
    for name in (
        "ProgrammePratique", "RevisionProgrammePratique", "DossierPratique", "HeurePratique",
        "DecisionHeurePratique", "EvaluationCompetencePratique", "AuditPratique",
    ):
        model = apps.get_model("stages", name)
        pre_delete.connect(reject_practical_delete, sender=model, dispatch_uid=f"pratique.delete.{name}")
    for name in (("ConventionStage", "OffreStage") if settings.SIS_VARIANT == "superieur" else ("ConventionStage",)):
        pre_delete.connect(
            reject_linked_delete, sender=apps.get_model("stages", name), dispatch_uid=f"pratique.legacy.{name}",
        )
