"""Private, tenant-bound incoming/outgoing correspondence register."""

import uuid

from django.apps import apps
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from sis_common.authorization import has_business_permission
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset


class CorrespondanceBase(models.Model):
    DIRECTIONS = [("entrante", "Entrante"), ("sortante", "Sortante")]
    STATUSES = [
        ("enregistree", "Enregistrée"),
        ("affectee", "Affectée"),
        ("approuvee", "Approuvée"),
        ("archivee", "Archivée"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    direction = models.CharField(max_length=10, choices=DIRECTIONS)
    expediteur = models.CharField(max_length=200)
    destinataire = models.CharField(max_length=200)
    objet = models.CharField(max_length=200)
    contenu = models.TextField()
    reference_externe = models.CharField(max_length=100, blank=True)
    statut = models.CharField(max_length=20, choices=STATUSES, default="enregistree")
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="correspondances_creees"
    )
    assigne_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correspondances_assignees",
    )
    assigne_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approuve_le = models.DateTimeField(null=True, blank=True)
    archive_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    archive_le = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at", "id"]
        permissions = [
            ("assign_correspondance", "Affecter les correspondances de l'établissement"),
            ("approve_correspondance", "Approuver les correspondances affectées"),
            ("archive_correspondance", "Archiver les correspondances approuvées"),
        ]

    def __str__(self):
        return f"COR-{self.pk.hex.upper()}"


def allowed(user, permission, tenant):
    return bool(
        tenant
        and user.is_authenticated
        and user.is_active
        and user.etablissement_id == tenant.pk
        and user.role not in ("eleve", "etudiant", "doctorant", "parent")
        and has_business_permission(user, permission, context={"etablissement_id": tenant.pk})
    )


