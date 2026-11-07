"""Tenant-local pedagogical projects with team-private, append-only evidence."""

import logging
import unicodedata
from uuid import UUID

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max, Q
from django.http import FileResponse
from django.utils import timezone
from django.utils.text import get_valid_filename
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from sis_common.authorization import filter_queryset_by_scopes, has_business_permission, is_current_tenant_user
from sis_common.exam_files import hash_uploaded_file
from sis_common.module_registry import require_module
from sis_common.pagination import SISPagination
from sis_common.project_competencies import competency_source, readable_competencies, select_competencies
from sis_common.project_courses import (
    ProjectCoursePagination,
    course_snapshot,
    course_summary,
    readable_course_snapshot,
    selectable_project_courses,
    validate_project_course,
)
from sis_common.project_serializers import (
    DeliveryCommand,
    DeliverySerializer,
    EvaluationCommand,
    EvaluationSerializer,
    MembershipCommand,
    MilestoneCommand,
    MilestoneSerializer,
    ProjectConfigureCommand,
    ProjectCreateCommand,
    ProjectSerializer,
    TeamCreateCommand,
    TeamSerializer,
    VersionCommand,
)
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

Project = apps.get_model("core", "PedagogicalProject")
Team = apps.get_model("core", "ProjectTeam")
Membership = apps.get_model("core", "ProjectMembership")
Milestone = apps.get_model("core", "ProjectMilestone")
Delivery = apps.get_model("core", "ProjectDelivery")
Evaluation = apps.get_model("core", "ProjectEvaluation")
Contribution = apps.get_model("core", "ProjectContribution")
MANAGE = "core.gerer_projet_pedagogique"
EVALUATE = "core.evaluer_projet_pedagogique"
LEARNER_ROLES = ("eleve", "etudiant", "doctorant")
SCOPES = {"etablissement_id": "etablissement_id", "projet_id": "pk", "responsable_id": "responsable_id"}
TEAM_PATH = r"equipes/(?P<equipe_id>[0-9a-f-]{36})"
logger = logging.getLogger("apps.projets")


def project_context(tenant, project=None, owner_id=None):
    context = {"etablissement_id": tenant.pk}
    if project:
        context.update(projet_id=str(project.pk), responsable_id=project.responsable_id)
    if owner_id is not None:
        context["responsable_id"] = owner_id
    return context


def permitted(user, permission, tenant, project=None, owner_id=None):
    return (
        user.is_active
        and user.etablissement_id == tenant.pk
        and user.role not in LEARNER_ROLES
        and has_business_permission(user, permission, context=project_context(tenant, project, owner_id))
    )


def scoped_projects(queryset, user, permission):
    constraints = (user.attributs_acces or {}).get("permission_scopes", {}).get(permission, {})
    if not user.is_superuser:
        for key, values in constraints.items():
            if key not in SCOPES or not isinstance(values, list):
                return queryset.none()
            for value in values:
                if key == "projet_id":
                    try:
                        if not isinstance(value, str) or str(UUID(value)) != value:
                            return queryset.none()
                    except ValueError:
                        return queryset.none()
                elif type(value) is not int:
                    return queryset.none()
    return filter_queryset_by_scopes(queryset, user, permission, SCOPES)


