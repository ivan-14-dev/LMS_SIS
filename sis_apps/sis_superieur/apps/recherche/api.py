"""Versioned, transactional university research commands."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Max, Q, Sum, Value
from django.db.models.functions import Concat
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from sis_common.exam_files import hash_uploaded_file
from sis_common.pagination import SISPagination
from sis_common.workflow_tracking import record_workflow_event

from . import access
from .files import cleanup_new_file, original_filename, private_response
from .finance_api import ResearchFinanceMixin
from .models import Laboratoire, ProductionScientifique, ProjetRecherche, ResearchDelivery, These
from .serializers import (
    AcceptMilestoneCommand,
    DefendCommand,
    DeliveryCommand,
    LaboratoireDetailSerializer,
    LaboratoireListSerializer,
    MilestoneCommand,
    ProductionScientifiqueSerializer,
    ProjetRechercheDetailSerializer,
    ProjetRechercheListSerializer,
    ResearchMilestoneSerializer,
    TheseDetailSerializer,
    TheseListSerializer,
    VersionCommand,
    selectable_related,
)


def audit(request, instance, command):
    metadata = {"version": instance.version}
    if isinstance(instance, (ProductionScientifique, These)) and instance.projet_id:
        metadata.update(projet_id=instance.projet_id, projet_version=instance.projet.version)
    record_workflow_event(
        request, instance, f"recherche_{command}", "Suivi de recherche",
        metadata=metadata,
    )


def advance(instance):
    instance.version += 1
    instance.save(update_fields=["version"])


def require_manager(request, instance):
    if isinstance(instance, Laboratoire):
        granted = access.allowed(request, access.MANAGE, laboratoire=instance)
        archived = instance.archive
    elif isinstance(instance, ProjetRecherche):
        granted = access.allowed(request, access.MANAGE, projet=instance)
        archived = instance.archive or instance.laboratoire.archive
    else:
        granted = access.allowed(
            request, access.MANAGE, projet=instance.projet, laboratoire=instance.laboratoire,
        )
        archived = (
            instance.archive or instance.laboratoire.archive
            or (instance.projet is not None and instance.projet.archive)
        )
    if not granted:
        raise PermissionDenied("Une permission explicite de gestion dans ce périmètre est requise.")
    if archived:
        raise ValidationError("Un dossier archivé ne peut pas être modifié.")


class ResearchViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [access.ResearchAccess]
    pagination_class = SISPagination
    http_method_names = ["get", "post", "patch", "head", "options"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    def collection(self, queryset, serializer_class):
        page = self.paginate_queryset(queryset)
        serializer = serializer_class(
            page if page is not None else queryset, many=True, context=self.get_serializer_context(),
        )
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    def command(self, instance, serializer_class=VersionCommand):
        serializer = serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        access.check_version(instance, data.pop("version"))
        return data

    def representation(self, instance, status=200):
        instance.refresh_from_db()
        return Response(self.get_serializer(instance).data, status=status)

    def lock_object(self):
        selected = self.get_object()
        # Child commands take the same project lock as financial/lifecycle commands.
        if isinstance(selected, (ProductionScientifique, These)) and selected.projet_id:
            project = get_object_or_404(ProjetRecherche.objects.select_for_update(), pk=selected.projet_id)
        else:
            project = None
        instance = get_object_or_404(type(selected).objects.select_for_update(), pk=selected.pk)
        # Visibility queries contain DISTINCT; PostgreSQL cannot lock those queries.
        get_object_or_404(self.get_queryset(), pk=instance.pk)
        if project is not None:
            instance.projet = project
        require_manager(self.request, instance)
        return instance

    def save_metadata(self, serializer):
        upload = serializer.validated_data.get("fichier")
        written = None
        if upload:
            written = ProductionScientifique().fichier
        try:
            if written is not None:
                written.save(original_filename(upload), upload, save=False)
                instance = serializer.save(fichier=written.name)
            else:
                instance = serializer.save()
            return instance, written
        except Exception:
            cleanup_new_file(written)
            raise

    def create(self, request, *args, **kwargs):
        written = None
        try:
            with transaction.atomic():
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                values = serializer.validated_data
                project = values.get("projet")
                lab = values.get("laboratoire")
                if project:
                    project = get_object_or_404(ProjetRecherche.objects.select_for_update(), pk=project.pk)
                    require_manager(request, project)
                    values["projet"] = project
                elif lab:
                    lab = get_object_or_404(Laboratoire.objects.select_for_update(), pk=lab.pk)
                    require_manager(request, lab)
                    values["laboratoire"] = lab
                elif not access.allowed(request, access.MANAGE):
                    raise PermissionDenied("Création non autorisée.")
                # Revalidate related objects and memberships after waiting for the lock.
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                instance, written = self.save_metadata(serializer)
                if project:
                    advance(project)
                    instance.projet = project
                audit(request, instance, "creation")
                response = self.representation(instance, status=201)
            return response
        except Exception:
            cleanup_new_file(written)
            raise

    def partial_update(self, request, *args, **kwargs):
        written = None
        try:
            with transaction.atomic():
                instance = self.lock_object()
                serializer = self.get_serializer(instance, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                access.check_version(instance, serializer.validated_data["version"])
                if isinstance(instance, ProjetRecherche) and "budget" in serializer.validated_data:
                    from .finance import validate_budget_floor

                    validate_budget_floor(instance, serializer.validated_data["budget"])
                instance, written = self.save_metadata(serializer)
                advance(instance)
                if isinstance(instance, (ProductionScientifique, These)) and instance.projet_id:
                    advance(instance.projet)
                audit(request, instance, "modification")
                response = self.representation(instance)
            return response
        except Exception:
            cleanup_new_file(written)
            raise


class LaboratoiresViewSet(ResearchViewSet):
    filterset_fields = ["faculte", "type", "directeur"]
    search_fields = ["nom", "acronyme"]
    ordering = ["nom", "pk"]

    def get_queryset(self):
        return access.visible_laboratories(self.request).select_related("faculte", "directeur__user")

    def get_serializer_class(self):
        return LaboratoireListSerializer if self.action == "list" else LaboratoireDetailSerializer

    @action(detail=True, methods=["post"])
    def archiver(self, request, pk=None):
        with transaction.atomic():
            lab = self.lock_object()
            self.command(lab)
            if lab.projets.filter(archive=False).exists():
                raise ValidationError("Tous les projets du laboratoire doivent être archivés.")
            lab.archive = True
            lab.save(update_fields=["archive"])
            advance(lab)
            audit(request, lab, "archivage")
            return self.representation(lab)

    @action(detail=True, methods=["get"])
    def projets(self, request, pk=None):
        lab = self.get_object()
        return self.collection(
            access.visible_projects(request).filter(laboratoire=lab).order_by("-date_debut", "pk"),
            ProjetRechercheListSerializer,
        )

    @action(detail=True, methods=["get"])
    def theses(self, request, pk=None):
        lab = self.get_object()
        return self.collection(
            access.visible_theses(request).filter(laboratoire=lab).order_by("-date_debut", "pk"),
            TheseListSerializer,
        )

    @action(detail=True, methods=["get"])
    def productions(self, request, pk=None):
        lab = self.get_object()
        return self.collection(
            access.visible_productions(request).filter(laboratoire=lab).order_by("-annee", "pk"),
            ProductionScientifiqueSerializer,
        )

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        lab = self.get_object()
        projects = access.visible_projects(request).filter(laboratoire=lab)
        theses = access.visible_theses(request).filter(laboratoire=lab)
        productions = access.visible_productions(request).filter(laboratoire=lab)
        return Response({
            "nb_projets": projects.count(), "nb_projets_en_cours": projects.filter(statut="en_cours").count(),
            "nb_theses": theses.count(), "nb_theses_en_cours": theses.filter(statut="en_cours").count(),
            "nb_publications": productions.count(),
            "budget_total": str(projects.aggregate(total=Sum("budget"))["total"] or Decimal("0.00")),
        })

    @action(detail=False, methods=["get"])
    def selecteurs(self, request):
        kind = request.query_params.get("type")
        term = request.query_params.get("q", "").strip()
        if kind not in ("enseignants", "etudiants", "facultes") or len(term) > 200:
            raise ValidationError("Type de sélecteur ou recherche invalide.")
        user = access.current_research_user(request)
        constraints = access.constraints_for(user, access.MANAGE) if user else None
        if constraints is None:
            raise PermissionDenied("Une permission explicite de gestion est requise.")
        labs = access.managed_laboratories(request)
        projects = access.scoped_projects(request, user, access.MANAGE)
        unrestricted = access.allowed(request, access.MANAGE)
        if not unrestricted and not labs.exists() and not projects.exists():
            raise PermissionDenied("Aucun périmètre de gestion autorisé.")
        queryset = selectable_related(request, kind)
        if kind in ("enseignants", "etudiants"):
            queryset = queryset.alias(
                selector_full_name=Concat("user__first_name", Value(" "), "user__last_name"),
            )
            search = Q(selector_full_name__icontains=term) | Q(user__username__icontains=term)
            if kind == "etudiants":
                search |= Q(matricule__icontains=term)
            queryset = queryset.filter(search).select_related("user").distinct().order_by("user__last_name", "pk")
        else:
            queryset = queryset.filter(nom__icontains=term).distinct().order_by("nom", "pk")
        page = self.paginate_queryset(queryset)
        rows = [
            {"id": obj.pk, "nom": obj.nom if kind == "facultes" else (obj.user.get_full_name() or obj.user.username)}
            for obj in (page if page is not None else queryset)
        ]
        return self.get_paginated_response(rows) if page is not None else Response(rows)


class ProjectSearchFilter(SearchFilter):
    def filter_queryset(self, request, queryset, view):
        academic = queryset.filter(pk__in=access.academic_projects(request).values("pk"))
        academic = super().filter_queryset(request, academic, view)
        # Finance access must not permit searching an otherwise hidden description or team.
        financial = queryset.exclude(pk__in=access.academic_projects(request).values("pk"))
        for term in self.get_search_terms(request):
            financial = financial.filter(Q(titre__icontains=term) | Q(acronyme__icontains=term))
        return (academic | financial).distinct()


class ProjetsRechercheViewSet(ResearchFinanceMixin, ResearchViewSet):
    filter_backends = [DjangoFilterBackend, ProjectSearchFilter, OrderingFilter]
    filterset_fields = ["laboratoire", "responsable", "statut", "financeur"]
    search_fields = ["titre", "acronyme", "description"]
    ordering = ["-date_debut", "pk"]
    ordering_fields = ["date_debut", "date_fin", "titre", "statut", "budget", "id"]

    def get_queryset(self):
        queryset = access.visible_projects(self.request)
        if self.request.query_params.get("responsable"):
            queryset = queryset.filter(pk__in=access.academic_projects(self.request).values("pk"))
        return queryset.select_related(
            "laboratoire", "responsable__user",
        ).prefetch_related("membres__user")

    def get_serializer_class(self):
        return ProjetRechercheListSerializer if self.action == "list" else ProjetRechercheDetailSerializer

    def project_response(self, project):
        project.refresh_from_db()
        return Response(ProjetRechercheDetailSerializer(project, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"])
    def capacites(self, request):
        user = access.current_research_user(request)
        labs = access.managed_laboratories(request).filter(archive=False)
        projects = access.visible_projects(request)
        return Response({
            "can_create_laboratoire": access.allowed(request, access.MANAGE),
            "can_create_projet": access.allowed(request, access.MANAGE) or labs.exists(),
            "can_manage": access.allowed(request, access.MANAGE) or labs.exists() or (
                access.scoped_projects(request, user, access.MANAGE).filter(archive=False).exists()
            ),
            "can_contribute": any(
                access.can_contribute(request, project)
                for project in projects.filter(statut="en_cours", archive=False, laboratoire__archive=False)
            ),
            "can_finance": access.allowed(request, access.FINANCE) or (
                access.scoped_projects(request, user, access.FINANCE).exists()
            ),
        })

    def transition(self, command, sources, target=None):
        with transaction.atomic():
            project = self.lock_object()
            self.command(project)
            if project.statut not in sources:
                raise ValidationError("Transition impossible depuis l'état actuel du projet.")
            if command in ("terminer", "archiver"):
                from .finance import project_has_open_commitments

                if command == "terminer" and project.jalons.exclude(statut="accepte").exists():
                    raise ValidationError("Tous les jalons doivent être acceptés.")
                if project_has_open_commitments(project):
                    raise ValidationError("Des engagements financiers restent ouverts.")
            if command == "archiver":
                project.archive = True
                project.save(update_fields=["archive"])
            else:
                project.statut = target
                project.save(update_fields=["statut"])
            advance(project)
            audit(self.request, project, command)
            return self.project_response(project)

    @action(detail=True, methods=["post"])
    def accepter(self, request, pk=None):
        return self.transition("accepter", ("propose",), "accepte")

    @action(detail=True, methods=["post"])
    def demarrer(self, request, pk=None):
        return self.transition("demarrer", ("accepte",), "en_cours")

    @action(detail=True, methods=["post"])
    def suspendre(self, request, pk=None):
        return self.transition("suspendre", ("en_cours",), "suspendu")

    @action(detail=True, methods=["post"])
    def reprendre(self, request, pk=None):
        return self.transition("reprendre", ("suspendu",), "en_cours")

    @action(detail=True, methods=["post"])
    def terminer(self, request, pk=None):
        return self.transition("terminer", ("en_cours",), "termine")

    @action(detail=True, methods=["post"])
    def archiver(self, request, pk=None):
        return self.transition("archiver", ("termine",))

    @action(detail=True, methods=["get", "post"])
    def jalons(self, request, pk=None):
        if request.method == "GET":
            project = self.get_object()
            if not access.can_read_academic(request, project):
                raise PermissionDenied("Accès académique requis.")
            return self.collection(project.jalons.prefetch_related("livrables"), ResearchMilestoneSerializer)
        with transaction.atomic():
            project = self.lock_object()
            data = self.command(project, MilestoneCommand)
            if project.statut not in ("propose", "accepte", "en_cours"):
                raise ValidationError("Les jalons ne peuvent pas être ajoutés dans cet état.")
            if not project.date_debut <= data["echeance"] <= project.date_fin:
                raise ValidationError({"echeance": "L'échéance doit être dans la période du projet."})
            project.jalons.create(**data)
            advance(project)
            audit(request, project, "jalon_creation")
            return self.project_response(project)

    @action(detail=True, methods=["post"])
    def livrables(self, request, pk=None):
        delivery = None
        try:
            with transaction.atomic():
                self.get_object()
                project = get_object_or_404(ProjetRecherche.objects.select_for_update(), pk=pk)
                if not access.can_contribute(request, project):
                    raise PermissionDenied("Une contribution explicitement autorisée est requise.")
                data = self.command(project, DeliveryCommand)
                if project.archive or project.laboratoire.archive or project.statut != "en_cours":
                    raise ValidationError("Un projet en cours non archivé est requis.")
                milestone = get_object_or_404(project.jalons, pk=data.pop("jalon"))
                if milestone.statut == "accepte":
                    raise ValidationError("Un jalon accepté ne peut plus recevoir de livrable.")
                upload = data.pop("fichier")
                revision = (milestone.livrables.aggregate(value=Max("revision"))["value"] or 0) + 1
                actor = access.current_research_user(request)
                if actor is None:
                    raise PermissionDenied("Le compte n'est plus autorisé.")
                delivery = ResearchDelivery(
                    jalon=milestone, revision=revision, fichier=upload, nom=original_filename(upload),
                    taille=upload.size, sha256=hash_uploaded_file(upload),
                    actor=actor, **data,
                )
                delivery.save()
                milestone.statut = "soumis"
                milestone.save(update_fields=["statut"])
                advance(project)
                audit(request, project, "livrable_depot")
                response = self.project_response(project)
            return response
        except Exception:
            if delivery is not None:
                cleanup_new_file(delivery.fichier)
            raise

    @action(detail=True, methods=["get"], url_path=r"livrables/(?P<livrable_id>[0-9]+)/fichier")
    def livrable_fichier(self, request, pk=None, livrable_id=None):
        project = self.get_object()
        if not access.can_read_academic(request, project):
            raise PermissionDenied("Accès académique requis.")
        delivery = get_object_or_404(ResearchDelivery.objects.filter(jalon__projet=project), pk=livrable_id)
        return private_response(delivery.fichier, filename=delivery.nom, delivery=True)

    @action(detail=True, methods=["post"], url_path="valider-jalon")
    def valider_jalon(self, request, pk=None):
        with transaction.atomic():
            project = self.lock_object()
            data = self.command(project, AcceptMilestoneCommand)
            milestone = get_object_or_404(project.jalons, pk=data["jalon"])
            if project.statut != "en_cours" or milestone.statut != "soumis" or not milestone.livrables.exists():
                raise ValidationError("Un projet en cours et un jalon soumis sont requis.")
            milestone.statut = "accepte"
            milestone.save(update_fields=["statut"])
            advance(project)
            audit(request, project, "jalon_acceptation")
            return self.project_response(project)


class ProductionsScientifiquesViewSet(ResearchViewSet):
    serializer_class = ProductionScientifiqueSerializer
    filterset_fields = ["laboratoire", "projet", "type", "annee", "statut"]
    search_fields = ["titre", "doi"]
    ordering = ["-annee", "-created_at", "pk"]

    def get_queryset(self):
        return access.visible_productions(self.request).select_related(
            "laboratoire", "projet",
        ).prefetch_related("auteurs__user")

    @action(detail=False, methods=["get"])
    def par_annee(self, request):
        return Response(list(
            self.filter_queryset(self.get_queryset()).values("annee").annotate(count=Count("id")).order_by("-annee"),
        ))

    @action(detail=True, methods=["get"])
    def fichier(self, request, pk=None):
        return private_response(self.get_object().fichier)

    def transition(self, command, source, target=None):
        with transaction.atomic():
            production = self.lock_object()
            self.command(production)
            if production.statut != source:
                raise ValidationError("Transition impossible depuis l'état actuel de la production.")
            if production.projet is None and command != "archiver":
                raise ValidationError("Une publication validée doit être liée à un projet.")
            if command != "archiver":
                project = production.projet
                researchers = {project.responsable_id, *project.membres.values_list("pk", flat=True)}
                authors = production.auteurs.all()
                if not authors.exists() or authors.exclude(
                    pk__in=researchers, user__is_active=True, user__etablissement_id=self.request.tenant.pk,
                ).exists():
                    raise ValidationError("Les auteurs doivent être des chercheurs locaux actifs du projet.")
            if command == "archiver":
                production.archive = True
                production.save(update_fields=["archive"])
            else:
                production.statut = target
                production.save(update_fields=["statut"])
            advance(production)
            if production.projet_id:
                advance(production.projet)
            audit(self.request, production, command)
            return self.representation(production)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        return self.transition("valider", "brouillon", "validee")

    @action(detail=True, methods=["post"])
    def publier(self, request, pk=None):
        return self.transition("publier", "validee", "publiee")

    @action(detail=True, methods=["post"])
    def archiver(self, request, pk=None):
        return self.transition("archiver", "publiee")


class ThesesViewSet(ResearchViewSet):
    filterset_fields = ["laboratoire", "projet", "directeur", "statut", "financement"]
    search_fields = ["titre", "doctorant__user__last_name", "mots_cles"]
    ordering = ["-date_debut", "pk"]

    def get_queryset(self):
        return access.visible_theses(self.request).select_related(
            "laboratoire", "projet", "doctorant__user", "directeur__user", "co_directeur__user",
        )

    def get_serializer_class(self):
        return TheseListSerializer if self.action == "list" else TheseDetailSerializer

    def transition(self, command, sources, target=None):
        with transaction.atomic():
            thesis = self.lock_object()
            data = self.command(thesis, DefendCommand if command == "soutenir" else VersionCommand)
            if thesis.statut not in sources:
                raise ValidationError("Transition impossible depuis l'état actuel de la thèse.")
            if command == "soutenir":
                defense = data["date_soutenance"]
                if defense < thesis.date_debut or defense > timezone.localdate() or (
                    thesis.projet and defense > thesis.projet.date_fin
                ):
                    raise ValidationError({"date_soutenance": "Date hors période ou future."})
                thesis.date_soutenance = defense
                thesis.save(update_fields=["date_soutenance"])
            if command == "archiver":
                thesis.archive = True
                thesis.save(update_fields=["archive"])
            else:
                thesis.statut = target
                thesis.save(update_fields=["statut"])
            advance(thesis)
            if thesis.projet_id:
                advance(thesis.projet)
            audit(self.request, thesis, command)
            return self.representation(thesis)

    @action(detail=True, methods=["post"])
    def soutenir(self, request, pk=None):
        return self.transition("soutenir", ("en_cours",), "soutenue")

    @action(detail=True, methods=["post"])
    def suspendre(self, request, pk=None):
        return self.transition("suspendre", ("en_cours",), "suspendue")

    @action(detail=True, methods=["post"])
    def reprendre(self, request, pk=None):
        return self.transition("reprendre", ("suspendue",), "en_cours")

    @action(detail=True, methods=["post"])
    def abandonner(self, request, pk=None):
        return self.transition("abandonner", ("en_cours", "suspendue"), "abandonnee")

    @action(detail=True, methods=["post"])
    def archiver(self, request, pk=None):
        return self.transition("archiver", ("soutenue", "abandonnee"))
