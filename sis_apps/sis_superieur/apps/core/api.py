"""API views for core."""

from apps.core.models import WorkflowEvent, WorkflowNotification
from apps.core.serializers import WorkflowNotificationSerializer
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation, Parcours
from apps.integration.api import visible_course_mappings
from apps.paiements.api import visible_invoices
from django.db.models import Count, F, Q, Value
from django.db.models.functions import Concat
from rest_framework import generics, mixins, permissions, response, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import clone_request

from sis_common.authorization import filter_queryset_by_scopes, has_business_permission_or_role
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
DOCUMENT_SEARCH_RESOURCES = {
    "releves": ("releves.relevenotes", "numero_serie", "Relevé"),
    "transcripts": ("releves.transcript", "numero_serie", "Transcript"),
    "attestations": ("releves.attestation", "numero", "Attestation"),
}
ACADEMIC_SEARCH_RESOURCES = (
    "formations", "parcours", "etudiants", "factures", "cours", "evaluations_lms", *DOCUMENT_SEARCH_RESOURCES,
)


def visible_mapped_evaluations(request):
    """Narrow the authoritative evaluations queryset to current, local LMS mappings."""
    from apps.notes.api import EvaluationsViewSet

    tenant = current_lms_tenant(request)
    if (
        request.user.role in ("etudiant", "doctorant", "parent")
        or not request.user.has_perm("notes.view_evaluation")
    ):
        raise PermissionDenied("La recherche des évaluations LMS exige la permission de lecture des évaluations.")
    read_request = clone_request(request, "GET")
    view = EvaluationsViewSet(request=read_request, action="list", kwargs={}, format_kwarg=None)
    view.check_permissions(read_request)
    queryset = view.get_queryset()
    if queryset.query.is_empty():
        raise PermissionDenied("La consultation des évaluations n'est pas autorisée dans ce périmètre.")
    formation = "ecue__ue__maquette__formation__"
    return queryset.filter(
        Q(**{f"{formation}departement__isnull": True})
        | Q(**{f"{formation}departement__faculte__universite_id": tenant.pk}),
        Q(**{f"{formation}ecole_doctorale__isnull": True})
        | Q(**{f"{formation}ecole_doctorale__universite_id": tenant.pk}),
        semestre__annee_universitaire__universite_id=tenant.pk,
        ecue__ue__maquette__annee_universitaire__universite_id=tenant.pk,
        ecue__ue__semestre__annee_universitaire__universite_id=tenant.pk,
        enseignant__etablissement_id=tenant.pk,
        edx_assessment__actif=True,
        edx_assessment__course__actif=True,
        edx_assessment__course__ecue_id=F("ecue_id"),
    ).exclude(edx_assessment__subsection_id="").exclude(edx_assessment__course__course_id="")


class AcademicSearchResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    nom = serializers.CharField()


class AcademicSearchPagination(SISPagination):
    page_size = 20
    max_page_size = 50


