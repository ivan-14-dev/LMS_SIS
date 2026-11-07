"""API views for core."""

import unicodedata

from apps.core.models import WorkflowEvent, WorkflowNotification
from apps.core.serializers import WorkflowNotificationSerializer
from apps.eleves.api import visible_learners
from apps.integration.api import visible_course_mappings
from apps.paiements.api import visible_invoices
from django.db.models import CharField, Count, F, Q, Value
from django.db.models.functions import Cast, Concat
from rest_framework import generics, mixins, permissions, response, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import clone_request

from sis_common.authorization import has_business_permission_or_role
from sis_common.delegations import ActiveTenantAccess
from sis_common.lms_tenants import current_lms_tenant
from sis_common.notification_channels import (
    notification_matches_delivery_filters,
    summarize_notification_deliveries,
    summarize_notification_delivery_trends,
)
from sis_common.pagination import SISPagination
from sis_common.reporting import configured_report, export_queryset
from sis_common.workflow_filters import EVENT_FILTERS, PRIVATE_WORKFLOW_MODELS, filter_events, validated_event_filters

from .serializers import WorkflowEventSerializer

EVENT_REPORT_FIELDS = {
    "action": ("Action", "action"),
    "title": ("Titre", "title"),
    "app_label": ("Module", "app_label"),
    "model": ("Modèle", "model"),
    "object_repr": ("Objet", "object_repr"),
    "actor": ("Acteur", "actor__username"),
    "tenant_id": ("Tenant", "tenant_id"),
    "request_id": ("Requête", "request_id"),
    "created_at": ("Date", "created_at"),
}
EVENT_REPORT_FILTERS = EVENT_FILTERS
EVENT_REPORT_GROUPS = {
    "action": "action",
    "app_label": "app_label",
    "model": "model",
}


def visible_mapped_evaluations(request):
    """Narrow the authoritative evaluations queryset to coherent local LMS mappings."""
    from apps.notes.api import EvaluationsViewSet

    tenant = current_lms_tenant(request)
    if (
        not tenant.actif
        or request.user.role in ("eleve", "parent")
        or not request.user.has_perm("notes.view_evaluation")
    ):
        raise PermissionDenied("La recherche des évaluations LMS exige la permission de lecture des évaluations.")
    read_request = clone_request(request, "GET")
    view = EvaluationsViewSet(request=read_request, action="list", kwargs={}, format_kwarg=None)
    view.check_permissions(read_request)
    queryset = view.get_queryset()
    if queryset.query.is_empty():
        raise PermissionDenied("La consultation des évaluations n'est pas autorisée dans ce périmètre.")
    return queryset.filter(
        classe__etablissement_id=tenant.pk,
        classe__annee_scolaire__etablissement_id=tenant.pk,
        classe__niveau__etablissement_id=tenant.pk,
        matiere__etablissement_id=tenant.pk,
        periode__annee_scolaire__etablissement_id=tenant.pk,
        periode__annee_scolaire_id=F("classe__annee_scolaire_id"),
        enseignant__user__etablissement_id=tenant.pk,
        edx_assessment__actif=True,
        edx_assessment__course__actif=True,
        edx_assessment__course__matiere_id=F("matiere_id"),
        edx_assessment__course__classe_id=F("classe_id"),
    ).exclude(edx_assessment__subsection_id="").exclude(edx_assessment__course__course_id="")


class AcademicSearchResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    nom = serializers.CharField()


class AcademicSearchPagination(SISPagination):
    page_size = 20
    max_page_size = 50


