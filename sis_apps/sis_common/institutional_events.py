"""Private institutional agenda, invitations and atomic room reservations."""

from uuid import UUID

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import CharField, Q
from django.db.models.functions import Cast
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from sis_common.authorization import filter_queryset_by_scopes, has_business_permission, is_current_tenant_user
from sis_common.event_occupancy import occupancy_lock, room_model, validate_event_room
from sis_common.event_serializers import CalendarQuery, EventCommand, UpdateEventCommand, VersionCommand
from sis_common.module_registry import effective_modules, module_configuration, require_module
from sis_common.pagination import SISPagination
from sis_common.workflow_tracking import record_workflow_event

MANAGE = "core.gerer_evenement_institutionnel"
CONSULT = "core.consulter_evenement_institutionnel"
SCOPES = {"etablissement_id": "etablissement_id", "evenement_id": "pk", "salle_id": "salle_id"}


def valid_scopes(user, permission):
    if user.is_superuser:
        return True
    attributes = user.attributs_acces or {}
    if not isinstance(attributes, dict):
        return False
    scopes = attributes.get("permission_scopes", {})
    if not isinstance(scopes, dict):
        return False
    constraints = scopes.get(permission, {})
    if not isinstance(constraints, dict):
        return False
    for key, values in constraints.items():
        if key not in SCOPES or not isinstance(values, list):
            return False
        if key == "evenement_id":
            for value in values:
                try:
                    if not isinstance(value, str) or str(UUID(value)) != value:
                        return False
                except ValueError:
                    return False
        elif any(type(value) is not int or value < 1 for value in values):
            return False
    return True


def event_model():
    return apps.get_model("core", "InstitutionalEvent")


def current_event_user(request):
    if not hasattr(request, "_event_user"):
        request._event_user = None
        if request.user.is_authenticated and is_current_tenant_user(request):
            request._event_user = (
                get_user_model()
                .objects.filter(pk=request.user.pk, etablissement=request.tenant, is_active=True)
                .first()
            )
    return request._event_user


def can_manage(request, event=None):
    user = current_event_user(request)
    context = {"etablissement_id": request.tenant.pk}
    if event is not None:
        context.update(evenement_id=str(event.pk), salle_id=event.salle_id)
    return bool(user and valid_scopes(user, MANAGE) and has_business_permission(user, MANAGE, context=context))


def permitted_events(request, permission):
    queryset = event_model().objects.filter(etablissement_id=request.tenant.pk)
    if room_model()._meta.app_label == "salles":
        queryset = queryset.filter(salle__etablissement_id=request.tenant.pk)
    user = current_event_user(request)
    if not user or not valid_scopes(user, permission) or not user.has_perm(permission):
        return queryset.none()
    try:
        return filter_queryset_by_scopes(queryset, user, permission, SCOPES)
    except (DjangoValidationError, TypeError, ValueError):
        # Malformed attribute values are a denied scope, not an unfiltered query.
        return queryset.none()


def visible_events(request):
    managed = permitted_events(request, MANAGE)
    invited = permitted_events(request, CONSULT).filter(
        invitations__utilisateur=request.user, invitations__revoked_at__isnull=True
    )
    return event_model().objects.filter(Q(pk__in=managed.values("pk")) | Q(pk__in=invited.values("pk")))


def filter_event_notifications(request, queryset):
    private = Q(event__app_label="core", event__model="institutionalevent")
    tenant = getattr(request, "tenant", None)
    if not tenant or not tenant.actif or not current_event_user(request):
        return queryset.exclude(private)
    configuration = module_configuration(tenant)
    if not effective_modules(configuration.enabled if configuration else {})["sis.events"]:
        return queryset.exclude(private)
    identifiers = visible_events(request).annotate(identifier=Cast("pk", CharField())).values("identifier")
    return queryset.filter(~private | Q(event__object_id__in=identifiers, event__tenant_id=tenant.pk))


