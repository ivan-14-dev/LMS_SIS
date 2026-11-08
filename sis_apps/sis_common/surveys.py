"""Management and recipient portal endpoints, with separate response contracts."""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from sis_common.authorization import has_business_permission, is_current_tenant_user
from sis_common.module_registry import require_module
from sis_common.pagination import SISPagination
from sis_common.survey_serializers import ConfigureCommand, RespondCommand, RevokeCommand, SurveyCommand, VersionCommand
from sis_common.workflow_tracking import record_workflow_event

Survey = apps.get_model("core", "InstitutionalSurvey")
Recipient = apps.get_model("core", "SurveyRecipient")
Answer = apps.get_model("core", "SurveyResponse")
MANAGE = "core.gerer_enquete_institutionnelle"
POLICY = "Nominative : votre identité et vos réponses sont visibles par les gestionnaires habilités. Aucun anonymat."


def can_manage(request):
    return has_business_permission(request.user, MANAGE, context={"etablissement_id": request.tenant.pk})


class SurveyAccess(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not (
            tenant
            and tenant.actif
            and request.user.is_active
            and request.user.etablissement_id == tenant.pk
            and is_current_tenant_user(request)
        ):
            return False
        require_module(tenant, "sis.surveys")
        return True


class SurveyManagementAccess(SurveyAccess):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and can_manage(request)


class SurveyConflict(APIException):
    status_code = 409
    default_detail = "L’enquête a changé. Rechargez-la avant de réessayer."
    default_code = "survey_conflict"


def user_summary(user):
    return {"id": user.pk, "nom": user.get_full_name() or user.username, "profil": user.get_role_display()}


def summary(survey):
    return {
        "id": str(survey.pk),
        "titre": survey.titre,
        "description": survey.description,
        "statut": survey.statut,
        "politique": survey.politique,
        "information": POLICY,
    }


class SurveyBaseViewSet(viewsets.GenericViewSet):
    serializer_class = SurveyCommand
    pagination_class = SISPagination
    filter_backends = []
    lookup_value_regex = "[0-9a-f-]{36}"

    def get_queryset(self):
        return Survey.objects.filter(etablissement_id=self.request.tenant.pk)

    def checked(self, command, **context):
        serializer = command(data=self.request.data, context=context)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def locked(self):
        return get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=self.kwargs["pk"])

    def collection(self, queryset, serialize):
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([serialize(item) for item in page])

    def list(self, request):
        return self.collection(self.get_queryset(), summary)

    def event(self, survey, action_name):
        # No answer text, title or recipient list in general audit/notifications.
        record_workflow_event(self.request, survey, f"enquete_{action_name}", "Enquête institutionnelle nominative")