class AcademicSearchView(generics.ListAPIView):
    """Recherche GET ?ressource=type&q=terme.

    Types : formations, parcours, etudiants, factures, cours, evaluations_lms,
    releves, transcripts, attestations.
    Chaque requête porte sur un seul modèle, et ne renvoie que id, code et nom.
    Pagination : 20 résultats par défaut, au plus 50 via page_size.
    Les formations sans rattachement sont propres au schéma du tenant courant.
    Les étudiants restent soumis au même périmètre que leur fiche.
    Les factures sont recherchées par numéro dans le périmètre de l'API finance,
    sans exposer l'identité de l'étudiant ni les montants.
    Les cours sont les EdxCourseMapping, recherchés par course_id ou course_name,
    réservés au même accès administrateur LMS que la liste des mappings.
    Leur id est celui du mapping, leur code la clé LMS et leur nom le course_name.
    Les mappings inactifs restent consultables par ces administrateurs.
    Le détail GET /api/v1/integration/mappings/courses/{id}/ partage les mêmes
    restrictions integration.view_edxcoursemapping que la liste et la recherche.
    evaluations_lms désigne uniquement les évaluations SIS reliées à une sous-section
    LMS par un mapping actif et cohérent vers un cours actif du tenant. La permission
    notes.view_evaluation est requise, en plus du queryset de l'API notes et de ses
    périmètres ; les apprenants et parents ne disposent pas ici d'un accès personnel.
    Recherche par titre ou identifiant de sous-section ; id est celui de l'évaluation,
    code l'identifiant de sous-section, nom le titre SIS. La cible de détail est
    GET /api/v1/notes/evaluations/{id}/, avec les permissions courantes de cette API.
    Ni description, notes, identité d'apprenant, ni URL LMS ne sont renvoyées.
    Les trois types de documents sont recherchés par numéro dans le périmètre
    courant de leur PDF officiel, y compris les restrictions de validation,
    de propriétaire et les périmètres métier. Le nom est le type et le numéro,
    jamais l'identité du bénéficiaire, les notes ou le chemin du fichier.
    Ce périmètre ne couvre ni les archives signées ni les diplômes délivrés,
    ni le catalogue natif de toutes les activités LMS ; une formation n'est pas un cours LMS.
    """

    permission_classes = [ActiveTenantAccess]
    serializer_class = AcademicSearchResultSerializer
    pagination_class = AcademicSearchPagination
    filter_backends = []

    def get_queryset(self):
        resource = self.request.query_params.get("ressource")
        if resource not in ACADEMIC_SEARCH_RESOURCES:
            raise ValidationError({"ressource": f"Choisissez parmi : {', '.join(ACADEMIC_SEARCH_RESOURCES)}."})
        raw_term = self.request.query_params.get("q", "")
        term = raw_term.strip()
        if (
            not 2 <= len(term) <= 100
            or len(raw_term) > 100
            or any(ord(char) < 32 or ord(char) == 127 for char in raw_term)
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

        if resource in DOCUMENT_SEARCH_RESOURCES:
            from sis_common.signed_documents import source_view

            source_type, number_field, label = DOCUMENT_SEARCH_RESOURCES[resource]
            view, _, _ = source_view(self.request, source_type)
            return view.get_queryset().filter(**{f"{number_field}__icontains": term}).annotate(
                code=F(number_field),
                nom=Concat(Value(f"{label} "), number_field),
            ).order_by("pk").values("id", "code", "nom")

        model = {"formations": Formation, "parcours": Parcours, "etudiants": Etudiant}[resource]
        permission = f"{model._meta.app_label}.view_{model._meta.model_name}"
        if not self.request.user.has_perm(permission):
            raise PermissionDenied("La consultation de cette ressource exige sa permission de lecture.")

        tenant_id = self.request.tenant.pk
        if resource == "etudiants":
            queryset = Etudiant.objects.filter(universite_id=tenant_id)
            queryset = filter_queryset_by_scopes(queryset, self.request.user, permission, {"etudiants": "pk"})
            if self.request.user.role in ("etudiant", "doctorant", "parent") and not self.request.user.is_superuser:
                queryset = queryset.filter(user=self.request.user)
            return queryset.filter(
                Q(matricule__icontains=term)
                | Q(user__first_name__icontains=term)
                | Q(user__last_name__icontains=term)
            ).annotate(
                code=F("matricule"),
                nom=Concat("user__first_name", Value(" "), "user__last_name"),
            ).order_by("pk").values("id", "code", "nom")

        prefix = "" if model is Formation else "formation__"
        queryset = model.objects.filter(
            Q(**{f"{prefix}departement__isnull": True})
            | Q(**{f"{prefix}departement__faculte__universite_id": tenant_id}),
            Q(**{f"{prefix}ecole_doctorale__isnull": True})
            | Q(**{f"{prefix}ecole_doctorale__universite_id": tenant_id}),
        )
        scope_fields = (
            {"formations": "pk", "departements": "departement_id"}
            if model is Formation
            else {"parcours": "pk", "formations": "formation_id", "departements": "formation__departement_id"}
        )
        queryset = filter_queryset_by_scopes(queryset, self.request.user, permission, scope_fields)
        if self.request.user.role in ("etudiant", "doctorant") and not self.request.user.is_superuser:
            from apps.etudiants.models import InscriptionAdministrative

            enrolled = InscriptionAdministrative.objects.filter(
                etudiant__user=self.request.user,
                statut="validee",
            ).values("formation_id")
            queryset = queryset.filter(**{f"{prefix}pk__in": enrolled})
        return queryset.filter(Q(code__icontains=term) | Q(nom__icontains=term)).order_by("pk").values(
            "id", "code", "nom"
        )


class IsWorkflowAuditor(permissions.IsAuthenticated):
    """Accès lecture réservé au pilotage métier et audit."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and has_business_permission_or_role(
            request.user,
            "core.view_workflowevent",
            (
                "president",
                "vice_president",
                "doyen",
                "directeur_etudes",
                "responsable_formation",
                "scolarite",
                "comptable",
            ),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=(
                "finance_manager_superieur",
                "document_signatory_superieur",
                "academic_registry_superieur",
                "exam_manager_superieur",
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
        from sis_common.institutional_events import filter_event_notifications

        queryset = filter_event_notifications(self.request, queryset)
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