class EventAccess(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant or not tenant.actif or not current_event_user(request):
            return False
        require_module(tenant, "sis.events")
        return True


class EventConflict(APIException):
    status_code = 409
    default_detail = "L'événement a changé ou est annulé. Rechargez-le avant de réessayer."
    default_code = "event_conflict"


def user_summary(user):
    return {"id": user.pk, "nom": user.get_full_name() or user.username}


def room_summary(room):
    return {"id": room.pk, "code": room.code, "nom": room.nom, "capacite": room.capacite}


class InstitutionalEventViewSet(viewsets.GenericViewSet):
    permission_classes = [EventAccess]
    serializer_class = EventCommand
    pagination_class = SISPagination
    filter_backends = []
    lookup_value_regex = "[0-9a-f-]{36}"

    def get_queryset(self):
        return visible_events(self.request).select_related("salle")

    def checked(self, command, data=None):
        serializer = command(data=self.request.data if data is None else data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def collection(self, queryset, serialize):
        return self.get_paginated_response([serialize(item) for item in self.paginate_queryset(queryset)])

    def summary(self, event):
        return {
            "id": str(event.pk),
            "titre": event.titre,
            "description": event.description,
            "type": event.type,
            "statut": event.statut,
            "debut": event.debut,
            "fin": event.fin,
            "salle": room_summary(event.salle),
            "effectif": event.effectif,
            "version": event.version,
            "can_manage": can_manage(self.request, event),
        }

    def serialize_detail(self, event):
        values = self.summary(event)
        if values["can_manage"]:
            values["participants"] = [
                user_summary(item.utilisateur)
                for item in event.invitations.filter(
                    revoked_at__isnull=True, utilisateur__etablissement=self.request.tenant
                ).select_related("utilisateur")
            ]
        return values

    def list(self, request):
        interval = self.checked(CalendarQuery, request.query_params.dict())
        events = self.get_queryset().filter(debut__lt=interval["fin"], fin__gt=interval["debut"])
        return self.collection(events, self.summary)

    def retrieve(self, request, pk=None):
        return Response(self.serialize_detail(self.get_object()))

    @action(detail=False, methods=["get"])
    def capacites(self, request):
        user = current_event_user(request)
        return Response(
            {
                "can_create": can_manage(request),
                "can_manage": user.has_perm(MANAGE) and permitted_events(request, MANAGE).exists(),
                "can_consult": valid_scopes(user, CONSULT) and user.has_perm(CONSULT),
                "types": [{"value": value, "label": label} for value, label in event_model().TYPES],
                "statuts": [{"value": value, "label": label} for value, label in event_model().STATUSES],
                "notifications": "internes",
            }
        )

    def selector_event(self):
        identifier = self.request.query_params.get("evenement_id")
        if identifier:
            from rest_framework import serializers

            identifier = serializers.UUIDField().run_validation(identifier)
            event = get_object_or_404(self.get_queryset(), pk=identifier)
            if can_manage(self.request, event):
                return event
        elif can_manage(self.request):
            return None
        raise PermissionDenied("Le droit explicite de gérer cet événement est requis.")

    @action(detail=False, methods=["get"])
    def salles(self, request):
        self.selector_event()
        rooms = room_model().objects.order_by("code", "pk")
        if room_model()._meta.app_label == "salles":
            rooms = rooms.filter(etablissement=request.tenant)
        user = current_event_user(request)
        if not user.is_superuser:
            scope = (user.attributs_acces or {}).get("permission_scopes", {}).get(MANAGE, {})
            if "salle_id" in scope:
                rooms = rooms.filter(pk__in=scope["salle_id"])
        return self.collection(rooms, room_summary)

    @action(detail=False, methods=["get"])
    def participants(self, request):
        self.selector_event()
        term = request.query_params.get("q", "").strip()
        if not 2 <= len(term) <= 100:
            raise ValidationError({"q": "Recherchez entre 2 et 100 caractères."})
        users = (
            get_user_model()
            .objects.filter(etablissement=request.tenant, is_active=True)
            .filter(Q(username__icontains=term) | Q(first_name__icontains=term) | Q(last_name__icontains=term))
            .order_by("last_name", "first_name", "pk")
        )
        return self.collection(users, user_summary)

    def apply_command(self, event, values):
        identifiers = values.pop("participants")
        users = list(
            get_user_model()
            .objects.filter(pk__in=identifiers, etablissement=self.request.tenant, is_active=True)
            .order_by("pk")
        )
        if len(users) != len(identifiers):
            raise ValidationError({"participants": "Sélectionnez uniquement des comptes actifs de cet établissement."})
        rooms = room_model().objects.all()
        if room_model()._meta.app_label == "salles":
            rooms = rooms.filter(etablissement=self.request.tenant)
        room = get_object_or_404(rooms, pk=values.pop("salle"))
        event.salle = room
        for field, value in values.items():
            setattr(event, field, value)
        if not can_manage(self.request, event):
            raise PermissionDenied("La salle ou l'événement sort du périmètre autorisé.")
        validate_event_room(event)
        event.save()
        Invitation = apps.get_model("core", "EventInvitation")
        event.invitations.exclude(utilisateur_id__in=identifiers).filter(revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        for user in users:
            Invitation.objects.update_or_create(evenement=event, utilisateur=user, defaults={"revoked_at": None})
        return users

    def notify(self, event, action_name, users):
        record_workflow_event(
            self.request,
            event,
            f"evenement_{action_name}",
            "Agenda institutionnel",
            message="Une invitation ou un horaire a changé. Consultez votre agenda autorisé.",
            recipients=users,
            notification_category="evenement_institutionnel",
        )

    @transaction.atomic
    def create(self, request):
        if not can_manage(request):
            raise PermissionDenied("Le droit explicite de créer un événement dans cet établissement est requis.")
        values = self.checked(EventCommand)
        occupancy_lock()
        event = event_model()(etablissement=request.tenant, cree_par=request.user)
        users = self.apply_command(event, values)
        self.notify(event, "cree", users)
        return Response(self.serialize_detail(event), status=201)

    def locked_version(self, version):
        occupancy_lock()
        event = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=self.kwargs["pk"])
        if not can_manage(self.request, event):
            raise PermissionDenied("Le droit explicite de gérer cet événement est requis.")
        if event.version != version or event.statut != "planifie":
            raise EventConflict()
        return event

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def modifier(self, request, pk=None):
        values = self.checked(UpdateEventCommand)
        event = self.locked_version(values.pop("version"))
        event.version += 1
        users = self.apply_command(event, values)
        self.notify(event, "modifie", users)
        return Response(self.serialize_detail(event))

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def annuler(self, request, pk=None):
        values = self.checked(VersionCommand)
        event = self.locked_version(values["version"])
        event.statut = "annule"
        event.version += 1
        event.save()
        users = get_user_model().objects.filter(
            pk__in=event.invitations.filter(revoked_at__isnull=True).values("utilisateur_id"),
            etablissement=request.tenant,
            is_active=True,
        )
        self.notify(event, "annule", users)
        return Response(self.serialize_detail(event))