class AcademicSearchView(generics.ListAPIView):
    """Recherche GET ?ressource=eleves|factures|cours|evaluations_lms|bulletins&q=terme.

    Terme de 2 à 100 caractères, sans caractères de contrôle.
    Résultats id/code/nom, paginés par 20 (page_size plafonné à 50).
    Les élèves exigent eleves.view_eleve et le périmètre de leur API.
    Les factures reprennent le périmètre finance, par numéro uniquement,
    sans exposer l'identité de l'élève ni les montants.
    Les cours sont les EdxCourseMapping, recherchés par course_id/course_name,
    avec le même accès administrateur LMS et les mêmes périmètres que leur liste.
    Les mappings inactifs sont inclus ; id est la PK du mapping, code la clé LMS,
    nom le course_name. Le détail est GET /integration/mappings/courses/<id>/.
    Les matières, classes, activités LMS et bulletins ne sont pas des cours.
    evaluations_lms désigne uniquement les évaluations SIS reliées à une sous-section
    LMS par un mapping actif vers un cours actif de même matière/classe. Les années,
    période, niveau et enseignant doivent être cohérents avec le tenant actif.
    notes.view_evaluation est requis en plus des permissions et du queryset de l'API
    notes, y compris les périmètres et l'attribution à l'enseignant (Personnel).
    Aucun accès personnel apprenant/parent ni catalogue natif d'activités LMS.
    Recherche par titre ou subsection_id ; id = évaluation, code = subsection_id,
    nom = titre SIS. Détail natif : GET /api/v1/notes/evaluations/{id}/.
    Ni description, notes, identité d'élève, ni URL LMS ne sont renvoyées.
    Les bulletins utilisent le périmètre de leur PDF officiel, publication et
    accès parent/professeur principal compris. Recherche sur la référence
    existante du PDF BUL-<id>, pas sur un numéro métier persistant ni sur l'élève.
    code = BUL-<id>, nom = Bulletin BUL-<id> ; ni notes, ni identité, ni fichier.
    """

    permission_classes = [ActiveTenantAccess]
    serializer_class = AcademicSearchResultSerializer
    pagination_class = AcademicSearchPagination
    filter_backends = []

    def get_queryset(self):
        resource = self.request.query_params.get("ressource")
        if resource not in ("eleves", "factures", "cours", "evaluations_lms", "bulletins"):
            raise ValidationError({"ressource": "Choisissez eleves, factures, cours, evaluations_lms ou bulletins."})
        raw_term = self.request.query_params.get("q", "")
        term = raw_term.strip()
        if (
            not 2 <= len(term) <= 100
            or len(raw_term) > 100
            or any(unicodedata.category(char) == "Cc" for char in raw_term)
        ):
            raise ValidationError({"q": "Saisissez entre 2 et 100 caractères, sans caractères de contrôle."})

        if resource == "factures":
            return visible_invoices(self.request).filter(numero__icontains=term).annotate(
                code=F("numero"),
                nom=Concat(Value("Facture "), "numero"),
            ).order_by("pk").values("id", "code", "nom")

        if resource == "cours":
            return visible_course_mappings(self.request).filter(
                Q(course_id__icontains=term) | Q(course_name__icontains=term)
            ).annotate(code=F("course_id"), nom=F("course_name")).order_by("pk").values("id", "code", "nom")

        if resource == "evaluations_lms":
            return visible_mapped_evaluations(self.request).filter(
                Q(titre__icontains=term) | Q(edx_assessment__subsection_id__icontains=term)
            ).annotate(code=F("edx_assessment__subsection_id"), nom=F("titre")).order_by("pk").values(
                "id", "code", "nom"
            )

        if resource == "bulletins":
            from sis_common.signed_documents import source_view

            view, _, _ = source_view(self.request, "notes.bulletin")
            return view.get_queryset().annotate(
                code=Concat(Value("BUL-"), Cast("pk", output_field=CharField())),
            ).filter(code__icontains=term).annotate(
                nom=Concat(Value("Bulletin "), "code"),
            ).order_by("pk").values("id", "code", "nom")

        if not self.request.user.has_perm("eleves.view_eleve"):
            raise PermissionDenied("La consultation de cette ressource exige sa permission de lecture.")
        return visible_learners(self.request).filter(
            Q(matricule__icontains=term)
            | Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term)
        ).annotate(
            code=F("matricule"),
            nom=Concat("user__first_name", Value(" "), "user__last_name"),
        ).order_by("pk").values("id", "code", "nom")