class ProjectAccess(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant or not tenant.actif or not is_current_tenant_user(request):
            return False
        if not request.user.is_active or request.user.etablissement_id != tenant.pk:
            return False
        require_module(tenant, "sis.projects")
        return True


class StaleProject(APIException):
    status_code = 409
    default_detail = "Le projet a été modifié. Rechargez sa version avant de réessayer."
    default_code = "stale_project"


class ProjectViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [ProjectAccess]
    serializer_class = ProjectSerializer
    pagination_class = SISPagination
    filter_backends = []
    lookup_value_regex = "[0-9a-f-]{36}"

    def can_manage(self, project=None):
        return permitted(self.request.user, MANAGE, self.request.tenant, project)

    def agent_queryset(self, permission):
        codename = permission.split(".")[1]
        return (
            get_user_model()
            .objects.filter(etablissement_id=self.request.tenant.pk, is_active=True)
            .exclude(role__in=LEARNER_ROLES)
            .filter(
                Q(is_superuser=True)
                | Q(user_permissions__content_type__app_label="core", user_permissions__codename=codename)
                | Q(groups__permissions__content_type__app_label="core", groups__permissions__codename=codename)
            )
            .distinct()
        )

    def eligible_owner(self, owner, project=None):
        tenant = self.request.tenant
        return permitted(owner, MANAGE, tenant, project, owner.pk) and permitted(
            self.request.user, MANAGE, tenant, project, owner.pk
        )

    def can_create(self):
        user = self.request.user
        if user.role in LEARNER_ROLES or not user.has_perm(MANAGE):
            return False
        if self.eligible_owner(user):
            return True
        return any(self.eligible_owner(owner) for owner in self.agent_queryset(MANAGE))

    def creation_owner(self, owner_id):
        # A future project has no project-id context: only eligible owners grant creation.
        if not permitted(self.request.user, MANAGE, self.request.tenant, owner_id=owner_id):
            raise PermissionDenied("La création exige une permission de gestion pour ce responsable.")
        owner = self.local_users([owner_id], "responsable")[0]
        if not self.eligible_owner(owner):
            raise ValidationError({"responsable": "Le responsable doit être habilité à gérer le nouveau projet."})
        return owner

    def can_evaluate(self, project):
        return permitted(self.request.user, EVALUATE, self.request.tenant, project) and (
            project.responsable_id == self.request.user.pk
            or project.evaluateurs.filter(pk=self.request.user.pk).exists()
        )

    def privileged(self, project):
        return self.can_manage(project) or self.can_evaluate(project)

    def is_member(self, team):
        return team.appartenances.filter(
            membre_id=self.request.user.pk,
            membre__is_active=True,
            membre__etablissement_id=self.request.tenant.pk,
            retired_at__isnull=True,
        ).exists()

    def get_queryset(self):
        user, tenant = self.request.user, self.request.tenant
        queryset = Project.objects.filter(etablissement_id=tenant.pk, responsable__etablissement_id=tenant.pk)
        membership = queryset.filter(
            equipes__appartenances__membre_id=user.pk, equipes__appartenances__retired_at__isnull=True
        )
        access = Q(pk__in=membership.values("pk"))
        if user.role not in LEARNER_ROLES:
            for permission in (MANAGE, EVALUATE):
                if user.has_perm(permission):
                    scoped = scoped_projects(queryset, user, permission)
                    if permission == EVALUATE:
                        scoped = scoped.filter(Q(responsable=user) | Q(evaluateurs=user))
                    access |= Q(pk__in=scoped.values("pk"))
        return queryset.filter(access)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        mode = request.query_params.get("mode")
        if mode:
            if mode not in dict(Project.MODES):
                raise ValidationError({"mode": "Choisissez individuel ou collectif."})
            queryset = queryset.filter(mode=mode)
        term = request.query_params.get("q", "").strip()
        if len(term) > 200:
            raise ValidationError({"q": "Recherche limitée à 200 caractères."})
        if term:
            queryset = queryset.filter(titre__icontains=term)
        return self.collection(queryset, ProjectSerializer)

    def collection(self, queryset, serializer_class, **context):
        page = self.paginate_queryset(queryset)
        data = serializer_class(
            page if page is not None else queryset, many=True, context={**self.get_serializer_context(), **context}
        ).data
        return self.get_paginated_response(data) if page is not None else Response(data)

    def locked_project(self):
        # All project mutations serialize on the same row, including membership revocations.
        return get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=self.kwargs["pk"])

    def command(self, command_class, project=None):
        serializer = command_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        if project is not None and values.pop("version") != project.version:
            raise StaleProject()
        return values

    def require_manager(self, project=None):
        if not self.can_manage(project):
            raise PermissionDenied("La gestion de ce projet exige une permission dans ce périmètre.")

    def require_evaluator(self, project, team):
        if not self.can_evaluate(project) or self.is_member(team):
            raise PermissionDenied("Un évaluateur habilité et affecté, extérieur à l'équipe, est requis.")

    def team(self, project, team_id):
        queryset = project.equipes.all()
        if not self.privileged(project):
            queryset = queryset.filter(appartenances__membre=self.request.user, appartenances__retired_at__isnull=True)
        return get_object_or_404(queryset.distinct(), pk=team_id)

    def milestone(self, project, milestone_id):
        return get_object_or_404(project.jalons, pk=milestone_id)

    def event(self, project, action_name, **metadata):
        metadata.setdefault("cours", self.binding_evidence(project))
        metadata.setdefault("competences", project.competences_snapshot)
        metadata["version"] = project.version
        record_workflow_event(
            self.request, project, f"projet_{action_name}", "Suivi de projet pédagogique", metadata=metadata
        )

    def binding_evidence(self, project):
        event = (
            workflow_history_queryset(project).filter(action__in=["projet_creation", "projet_configuration"]).first()
        )
        return event.metadata.get("cours") if event else None

    def updated(self, project, action_name, **metadata):
        project.version += 1
        project.save()
        self.event(project, action_name, **metadata)

    def result(self, project, key, obj, serializer_class, status=200):
        data = serializer_class(
            obj, context={**self.get_serializer_context(), "privileged": self.privileged(project)}
        ).data
        return Response({"version": project.version, key: data}, status=status)

    def local_users(self, ids, field):
        if len(ids) != len(set(ids)):
            raise ValidationError({field: "Un compte ne peut figurer qu'une fois."})
        users = list(
            get_user_model().objects.filter(pk__in=ids, etablissement_id=self.request.tenant.pk, is_active=True)
        )
        if len(users) != len(ids):
            raise ValidationError({field: "Tous les comptes doivent être actifs dans cet établissement."})
        return users

    def validate_delegation(self, project, owner_id, evaluator_ids):
        owner = self.local_users([owner_id], "responsable")[0]
        tenant = self.request.tenant
        if not permitted(owner, MANAGE, tenant, project, owner.pk):
            raise ValidationError({"responsable": "Le responsable doit être habilité à gérer ce projet."})
        if not permitted(self.request.user, MANAGE, tenant, project, owner.pk):
            raise PermissionDenied("Cette affectation sortirait de votre périmètre de gestion.")
        evaluators = self.local_users(evaluator_ids, "evaluateurs")
        if any(not permitted(user, EVALUATE, tenant, project, owner.pk) for user in evaluators):
            raise ValidationError({"evaluateurs": "Chaque évaluateur doit être habilité dans le périmètre du projet."})
        return owner, evaluators

    @action(detail=False, methods=["get"])
    def capacites(self, request):
        return Response({"can_create": self.can_create(), "permissions": [MANAGE, EVALUATE]})

    @action(detail=False, methods=["get"])
    def candidats(self, request):
        project = None
        owner_id = None
        if request.query_params.get("projet"):
            if "responsable" in request.query_params:
                raise ValidationError({"responsable": "Utilisez projet ou responsable, pas les deux."})
            try:
                project_id = UUID(request.query_params["projet"])
            except ValueError:
                raise ValidationError({"projet": "Identifiant de projet invalide."})
            project = get_object_or_404(self.get_queryset(), pk=project_id)
            self.require_manager(project)
        elif not self.can_create():
            raise PermissionDenied("Aucun responsable éligible dans votre périmètre de création.")
        kind = request.query_params.get("type")
        if kind not in ("membre", "responsable", "evaluateur"):
            raise ValidationError({"type": "Choisissez membre, responsable ou evaluateur."})
        if project is None and (kind != "responsable" or "responsable" in request.query_params):
            try:
                owner_id = int(request.query_params.get("responsable", request.user.pk))
            except (TypeError, ValueError):
                raise ValidationError({"responsable": "Un identifiant de compte entier est attendu."})
            if owner_id < 1:
                raise ValidationError({"responsable": "Un identifiant de compte positif est attendu."})
            self.creation_owner(owner_id)
        term = request.query_params.get("q", "").strip()
        if not 2 <= len(term) <= 100:
            raise ValidationError({"q": "Saisissez entre 2 et 100 caractères."})
        queryset = (
            get_user_model()
            .objects.filter(etablissement_id=request.tenant.pk, is_active=True)
            .filter(Q(username__icontains=term) | Q(first_name__icontains=term) | Q(last_name__icontains=term))
            .order_by("last_name", "first_name", "pk")
        )
        if kind == "membre":
            queryset = queryset.filter(role__in=LEARNER_ROLES)
        else:
            permission = MANAGE if kind == "responsable" else EVALUATE
            queryset = queryset.filter(pk__in=self.agent_queryset(permission).values("pk"))
        result = []
        for user in queryset:
            candidate_owner_id = user.pk if kind == "responsable" else owner_id
            if kind != "membre" and not permitted(user, permission, request.tenant, project, candidate_owner_id):
                continue
            if kind == "responsable" and not permitted(request.user, MANAGE, request.tenant, project, user.pk):
                continue
            result.append({"id": user.pk, "nom": user.get_full_name() or user.username})
            if len(result) == 20:
                break
        return Response({"results": result})

    @action(detail=False, methods=["get"], url_path="cours-candidats")
    def cours_candidats(self, request):
        owner = self.course_candidate_owner(request)
        raw_term = request.query_params.get("q", "")
        term = raw_term.strip()
        if (
            not 2 <= len(term) <= 100
            or len(raw_term) > 100
            or any(unicodedata.category(char).startswith("C") for char in raw_term)
        ):
            raise ValidationError({"q": "Saisissez entre 2 et 100 caractères, sans caractères de contrôle."})
        queryset = (
            selectable_project_courses(request, owner)
            .filter(Q(course_name__icontains=term) | Q(course_id__icontains=term))
            .order_by("course_name", "pk")
        )
        paginator = ProjectCoursePagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([course_summary(course) for course in page])

    def course_candidate_owner(self, request):
        project = None
        if "projet" in request.query_params:
            try:
                project_id = UUID(request.query_params["projet"])
            except ValueError:
                raise ValidationError({"projet": "Identifiant de projet invalide."})
            project = get_object_or_404(self.get_queryset(), pk=project_id)
            self.require_manager(project)
        try:
            owner_id = int(request.query_params.get("responsable", project.responsable_id if project else ""))
        except (TypeError, ValueError):
            raise ValidationError({"responsable": "Un identifiant de responsable positif est requis."})
        if owner_id < 1:
            raise ValidationError({"responsable": "Un identifiant de responsable positif est requis."})
        if project is None:
            owner = self.creation_owner(owner_id)
        else:
            owner, _ = self.validate_delegation(project, owner_id, [])
        return owner

    @action(detail=False, methods=["get"], url_path="competences-candidates")
    @transaction.atomic
    def competences_candidates(self, request):
        owner = self.course_candidate_owner(request)
        raw_course = request.query_params.get("cours", "")
        if not raw_course.isascii() or not raw_course.isdecimal() or len(raw_course) > 18 or int(raw_course) < 1:
            raise ValidationError({"cours": "Un identifiant de cours positif est requis."})
        course = validate_project_course(request, owner, int(raw_course))
        criteria, mode, _, _ = competency_source(request, course)
        paginator = ProjectCoursePagination()
        page = paginator.paginate_queryset(criteria, request, view=self)
        response = paginator.get_paginated_response(page)
        response.data["etat"] = mode
        return response

    @transaction.atomic
    def create(self, request):
        values = self.command(ProjectCreateCommand)
        owner_id = values.pop("responsable")
        self.creation_owner(owner_id)
        evaluator_ids = values.pop("evaluateurs")
        course_id = values.pop("cours")
        codes = values.pop("competences")
        project = Project(etablissement=request.tenant, cree_par=request.user, responsable_id=owner_id, **values)
        owner, evaluators = self.validate_delegation(project, owner_id, evaluator_ids)
        project.responsable = owner
        project.cours = validate_project_course(request, owner, course_id)
        project.competences_snapshot = select_competencies(request, project.cours, codes)
        project.save()
        project.evaluateurs.set(evaluators)
        self.event(
            project,
            "creation",
            responsable=owner.pk,
            evaluateurs=evaluator_ids,
            mode=project.mode,
            titre=project.titre,
            description=project.description,
            cours=course_snapshot(project.cours),
        )
        return Response(self.get_serializer(project).data, status=201)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def configurer(self, request, pk=None):
        project = self.locked_project()
        self.require_manager(project)
        values = self.command(ProjectConfigureCommand, project)
        if not values:
            raise ValidationError({"detail": "Indiquez au moins un changement."})
        owner_id = values.pop("responsable", project.responsable_id)
        evaluator_ids = values.pop("evaluateurs", list(project.evaluateurs.values_list("pk", flat=True)))
        course_id = values.pop("cours", project.cours_id)
        codes = values.pop("competences", None)
        owner, evaluators = self.validate_delegation(project, owner_id, evaluator_ids)
        course = validate_project_course(request, owner, course_id)
        competencies = select_competencies(request, course, codes, previous=project.competences_snapshot)
        before = {
            "responsable": project.responsable_id,
            "evaluateurs": list(project.evaluateurs.values_list("pk", flat=True)),
            "titre": project.titre,
            "description": project.description,
            "cours": self.binding_evidence(project),
            "competences": project.competences_snapshot,
        }
        project.responsable = owner
        project.cours = course
        project.competences_snapshot = competencies
        for field, value in values.items():
            setattr(project, field, value)
        project.evaluateurs.set(evaluators)
        self.updated(
            project,
            "configuration",
            avant=before,
            responsable=owner.pk,
            evaluateurs=evaluator_ids,
            cours=course_snapshot(course),
            **values,
        )
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["get", "post"])
    @transaction.atomic
    def jalons(self, request, pk=None):
        project = self.locked_project() if request.method == "POST" else self.get_object()
        if request.method == "GET":
            return self.collection(project.jalons.all(), MilestoneSerializer)
        self.require_manager(project)
        values = self.command(MilestoneCommand, project)
        if project.jalons.filter(ordre=values["ordre"]).exists():
            raise ValidationError({"ordre": "Cet ordre est déjà utilisé par un jalon."})
        milestone = Milestone.objects.create(projet=project, cree_par=request.user, **values)
        self.updated(project, "jalon", jalon=str(milestone.pk))
        return self.result(project, "jalon", milestone, MilestoneSerializer, status=201)

    def replace_members(self, project, team, member_ids, creating=False):
        users = self.local_users(member_ids, "membres")
        if creating and not users:
            raise ValidationError({"membres": "Une équipe doit être créée avec au moins un apprenant."})
        if project.mode == "individuel" and len(users) > 1:
            raise ValidationError({"membres": "Un projet individuel accepte une seule personne active par équipe."})
        if any(user.role not in LEARNER_ROLES for user in users):
            raise ValidationError({"membres": "Les membres doivent être des apprenants."})
        if (
            Membership.objects.filter(equipe__projet=project, membre_id__in=member_ids, retired_at__isnull=True)
            .exclude(equipe=team)
            .exists()
        ):
            raise ValidationError({"membres": "Un apprenant ne peut appartenir qu'à une équipe active par projet."})
        previous = team.appartenances.filter(retired_at__isnull=True)
        old_ids = set(previous.values_list("membre_id", flat=True))
        previous.exclude(membre_id__in=member_ids).update(retired_at=timezone.now(), retire_par=self.request.user)
        for user in users:
            if user.pk not in old_ids:
                Membership.objects.create(equipe=team, membre=user, ajoute_par=self.request.user)
        return {"ajoutes": sorted(set(member_ids) - old_ids), "retires": sorted(old_ids - set(member_ids))}

    @action(detail=True, methods=["get", "post"])
    @transaction.atomic
    def equipes(self, request, pk=None):
        project = self.locked_project() if request.method == "POST" else self.get_object()
        if request.method == "GET":
            queryset = project.equipes.all()
            if not self.privileged(project):
                queryset = queryset.filter(
                    appartenances__membre=request.user, appartenances__retired_at__isnull=True
                ).distinct()
            return self.collection(queryset, TeamSerializer)
        self.require_manager(project)
        values = self.command(TeamCreateCommand, project)
        if project.equipes.filter(nom=values["nom"]).exists():
            raise ValidationError({"nom": "Ce nom d'équipe existe déjà dans le projet."})
        team = Team.objects.create(projet=project, nom=values["nom"], cree_par=request.user)
        changes = self.replace_members(project, team, values["membres"], creating=True)
        self.updated(project, "equipe", equipe=str(team.pk), **changes)
        return self.result(project, "equipe", team, TeamSerializer, status=201)

    @action(detail=True, methods=["post"], url_path=TEAM_PATH + "/membres")
    @transaction.atomic
    def membres(self, request, pk=None, equipe_id=None):
        project = self.locked_project()
        self.require_manager(project)
        team = self.team(project, equipe_id)
        values = self.command(MembershipCommand, project)
        changes = self.replace_members(project, team, values["membres"])
        self.updated(project, "membres", equipe=str(team.pk), **changes)
        return self.result(project, "equipe", team, TeamSerializer)

    def filter_milestone(self, queryset, project):
        selected = self.request.query_params.get("jalon")
        if selected:
            try:
                milestone_id = UUID(selected)
            except ValueError:
                raise ValidationError({"jalon": "Identifiant de jalon invalide."})
            milestone = self.milestone(project, milestone_id)
            queryset = queryset.filter(jalon=milestone)
        return queryset.filter(jalon__projet=project)

    @action(detail=True, methods=["get", "post"], url_path=TEAM_PATH + "/livrables")
    def livrables(self, request, pk=None, equipe_id=None):
        if request.method == "GET":
            project = self.get_object()
            team = self.team(project, equipe_id)
            return self.collection(
                self.filter_milestone(team.livrables.select_related("jalon"), project), DeliverySerializer
            )
        delivery = None
        committed = False
        try:
            with transaction.atomic():
                project = self.locked_project()
                team = self.team(project, equipe_id)
                if not self.is_member(team):
                    raise PermissionDenied("Seul un membre actuel de cette équipe peut remettre un livrable.")
                # Authorization precedes multipart parsing, file validation, hashing and storage.
                values = self.command(DeliveryCommand, project)
                milestone = self.milestone(project, values["jalon"])
                upload = values["fichier"]
                if any(unicodedata.category(char).startswith("C") for char in upload.name):
                    raise ValidationError({"fichier": "Le nom du fichier contient des caractères interdits."})
                name = get_valid_filename(upload.name.replace("\\", "_"))[:196]
                name = name.rsplit(".", 1)[0] + ".pdf"
                revision = (team.livrables.filter(jalon=milestone).aggregate(value=Max("revision"))["value"] or 0) + 1
                delivery = Delivery(
                    equipe=team,
                    jalon=milestone,
                    revision=revision,
                    fichier=upload,
                    nom=name,
                    taille=upload.size,
                    sha256=hash_uploaded_file(upload),
                    commentaire=values["commentaire"],
                    depose_par=request.user,
                )
                delivery.save()
                self.updated(project, "depot", equipe=str(team.pk), livrable=str(delivery.pk), revision=revision)
                result = self.result(project, "livrable", delivery, DeliverySerializer, status=201)
            committed = True
            return result
        finally:
            if delivery is not None and delivery.fichier._committed and not committed:
                delivery.fichier.storage.delete(delivery.fichier.name)

    @action(
        detail=True,
        methods=["get"],
        url_path=TEAM_PATH + r"/livrables/(?P<livrable_id>[0-9a-f-]{36})/telecharger",
    )
    @transaction.atomic
    def telecharger(self, request, pk=None, equipe_id=None, livrable_id=None):
        project = self.locked_project()
        team = self.team(project, equipe_id)
        delivery = get_object_or_404(team.livrables.filter(jalon__projet=project), pk=livrable_id)
        try:
            stream = delivery.fichier.open("rb")
        except FileNotFoundError:
            logger.error(
                "Missing project delivery", extra={"project_id": str(project.pk), "delivery_id": str(delivery.pk)}
            )
            raise NotFound("Le livrable est indisponible. Contactez le responsable du projet.")
        try:
            self.event(project, "telechargement", equipe=str(team.pk), livrable=str(delivery.pk))
        except Exception:
            stream.close()
            raise
        result = FileResponse(stream, as_attachment=True, filename=delivery.nom, content_type="application/pdf")
        result["Cache-Control"] = "private, no-store"
        result["X-Content-Type-Options"] = "nosniff"
        return result

    def active_memberships(self, team):
        return team.appartenances.filter(
            retired_at__isnull=True,
            membre__is_active=True,
            membre__etablissement_id=self.request.tenant.pk,
            membre__role__in=LEARNER_ROLES,
        )

    def check_scores(self, milestone, group_score, contributions):
        if group_score < 0 or group_score > milestone.bareme:
            raise ValidationError({"note_groupe": f"La note doit être comprise entre 0 et {milestone.bareme}."})
        if any(item["note"] < 0 or item["note"] > milestone.bareme for item in contributions):
            raise ValidationError({"contributions": f"Chaque note doit être comprise entre 0 et {milestone.bareme}."})

    @action(detail=True, methods=["get", "post"], url_path=TEAM_PATH + "/evaluations")
    @transaction.atomic
    def evaluations(self, request, pk=None, equipe_id=None):
        project = self.locked_project() if request.method == "POST" else self.get_object()
        team = self.team(project, equipe_id)
        if request.method == "GET":
            queryset = self.filter_milestone(team.evaluations.select_related("jalon"), project)
            privileged = self.privileged(project)
            if not privileged:
                queryset = queryset.filter(published_at__isnull=False)
            return self.collection(queryset, EvaluationSerializer, privileged=privileged)
        self.require_evaluator(project, team)
        values = self.command(EvaluationCommand, project)
        milestone = self.milestone(project, values.pop("jalon"))
        contributions = values.pop("contributions")
        self.check_scores(milestone, values["note_groupe"], contributions)
        memberships = {item.membre_id: item for item in self.active_memberships(team)}
        if not memberships:
            raise ValidationError({"equipe": "L'équipe ne compte aucun apprenant actif."})
        member_ids = [item["membre"] for item in contributions]
        if len(member_ids) != len(set(member_ids)) or any(member not in memberships for member in member_ids):
            raise ValidationError(
                {"contributions": "Chaque contribution doit désigner un membre actuel unique de l'équipe."}
            )
        revision = (team.evaluations.filter(jalon=milestone).aggregate(value=Max("revision"))["value"] or 0) + 1
        evaluation = Evaluation.objects.create(
            equipe=team, jalon=milestone, revision=revision, evalue_par=request.user, **values
        )
        Contribution.objects.bulk_create(
            [
                Contribution(
                    evaluation=evaluation,
                    appartenance=memberships[item["membre"]],
                    note=item["note"],
                    commentaire=item["commentaire"],
                )
                for item in contributions
            ]
        )
        self.updated(project, "evaluation", equipe=str(team.pk), evaluation=str(evaluation.pk), revision=revision)
        return self.result(project, "evaluation", evaluation, EvaluationSerializer, status=201)

    @action(
        detail=True,
        methods=["post"],
        url_path=TEAM_PATH + r"/evaluations/(?P<evaluation_id>[0-9a-f-]{36})/publier",
    )
    @transaction.atomic
    def publier(self, request, pk=None, equipe_id=None, evaluation_id=None):
        project = self.locked_project()
        team = self.team(project, equipe_id)
        self.require_evaluator(project, team)
        self.command(VersionCommand, project)
        evaluation = get_object_or_404(
            team.evaluations.filter(jalon__projet=project).select_related("jalon"), pk=evaluation_id
        )
        if evaluation.published_at:
            raise ValidationError({"evaluation": "Cette évaluation est déjà publiée et ne peut plus être modifiée."})
        if team.evaluations.filter(jalon=evaluation.jalon, revision__gt=evaluation.revision).exists():
            raise ValidationError({"evaluation": "Seule la dernière révision peut être publiée."})
        contributions = list(evaluation.contributions.select_related("appartenance"))
        memberships = set(self.active_memberships(team).values_list("pk", flat=True))
        if not memberships or memberships != {item.appartenance_id for item in contributions}:
            raise ValidationError(
                {"contributions": "Évaluez exactement les membres actuels dans un nouveau brouillon."}
            )
        self.check_scores(evaluation.jalon, evaluation.note_groupe, [{"note": item.note} for item in contributions])
        evaluation.publie_par = request.user
        evaluation.published_at = timezone.now()
        evaluation.save(update_fields=["publie_par", "published_at"])
        self.updated(project, "publication", equipe=str(team.pk), evaluation=str(evaluation.pk))
        return self.result(project, "evaluation", evaluation, EvaluationSerializer)

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        project = self.get_object()
        if not self.privileged(project):
            raise PermissionDenied("L'historique administratif est réservé aux agents habilités du projet.")
        rows = workflow_history_queryset(project)
        page = self.paginate_queryset(rows)
        data = [
            {
                "id": item.pk,
                "acteur": item.actor_id,
                "action": item.action,
                "created_at": item.created_at,
                "metadata": self.readable_evidence(item.metadata),
            }
            for item in (page if page is not None else rows)
        ]
        return self.get_paginated_response(data) if page is not None else Response(data)

    def readable_evidence(self, metadata):
        result = dict(metadata)
        if "competences" in result:
            result["competences"] = readable_competencies(self.request, result["competences"])
        if "competences" in result.get("avant", {}):
            result["avant"] = {
                **result["avant"],
                "competences": readable_competencies(self.request, result["avant"]["competences"]),
            }
        if "cours" in result:
            result["cours"] = readable_course_snapshot(self.request, result["cours"])
        if "cours" in result.get("avant", {}):
            result["avant"] = {
                **result["avant"],
                "cours": readable_course_snapshot(self.request, result["avant"]["cours"]),
            }
        return result