class SurveyManagementViewSet(SurveyBaseViewSet):
    permission_classes = [SurveyManagementAccess]

    def serialize_detail(self, survey):
        return {
            **summary(survey),
            "version": survey.version,
            "questionnaire": survey.questionnaire,
            "destinataires": [
                {**user_summary(item.utilisateur), "revoked_at": item.revoked_at}
                for item in survey.destinataires.filter(
                    utilisateur__etablissement_id=self.request.tenant.pk
                ).select_related("utilisateur")
            ],
        }

    def retrieve(self, request, pk=None):
        return Response(self.serialize_detail(self.get_object()))

    def local_users(self, identifiers):
        users = list(
            get_user_model()
            .objects.select_for_update()
            .filter(pk__in=identifiers, is_active=True, etablissement_id=self.request.tenant.pk)
            .order_by("pk")
        )
        if len(users) != len(identifiers):
            raise ValidationError({"destinataires": "Sélectionnez uniquement des comptes actifs de cet établissement."})
        return users

    def versioned(self, command):
        values = self.checked(command)
        survey = self.locked()
        if survey.version != values.pop("version"):
            raise SurveyConflict()
        return survey, values

    def saved(self, survey, event):
        survey.version += 1
        survey.save()
        self.event(survey, event)
        return Response(self.serialize_detail(survey))

    @action(detail=False, methods=["get"])
    def candidats(self, request):
        term = request.query_params.get("q", "").strip()
        if not 2 <= len(term) <= 100:
            raise ValidationError({"q": "Recherchez entre 2 et 100 caractères."})
        users = (
            get_user_model()
            .objects.filter(etablissement_id=request.tenant.pk, is_active=True)
            .filter(Q(username__icontains=term) | Q(first_name__icontains=term) | Q(last_name__icontains=term))
            .order_by("last_name", "first_name", "pk")
        )
        return self.collection(users, user_summary)

    @transaction.atomic
    def create(self, request):
        values = self.checked(SurveyCommand)
        users = self.local_users(values.pop("destinataires"))
        survey = Survey.objects.create(etablissement=request.tenant, cree_par=request.user, **values)
        Recipient.objects.bulk_create([Recipient(enquete=survey, utilisateur=user) for user in users])
        self.event(survey, "cree")
        return Response(self.serialize_detail(survey), status=201)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def configurer(self, request, pk=None):
        survey, values = self.versioned(ConfigureCommand)
        if survey.statut != "brouillon":
            raise SurveyConflict("Le questionnaire et les destinataires sont figés après publication.")
        users = self.local_users(values.pop("destinataires"))
        for key, value in values.items():
            setattr(survey, key, value)
        survey.destinataires.all().delete()
        Recipient.objects.bulk_create([Recipient(enquete=survey, utilisateur=user) for user in users])
        return self.saved(survey, "configuree")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def publier(self, request, pk=None):
        survey, _ = self.versioned(VersionCommand)
        if survey.statut != "brouillon":
            raise SurveyConflict("Seul un brouillon peut être publié.")
        identifiers = list(survey.destinataires.values_list("utilisateur_id", flat=True))
        if not identifiers:
            raise ValidationError({"destinataires": "Au moins un destinataire est requis."})
        self.local_users(identifiers)
        survey.statut = "publiee"
        return self.saved(survey, "publiee")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def fermer(self, request, pk=None):
        survey, _ = self.versioned(VersionCommand)
        if survey.statut != "publiee":
            raise SurveyConflict("Seule une enquête publiée peut être fermée.")
        survey.statut = "fermee"
        return self.saved(survey, "fermee")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def revoquer(self, request, pk=None):
        survey, values = self.versioned(RevokeCommand)
        if survey.statut == "brouillon":
            raise SurveyConflict("Modifiez la sélection du brouillon avant publication.")
        recipient = get_object_or_404(survey.destinataires, utilisateur_id=values["destinataire"])
        if recipient.revoked_at:
            raise SurveyConflict("Ce destinataire est déjà révoqué.")
        recipient.revoked_at = timezone.now()
        recipient.save(update_fields=["revoked_at"])
        return self.saved(survey, "destinataire_revoque")

    @action(detail=True, methods=["get"])
    def resultats(self, request, pk=None):
        survey = self.get_object()
        recipients = survey.destinataires.filter(utilisateur__etablissement_id=request.tenant.pk)
        answers = Answer.objects.filter(destinataire__in=recipients).select_related("destinataire__utilisateur")
        rows = [
            {
                "destinataire": user_summary(answer.destinataire.utilisateur),
                "revoked_at": answer.destinataire.revoked_at,
                "reponses": answer.reponses,
                "created_at": answer.created_at,
            }
            for answer in answers
        ]
        return Response(
            {
                "politique": "nominative",
                "information": POLICY,
                "destinataires": recipients.count(),
                "reponses_recues": len(rows),
                "choix": [
                    {
                        "id": question["id"],
                        "libelle": question["libelle"],
                        "comptages": [
                            {
                                "choix": option,
                                "total": sum(row["reponses"].get(question["id"]) == option for row in rows),
                            }
                            for option in question["choix"]
                        ],
                    }
                    for question in survey.questionnaire
                    if question["type"] == "choix"
                ],
                "reponses": rows,
            }
        )


class SurveyPortalViewSet(SurveyBaseViewSet):
    permission_classes = [SurveyAccess]
    serializer_class = RespondCommand

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                statut__in=["publiee", "fermee"],
                destinataires__utilisateur=self.request.user,
                destinataires__revoked_at__isnull=True,
            )
        )

    @action(detail=False, methods=["get"])
    def capacites(self, request):
        return Response({"can_manage": can_manage(request), "politique": "nominative", "information": POLICY})

    def serialize_detail(self, survey):
        answer = Answer.objects.filter(
            destinataire__enquete=survey, destinataire__utilisateur=self.request.user
        ).first()
        return {
            **summary(survey),
            "questionnaire": survey.questionnaire,
            "ma_reponse": {"reponses": answer.reponses, "created_at": answer.created_at} if answer else None,
            "peut_repondre": survey.statut == "publiee" and answer is None,
        }

    def retrieve(self, request, pk=None):
        return Response(self.serialize_detail(self.get_object()))

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def repondre(self, request, pk=None):
        # The same parent lock serializes submissions, closure and recipient revocation.
        survey = self.locked()
        recipient = get_object_or_404(survey.destinataires, utilisateur=request.user, revoked_at__isnull=True)
        if survey.statut != "publiee":
            raise SurveyConflict("Cette enquête est fermée ; aucune nouvelle réponse n’est acceptée.")
        if Answer.objects.filter(destinataire=recipient).exists():
            raise SurveyConflict("Vous avez déjà répondu. Votre réponse ne sera pas remplacée.")
        values = self.checked(RespondCommand, questionnaire=survey.questionnaire)
        try:
            with transaction.atomic():
                Answer.objects.create(destinataire=recipient, reponses=values["reponses"])
        except IntegrityError as exc:
            raise SurveyConflict("Vous avez déjà répondu. Votre réponse ne sera pas remplacée.") from exc
        self.event(survey, "reponse_recue")
        return Response(self.serialize_detail(survey), status=201)
