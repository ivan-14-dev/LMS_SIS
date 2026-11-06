"""Tenant-bound complaint workflow; staff status alone never grants access."""

import logging

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, prefetch_related_objects
from django.http import FileResponse
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from sis_common.authorization import has_business_permission
from sis_common.exam_files import validate_exam_copy
from sis_common.module_registry import require_module
from sis_common.workflow_tracking import record_workflow_event

Reclamation = apps.get_model("core", "Reclamation")
ReclamationEntry = apps.get_model("core", "ReclamationEntry")
ReclamationPiece = apps.get_model("core", "ReclamationPiece")
ASSIGN = "core.affecter_reclamation"
PROCESS = "core.traiter_reclamation"
LEARNER_ROLES = ("eleve", "etudiant", "doctorant")
logger = logging.getLogger("apps.reclamations")


def user_label(user):
    return (user.get_full_name() or user.username) if user else ""


def allowed(user, permission, tenant):
    return (
        user.is_active
        and user.etablissement_id == tenant.pk
        and has_business_permission(user, permission, context={"etablissement_id": tenant.pk})
    )


def eligible_agents(tenant, permission):
    codename = permission.split(".")[1]
    candidates = (
        get_user_model()
        .objects.filter(is_active=True, etablissement_id=tenant.pk)
        .filter(
            Q(is_superuser=True)
            | Q(user_permissions__content_type__app_label="core", user_permissions__codename=codename)
            | Q(groups__permissions__content_type__app_label="core", groups__permissions__codename=codename)
        )
        .distinct()
    )
    return [user for user in candidates.order_by("last_name", "first_name", "pk") if allowed(user, permission, tenant)]


class ComplaintAccess(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if tenant:
            require_module(tenant, "sis.complaints")
        return bool(
            tenant
            and request.user.is_active
            and request.user.etablissement_id == tenant.pk
            and (
                request.user.role in LEARNER_ROLES
                or allowed(request.user, ASSIGN, tenant)
                or allowed(request.user, PROCESS, tenant)
            )
        )


class EntrySerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()

    def get_auteur_nom(self, obj):
        return user_label(obj.auteur)

    class Meta:
        model = ReclamationEntry
        fields = ["id", "auteur_nom", "action", "message", "statut", "created_at"]


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReclamationPiece
        fields = ["id", "nom", "taille", "created_at"]


class ComplaintSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    demandeur_nom = serializers.SerializerMethodField()
    responsable_nom = serializers.SerializerMethodField()
    historique = EntrySerializer(many=True, read_only=True)
    pieces = AttachmentSerializer(many=True, read_only=True)
    actions = serializers.SerializerMethodField()

    class Meta:
        model = Reclamation
        fields = [
            "id",
            "reference",
            "categorie",
            "objet",
            "description",
            "reference_dossier",
            "statut",
            "decision",
            "demandeur_nom",
            "responsable",
            "responsable_nom",
            "version",
            "created_at",
            "updated_at",
            "historique",
            "pieces",
            "actions",
        ]
        read_only_fields = fields

    def get_demandeur_nom(self, obj):
        return user_label(obj.demandeur)

    def get_responsable_nom(self, obj):
        return user_label(obj.responsable)

    def get_actions(self, obj):
        request = self.context["request"]
        owner = obj.demandeur_id == request.user.pk
        coordinator = allowed(request.user, ASSIGN, request.tenant) and not owner
        handler = obj.responsable_id == request.user.pk and allowed(request.user, PROCESS, request.tenant) and not owner
        return {
            "affecter": coordinator and obj.statut in ("soumise", "en_cours", "complement"),
            "traiter": handler and obj.statut in ("en_cours", "complement"),
            "cloturer": (owner or handler) and obj.statut == "resolue",
            "recours": owner and obj.statut in ("resolue", "cloturee"),
            "echanger": (owner or handler or coordinator) and obj.statut not in ("resolue", "cloturee"),
        }


class CreateSerializer(serializers.Serializer):
    categorie = serializers.ChoiceField(choices=Reclamation.CATEGORIES)
    objet = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=10000)
    reference_dossier = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class VersionSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)