class CorrespondanceAccess(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and allowed(
            request.user, "core.view_correspondance", getattr(request, "tenant", None)
        )


class StaleCorrespondance(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Cette correspondance a été modifiée. Rechargez-la avant de réessayer."


class CorrespondanceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """No generic update/delete: every transition is checked and audited."""

    permission_classes = [CorrespondanceAccess]

    def get_serializer_class(self):
        correspondence_model = apps.get_model("core", "Correspondance")

        class CorrespondanceSerializer(serializers.ModelSerializer):
            class Meta:
                model = correspondence_model
                fields = [
                    "id", "direction", "expediteur", "destinataire", "objet", "contenu", "reference_externe",
                    "statut", "cree_par", "assigne_a", "assigne_par", "approuve_par", "approuve_le",
                    "archive_par", "archive_le", "version", "created_at", "updated_at",
                ]
                read_only_fields = fields

        return CorrespondanceSerializer

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    def get_queryset(self):
        return apps.get_model("core", "Correspondance").objects.filter(
            etablissement_id=self.request.tenant.pk
        ).select_related("cree_par", "assigne_a", "assigne_par", "approuve_par", "archive_par")

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        record_workflow_event(request, instance, "correspondance_consultee", "Correspondance consultée")
        return Response(self.get_serializer(instance).data)

    def _require(self, permission):
        if not allowed(self.request.user, permission, self.request.tenant):
            raise PermissionDenied("Habilitation de correspondance requise.")

    def _checked(self, data):
        obj = get_object_or_404(
            self.get_queryset().select_related(None).select_for_update(of=("self",)), pk=self.kwargs["pk"]
        )
        if obj.version != data["version"]:
            raise StaleCorrespondance()
        return obj

    def _record(self, obj, action_name):
        record_workflow_event(
            self.request, obj, f"correspondance_{action_name}", f"Correspondance {action_name}",
            metadata={"direction": obj.direction, "statut": obj.statut, "version": obj.version},
        )

    def _result(self, obj):
        return Response(self.get_serializer(obj).data)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        direction = request.query_params.get("direction")
        statut = request.query_params.get("statut")
        if direction:
            if direction not in dict(apps.get_model("core", "Correspondance").DIRECTIONS):
                raise ValidationError({"direction": "Direction inconnue."})
            queryset = queryset.filter(direction=direction)
        if statut:
            if statut not in dict(apps.get_model("core", "Correspondance").STATUSES):
                raise ValidationError({"statut": "Statut inconnu."})
            queryset = queryset.filter(statut=statut)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(queryset, many=True).data)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        self._require("core.add_correspondance")

        class Creation(serializers.Serializer):
            direction = serializers.ChoiceField(choices=CorrespondanceBase.DIRECTIONS)
            expediteur = serializers.CharField(max_length=200)
            destinataire = serializers.CharField(max_length=200)
            objet = serializers.CharField(max_length=200)
            contenu = serializers.CharField(max_length=10000)
            reference_externe = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")

        payload = Creation(data=request.data)
        payload.is_valid(raise_exception=True)
        obj = apps.get_model("core", "Correspondance").objects.create(
            **payload.validated_data, cree_par=request.user, etablissement=request.tenant
        )
        self._record(obj, "enregistree")
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def affecter(self, request, pk=None):
        self._require("core.assign_correspondance")

        class Assignment(serializers.Serializer):
            version = serializers.IntegerField(min_value=1)
            assigne_a = serializers.IntegerField(min_value=1)

        payload = Assignment(data=request.data)
        payload.is_valid(raise_exception=True)
        obj = self._checked(payload.validated_data)
        if obj.statut not in ("enregistree", "affectee"):
            raise ValidationError({"statut": "Une correspondance approuvée ne peut plus être affectée."})
        assignee = get_object_or_404(
            apps.get_model(settings.AUTH_USER_MODEL).objects.filter(
                pk=payload.validated_data["assigne_a"], etablissement_id=request.tenant.pk
            )
        )
        if not allowed(assignee, "core.view_correspondance", request.tenant) or not allowed(
            assignee, "core.approve_correspondance", request.tenant
        ) or assignee.pk in (obj.cree_par_id, request.user.pk):
            raise ValidationError({
                "assigne_a": "Un autre agent habilité, distinct du créateur et de l'affectant, est requis."
            })
        obj.assigne_a = assignee
        obj.assigne_par = request.user
        obj.statut = "affectee"
        obj.version += 1
        obj.save(update_fields=["assigne_a", "assigne_par", "statut", "version", "updated_at"])
        self._record(obj, "affectee")
        return self._result(obj)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approuver(self, request, pk=None):
        self._require("core.approve_correspondance")
        payload = serializers.Serializer(data=request.data)
        payload.fields["version"] = serializers.IntegerField(min_value=1)
        payload.is_valid(raise_exception=True)
        obj = self._checked(payload.validated_data)
        if obj.statut != "affectee":
            raise ValidationError({"statut": "Une correspondance affectée et non approuvée est requise."})
        if obj.assigne_a_id != request.user.pk or request.user.pk in (obj.cree_par_id, obj.assigne_par_id):
            raise PermissionDenied(
                "L'approbation est réservée à l'agent affecté, distinct du créateur et de l'affectant."
            )
        obj.approuve_par = request.user
        obj.approuve_le = timezone.now()
        obj.statut = "approuvee"
        obj.version += 1
        obj.save(update_fields=["approuve_par", "approuve_le", "statut", "version", "updated_at"])
        self._record(obj, "approuvee")
        return self._result(obj)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def archiver(self, request, pk=None):
        self._require("core.archive_correspondance")
        payload = serializers.Serializer(data=request.data)
        payload.fields["version"] = serializers.IntegerField(min_value=1)
        payload.is_valid(raise_exception=True)
        obj = self._checked(payload.validated_data)
        if obj.statut != "approuvee":
            raise ValidationError({"statut": "Seule une correspondance approuvée peut être archivée."})
        if obj.approuve_par_id == request.user.pk:
            raise PermissionDenied("L'archivage est réservé à un autre agent habilité.")
        obj.archive_par = request.user
        obj.archive_le = timezone.now()
        obj.statut = "archivee"
        obj.version += 1
        obj.save(update_fields=["archive_par", "archive_le", "statut", "version", "updated_at"])
        self._record(obj, "archivee")
        return self._result(obj)

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        obj = self.get_object()
        return Response(list(workflow_history_queryset(obj).filter(tenant_id=request.tenant.pk).values(
            "action", "actor_id", "created_at", "metadata"
        )))