class IsWorkflowAuditor(permissions.IsAuthenticated):
    """Accès lecture réservé au pilotage métier et audit."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and has_business_permission_or_role(
            request.user,
            "core.view_workflowevent",
            (
                "direction",
                "responsable_pedagogique",
                "vie_scolaire",
                "personnel_administratif",
                "comptable",
            ),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=(
                "finance_manager_secondary",
                "document_signatory_secondary",
                "academic_registry_secondary",
                "exam_manager_secondary",
            ),
        )


class WorkflowEventViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Historique global des événements de workflow."""

    serializer_class = WorkflowEventSerializer
    permission_classes = [IsWorkflowAuditor]

    def get_queryset(self):
        queryset = WorkflowEvent.objects.exclude(app_label="core", model__in=PRIVATE_WORKFLOW_MODELS).select_related(
            "actor"
        )
        tenant_id = getattr(getattr(self.request, "tenant", None), "id", None)
        if tenant_id is not None:
            queryset = queryset.filter(tenant_id=tenant_id)
        return filter_events(queryset, self.request.query_params.dict()).order_by("-created_at", "-id")

    @action(detail=False, methods=["get"])
    def acteurs(self, request):
        rows = (
            self.get_queryset()
            .exclude(actor=None)
            .order_by("actor__username")
            .values("actor_id", "actor__username", "actor__first_name", "actor__last_name")
            .distinct()
        )
        return response.Response(
            [
                {
                    "id": row["actor_id"],
                    "nom": " ".join(value for value in (row["actor__first_name"], row["actor__last_name"]) if value)
                    or row["actor__username"],
                }
                for row in rows
            ]
        )

    @action(detail=False, methods=["get"])
    def bilan(self, request):
        group_by = request.query_params.get("group_by", "action")
        group_field = EVENT_REPORT_GROUPS.get(group_by)
        if not group_field:
            return response.Response(
                {"group_by": f"Valeurs acceptées: {', '.join(EVENT_REPORT_GROUPS)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows = self.get_queryset().values(group_field).annotate(nombre=Count("id")).order_by(group_field)
        return response.Response([{"groupe": row[group_field], "nombre": row["nombre"]} for row in rows])

    @action(detail=False, methods=["post"])
    def exporter(self, request):
        report = configured_report(
            request,
            request.data.get("report"),
            allowed_datasets={"workflow_events"},
        )
        return export_queryset(
            request,
            self.get_queryset(),
            report,
            EVENT_REPORT_FIELDS,
            EVENT_REPORT_FILTERS,
            validated_event_filters(request.data.get("filters", {})),
        )


class WorkflowNotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Notifications de workflow de l'utilisateur courant."""

    serializer_class = WorkflowNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _apply_delivery_filters(self, queryset):
        category = self.request.query_params.get("category", "").strip()
        if category:
            queryset = queryset.filter(category=category)
        channel = self.request.query_params.get("delivery_channel", "").strip()
        delivery_status = self.request.query_params.get("delivery_status", "").strip()
        if channel or delivery_status:
            matching_ids = [
                notification.id
                for notification in queryset
                if notification_matches_delivery_filters(notification, channel=channel, status=delivery_status)
            ]
            queryset = queryset.filter(id__in=matching_ids)
        return queryset

    def get_queryset(self):
        queryset = WorkflowNotification.objects.filter(recipient=self.request.user).select_related(
            "event", "event__actor"
        )
        if self.request.query_params.get("non_lues") == "1":
            queryset = queryset.filter(is_read=False)
        return self._apply_delivery_filters(queryset).order_by("-created_at")

    @action(detail=True, methods=["post"])
    def marquer_lue(self, request, pk=None):
        notification = self.get_object()
        notification.mark_read()
        return response.Response(
            self.get_serializer(notification).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def tout_marquer_lu(self, request):
        for notification in self.get_queryset().filter(is_read=False):
            notification.mark_read()
        return response.Response({"detail": "Notifications marquées comme lues."})

    @action(detail=False, methods=["get"])
    def bilan_livraison(self, request):
        queryset = self.get_queryset()
        return response.Response(summarize_notification_deliveries(queryset))

    @action(detail=False, methods=["get"])
    def tendances_livraison(self, request):
        queryset = self.get_queryset()
        return response.Response(summarize_notification_delivery_trends(queryset))
