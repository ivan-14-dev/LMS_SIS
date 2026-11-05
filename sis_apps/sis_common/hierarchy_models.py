"""Immutable configuration publications and tenant-local organizational scopes."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class OrganizationUnitBase(models.Model):
    KINDS = [
        ("campus", "Campus"), ("department", "Département"), ("program", "Programme de formation"),
        ("university", "Université"), ("company", "Entreprise"), ("faculty", "Faculté"),
        ("school", "École"), ("track", "Filière / parcours"), ("level", "Niveau"),
        ("class", "Classe"), ("group", "Groupe"), ("teaching_unit", "Unité d’enseignement"),
        ("directorate", "Direction"), ("service", "Service"), ("team", "Équipe"), ("custom", "Autre catégorie"),
    ]
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    code = models.SlugField(max_length=64)
    nom = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=KINDS)
    category_label = models.CharField(max_length=100, blank=True)
    topology_version = models.PositiveSmallIntegerField(
        default=1, choices=[(1, "Périmètres historiques"), (2, "Organisation libre")]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["nom", "id"]

    def __str__(self):
        return f"{self.code} - {self.nom}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            for field in ("code", "kind", "parent_id", "topology_version", "etablissement_id"):
                if getattr(previous, field) != getattr(self, field):
                    raise ValidationError({field: "Le rattachement et le code sont figés pour conserver l'historique."})
        ranks = {"campus": 0, "department": 1, "program": 2}
        if self.topology_version == 1 and self.kind not in ranks:
            raise ValidationError({"kind": "Cette catégorie exige le mode organisation libre."})
        if self.kind == "custom" and not self.category_label.strip():
            raise ValidationError({"category_label": "Précisez le nom de cette catégorie."})
        parent, seen = self.parent, {self.pk} if self.pk else set()
        while parent:
            if parent.etablissement_id != self.etablissement_id or parent.pk in seen:
                raise ValidationError({"parent": "Parent étranger ou cycle interdit."})
            seen.add(parent.pk)
            if self.topology_version == 1 and (
                parent.topology_version != 1 or ranks.get(parent.kind, 3) >= ranks[self.kind]
            ):
                raise ValidationError({"parent": "Un parent historique doit être situé plus haut dans la hiérarchie."})
            parent = parent.parent


def attachment_constraint(fields):
    condition = models.Q()
    for field in fields:
        condition |= models.Q(**{f"{name}__isnull": name != field for name in fields})
    return models.CheckConstraint(condition=condition, name="organization_attachment_one_target")


class OrganizationAttachmentBase(models.Model):
    """Closed foreign keys only; never an authorization or a generic content-type relation."""

    unit = models.ForeignKey("core.OrganizationUnit", on_delete=models.PROTECT, related_name="attachments")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    book = models.OneToOneField("bibliotheque.Livre", null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", editable=False
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        from sis_common.hierarchy_attachments import validate_attachment_model

        validate_attachment_model(self)


class ConfigurationRevisionBase(models.Model):
    unit = models.ForeignKey("core.OrganizationUnit", null=True, blank=True, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    values = models.JSONField(default=dict)
    locks = models.JSONField(default=list)
    effective_from = models.DateTimeField()
    reason = models.TextField()
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-effective_from", "-revision"]

    def __str__(self):
        return f"Configuration #{self.revision}"