class MessageSerializer(VersionSerializer):
    message = serializers.CharField(max_length=10000)


class AssignmentSerializer(VersionSerializer):
    responsable = serializers.IntegerField(min_value=1)


class TransitionSerializer(MessageSerializer):
    statut = serializers.ChoiceField(choices=["complement", "resolue", "cloturee", "recours"])


class FileSerializer(VersionSerializer):
    fichier = serializers.FileField(validators=[validate_exam_copy])


class StaleComplaint(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ce dossier a été modifié. Rechargez-le avant de réessayer."


class ComplaintViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [ComplaintAccess]
    serializer_class = ComplaintSerializer

    def get_queryset(self):
        request = self.request
        queryset = Reclamation.objects.filter(etablissement_id=request.tenant.pk)
        if not allowed(request.user, ASSIGN, request.tenant):
            access = Q(demandeur=request.user)
            if allowed(request.user, PROCESS, request.tenant):
                access |= Q(responsable=request.user)
            queryset = queryset.filter(access)
        return queryset.select_related("demandeur", "responsable").prefetch_related("historique__auteur", "pieces")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        selected = request.query_params.get("statut")
        if selected:
            if selected not in dict(Reclamation.STATUSES):
                raise ValidationError({"statut": "Statut inconnu."})
            queryset = queryset.filter(statut=selected)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    def checked(self, serializer_class):
        serializer = serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        obj = get_object_or_404(
            self.get_queryset().prefetch_related(None).select_for_update(of=("self",)), pk=self.kwargs["pk"]
        )
        if obj.version != serializer.validated_data["version"]:
            raise StaleComplaint()
        return obj, serializer.validated_data

    def event(self, obj, action_name, message, extra_recipients=()):
        ReclamationEntry.objects.create(
            reclamation=obj, auteur=self.request.user, action=action_name, message=message, statut=obj.statut
        )
        recipients = {obj.demandeur_id: obj.demandeur}
        if obj.responsable and allowed(obj.responsable, PROCESS, self.request.tenant):
            recipients[obj.responsable_id] = obj.responsable
        else:
            for user in eligible_agents(self.request.tenant, ASSIGN):
                recipients[user.pk] = user
        for user in extra_recipients:
            recipients[user.pk] = user
        # Sensitive exchanges stay in the object-scoped history, never in generic notifications.
        record_workflow_event(
            self.request,
            obj,
            f"reclamation_{action_name}",
            "Suivi de réclamation",
            message=f"{obj.reference} : consultez votre espace Réclamations.",
            recipients=list(recipients.values()),
            notification_category="reclamation",
        )

    def updated(self, obj, action_name, message, extra_recipients=()):
        obj.version += 1
        obj.save()
        self.event(obj, action_name, message, extra_recipients)
        obj._prefetched_objects_cache = {}
        prefetch_related_objects([obj], "historique__auteur", "pieces")
        return Response(self.get_serializer(obj).data)

    @action(detail=False, methods=["get"])
    def capacites(self, request):
        coordinator = allowed(request.user, ASSIGN, request.tenant)
        return Response(
            {
                "deposer": request.user.role in LEARNER_ROLES,
                "affecter": coordinator,
                "agents": (
                    [{"id": user.pk, "nom": user_label(user)} for user in eligible_agents(request.tenant, PROCESS)]
                    if coordinator
                    else []
                ),
            }
        )

    @transaction.atomic
    def create(self, request):
        if request.user.role not in LEARNER_ROLES:
            raise PermissionDenied("Seul un apprenant peut déposer une réclamation personnelle.")
        data = CreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        obj = Reclamation.objects.create(etablissement=request.tenant, demandeur=request.user, **data.validated_data)
        self.event(obj, "depot", "Demande reçue.")
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def affecter(self, request, pk=None):
        obj, data = self.checked(AssignmentSerializer)
        if not self.get_serializer(obj).get_actions(obj)["affecter"]:
            raise PermissionDenied("Vous ne pouvez pas affecter ce dossier.")
        user = next(
            (
                user
                for user in eligible_agents(request.tenant, PROCESS)
                if user.pk == data["responsable"] and user.pk != obj.demandeur_id
            ),
            None,
        )
        if user is None:
            raise ValidationError({"responsable": "Choisissez un agent habilité, différent du demandeur."})
        previous = obj.responsable
        obj.responsable = user
        if obj.statut == "soumise":
            obj.statut = "en_cours"
        return self.updated(
            obj,
            "affectation",
            f"Dossier confié à {user_label(user)}.",
            [previous] if previous and allowed(previous, PROCESS, request.tenant) else [],
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def message(self, request, pk=None):
        obj, data = self.checked(MessageSerializer)
        if not self.get_serializer(obj).get_actions(obj)["echanger"]:
            raise PermissionDenied("Les échanges sont fermés pour ce dossier.")
        if obj.demandeur_id == request.user.pk and obj.statut == "complement":
            obj.statut = "en_cours"
        return self.updated(obj, "message", data["message"])

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def transition(self, request, pk=None):
        obj, data = self.checked(TransitionSerializer)
        target = data["statut"]
        actions = self.get_serializer(obj).get_actions(obj)
        permitted = actions["traiter"]
        if target == "recours":
            permitted = actions["recours"]
        elif target == "cloturee":
            permitted = actions["cloturer"]
        if not permitted:
            raise PermissionDenied("Cette transition n'est pas autorisée.")
        if target == "complement" and obj.statut == "complement":
            raise ValidationError({"statut": "Un complément est déjà attendu."})
        obj.statut = "en_cours" if target == "recours" and obj.responsable_id else target
        if target == "recours" and not obj.responsable_id:
            obj.statut = "soumise"
        if target == "resolue":
            obj.decision = data["message"]
        recipients = eligible_agents(request.tenant, ASSIGN) if target == "recours" else []
        return self.updated(obj, target, data["message"], recipients)

    @action(detail=True, methods=["post"])
    def pieces(self, request, pk=None):
        piece = None
        committed = False
        try:
            with transaction.atomic():
                obj, data = self.checked(FileSerializer)
                if not self.get_serializer(obj).get_actions(obj)["echanger"]:
                    raise PermissionDenied("L'ajout de pièces est fermé pour ce dossier.")
                if obj.pieces.count() >= 10:
                    raise ValidationError({"fichier": "Dix justificatifs maximum par dossier."})
                upload = data["fichier"]
                piece = ReclamationPiece(
                    reclamation=obj, auteur=request.user, fichier=upload, nom=upload.name, taille=upload.size
                )
                piece.save()
                result = self.updated(obj, "piece", f"Justificatif ajouté : {piece.nom}.")
            committed = True
            return result
        finally:
            if piece is not None and piece.fichier._committed and not committed:
                piece.fichier.storage.delete(piece.fichier.name)

    @action(detail=True, methods=["get"], url_path=r"pieces/(?P<piece_id>[0-9]+)/telecharger")
    def telecharger(self, request, pk=None, piece_id=None):
        obj = self.get_object()
        piece = get_object_or_404(obj.pieces, pk=piece_id)
        try:
            stream = piece.fichier.open("rb")
        except FileNotFoundError:
            logger.error("Missing complaint attachment", extra={"complaint_id": str(obj.pk), "attachment_id": piece.pk})
            raise NotFound("Le justificatif est indisponible. Contactez le service chargé du dossier.")
        result = FileResponse(stream, as_attachment=True, filename=piece.nom, content_type="application/pdf")
        result["Cache-Control"] = "private, no-store"
        result["X-Content-Type-Options"] = "nosniff"
        return result
