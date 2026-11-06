"""API views for etudiants (ViewSets DRF) - SIS Supérieur."""

from apps.core.serializers import WorkflowEventSerializer
from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.academic_lifecycle import AcademicLifecycleMixin, ensure_academic_open
from sis_common.admissions import AdmissionTenantAccess, ReenrollmentMixin, scoped_admissions
from sis_common.authorization import request_has_business_access
from sis_common.learner_import import LearnerImportMixin
from sis_common.workflow_tracking import (
    record_workflow_event,
    workflow_history_queryset,
)

from .models import AffectationECUEIndividuelle, Etudiant, InscriptionAdministrative
from .serializers import (
    AffectationECUEIndividuelleSerializer,
    EtudiantCreateSerializer,
    EtudiantDetailSerializer,
    EtudiantListSerializer,
    InscriptionAdministrativeSerializer,
)


def _inscription_notification_recipients(request, inscription):
    recipients = []
    user = getattr(inscription.etudiant, "user", None)
    if user is not None:
        recipients.append(user)
    actor = getattr(request, "user", None)
    if getattr(actor, "is_authenticated", False) and actor not in recipients:
        recipients.append(actor)
    return recipients


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        permission = getattr(view, "required_change_permission", "etudiants.change_etudiant")
        if hasattr(view, "required_change_permission") and request.user.has_perm(permission):
            return True
        return request_has_business_access(
            request,
            permission,
            ("scolarite", "directeur_etudes", "responsable_formation", "doyen"),
            tenant_group_codes=("student_manager_superieur",),
        )


class EtudiantsViewSet(LearnerImportMixin, AcademicLifecycleMixin, viewsets.ModelViewSet):
    """ViewSet CRUD pour étudiants."""

    permission_classes = [IsScolariteOrReadOnly]
    learner_model = Etudiant
    learner_create_serializer = EtudiantCreateSerializer
    import_extra_columns = ("matricule", "telephone")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "statut",
        "regime",
        "boursier",
        "sexe",
        "annee_universitaire_actuelle",
    ]
    search_fields = [
        "matricule",
        "ine",
        "user__first_name",
        "user__last_name",
        "user__email",
    ]
    ordering_fields = ["matricule", "user__last_name", "date_naissance", "created_at"]
    ordering = ["user__last_name", "user__first_name"]

    def get_queryset(self):
        """Retourne les étudiants de l'établissement courant."""
        qs = Etudiant.objects.select_related("user", "universite", "annee_universitaire_actuelle")

        # Filtrer par université du tenant
        request = self.request
        if hasattr(request, "tenant"):
            qs = qs.filter(universite=request.tenant)

        user = request.user
        if not getattr(user, "is_superuser", False) and (
            user.role in ("etudiant", "doctorant", "parent")
            or not (
                user.has_perm("etudiants.view_etudiant")
                or request_has_business_access(
                    request,
                    "etudiants.view_etudiant",
                    ("scolarite", "directeur_etudes", "responsable_formation", "doyen"),
                    tenant_group_codes=("student_manager_superieur",),
                )
            )
        ):
            qs = qs.filter(user=user)

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return EtudiantListSerializer
        elif self.action == "create":
            return EtudiantCreateSerializer
        return EtudiantDetailSerializer

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Recherche avancée d'étudiants."""
        q = request.query_params.get("q", "")
        qs = self.get_queryset()

        if q:
            qs = qs.filter(
                Q(matricule__icontains=q)
                | Q(ine__icontains=q)
                | Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
                | Q(user__email__icontains=q)
            )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = EtudiantListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = EtudiantListSerializer(qs[:50], many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def inscriptions(self, request, pk=None):
        """Liste les inscriptions administratives d'un étudiant."""
        etudiant = self.get_object()
        inscriptions = etudiant.inscriptions_admin.select_related(
            "annee_universitaire", "formation", "parcours"
        ).order_by("-annee_universitaire__date_debut")
        serializer = InscriptionAdministrativeSerializer(inscriptions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def changer_statut(self, request, pk=None):
        """Change le statut d'un étudiant."""
        etudiant = self.get_object()
        nouveau_statut = request.data.get("statut")

        if nouveau_statut not in dict(Etudiant.STATUT_CHOICES):
            return Response(
                {"error": f"Statut invalide. Valeurs possibles: {list(dict(Etudiant.STATUT_CHOICES).keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ancien_statut = etudiant.statut
        etudiant.statut = nouveau_statut
        etudiant.save(update_fields=["statut", "updated_at"])

        return Response(
            {
                "id": etudiant.id,
                "ancien_statut": ancien_statut,
                "nouveau_statut": nouveau_statut,
                "detail": f"Statut modifié de '{ancien_statut}' à '{nouveau_statut}'.",
            }
        )

    @action(detail=True, methods=["get", "post"])
    @transaction.atomic
    def matieres_individuelles(self, request, pk=None):
        """Liste ou crée des ECUE individualisés pour un étudiant."""
        etudiant = self.get_object()
        if request.method == "GET":
            affectations = AffectationECUEIndividuelle.objects.filter(
                inscription_admin__etudiant=etudiant
            ).select_related(
                "inscription_admin__annee_universitaire",
                "semestre_cible__annee_universitaire",
                "ecue__ue__semestre",
            )
            serializer = AffectationECUEIndividuelleSerializer(affectations, many=True)
            return Response(serializer.data)

        serializer = AffectationECUEIndividuelleSerializer(
            data=request.data,
            context={"request": request, "etudiant": etudiant},
        )
        serializer.is_valid(raise_exception=True)
        ensure_academic_open(
            data=serializer.validated_data,
            paths=("inscription_admin.annee_universitaire", "semestre_cible.annee_universitaire", "semestre_cible"),
        )
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def retirer_matiere_individuelle(self, request, pk=None):
        """Retire une affectation ECUE individualisée d'un étudiant."""
        etudiant = self.get_object()
        affectation_id = request.data.get("affectation_id")
        affectation = AffectationECUEIndividuelle.objects.filter(
            id=affectation_id,
            inscription_admin__etudiant=etudiant,
        ).first()
        if affectation is None:
            return Response(
                {"error": "Affectation individuelle introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        ensure_academic_open(affectation, paths=("inscription_admin.annee_universitaire", "semestre_cible"))
        affectation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InscriptionsAdminViewSet(ReenrollmentMixin, AcademicLifecycleMixin, viewsets.ModelViewSet):
    """ViewSet pour les inscriptions administratives."""

    permission_classes = [AdmissionTenantAccess, IsScolariteOrReadOnly]
    required_change_permission = "etudiants.change_inscriptionadministrative"
    serializer_class = InscriptionAdministrativeSerializer
    academic_period_paths = ("annee_universitaire",)
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["statut", "annee_universitaire", "formation", "regime", "etudiant"]
    ordering = ["-annee_universitaire__date_debut", "-date_inscription"]

    def get_queryset(self):
        queryset = InscriptionAdministrative.objects.select_related(
            "etudiant__user", "annee_universitaire", "formation", "parcours"
        ).filter(etudiant__universite=self.request.tenant)
        user = self.request.user
        if user.role in ("etudiant", "doctorant", "parent") and not user.is_superuser:
            return queryset.filter(etudiant__user=user)
        if (
            user.has_perm("etudiants.view_inscriptionadministrative")
            or (
                self.request.method not in ("GET", "HEAD", "OPTIONS") and user.has_perm(self.required_change_permission)
            )
            or request_has_business_access(
                self.request,
                "etudiants.view_inscriptionadministrative",
                ("scolarite", "directeur_etudes", "responsable_formation", "doyen"),
                tenant_group_codes=("student_manager_superieur",),
            )
        ):
            return scoped_admissions(queryset, self.request)
        return queryset.filter(etudiant__user=self.request.user)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def transferer(self, request, pk=None):
        from apps.examens.models import ResultatExamen
        from apps.notes.models import Note

        inscription = self.get_object()
        ensure_academic_open(inscription, paths=self.academic_period_paths)
        motif = serializers.CharField(allow_blank=False, max_length=2000).run_validation(request.data.get("motif"))
        serializer = self.get_serializer(
            inscription,
            data={"formation": request.data.get("formation"), "parcours": request.data.get("parcours")},
            partial=True,
            context={**self.get_serializer_context(), "controlled_transfer": True},
        )
        serializer.is_valid(raise_exception=True)
        formation = serializer.validated_data["formation"]
        if inscription.statut != "validee":
            raise serializers.ValidationError({"detail": "Le transfert exige une inscription validée."})
        if formation.pk == inscription.formation_id and serializer.validated_data["parcours"] == inscription.parcours:
            raise serializers.ValidationError({"formation": "Sélectionnez une autre formation ou un autre parcours."})
        if (
            inscription.offre_configuration
            or formation.offre_configuration
            or inscription.inscriptions_peda.exists()
            or inscription.affectations_ecue_individuelles.exists()
            or inscription.etudiant.acquisitions_ects.filter(
                annee_universitaire=inscription.annee_universitaire
            ).exists()
            or Note.objects.filter(
                etudiant=inscription.etudiant, evaluation__semestre__annee_universitaire=inscription.annee_universitaire
            ).exists()
            or ResultatExamen.objects.filter(
                etudiant=inscription.etudiant,
                epreuve__session__semestre__annee_universitaire=inscription.annee_universitaire,
            ).exists()
        ):
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Ce dossier possède des règles, inscriptions pédagogiques ou acquis. "
                        "Un traitement des équivalences est requis."
                    )
                }
            )
        previous = {"formation_id": inscription.formation_id, "parcours_id": inscription.parcours_id}
        self.save_academic(serializer)
        record_workflow_event(
            request,
            inscription,
            "transfert",
            "Transfert de formation",
            message=motif,
            recipients=_inscription_notification_recipients(request, inscription),
            metadata={
                "avant": previous,
                "apres": {"formation_id": inscription.formation_id, "parcours_id": inscription.parcours_id},
            },
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def valider(self, request, pk=None):
        """Valide une inscription administrative."""
        inscription = self.get_object()
        ensure_academic_open(inscription, paths=self.academic_period_paths)
        if inscription.statut != "provisoire":
            return Response(
                {"error": "Seules les inscriptions provisoires peuvent être validées."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        inscription.statut = "validee"
        inscription.save(update_fields=["statut", "updated_at"])
        record_workflow_event(
            request,
            inscription,
            "validation",
            "Inscription validée",
            message=f"L'inscription administrative de {inscription.etudiant} a été validée.",
            recipients=_inscription_notification_recipients(request, inscription),
            metadata={
                "etudiant_id": inscription.etudiant_id,
                "formation_id": inscription.formation_id,
                "annee_universitaire_id": inscription.annee_universitaire_id,
            },
        )
        return Response({"detail": "Inscription validée.", "id": inscription.id})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def refuser(self, request, pk=None):
        """Refuse une inscription administrative."""
        inscription = self.get_object()
        ensure_academic_open(inscription, paths=self.academic_period_paths)
        if inscription.statut != "provisoire":
            return Response({"error": "Seule une inscription provisoire peut être refusée."}, status=400)
        motif = request.data.get("motif", "")
        if not isinstance(motif, str) or not motif.strip() or len(motif) > 2000:
            return Response(
                {"error": "Le motif de refus est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        inscription.statut = "refusee"
        inscription.motif_refus = motif.strip()
        inscription.save(update_fields=["statut", "motif_refus", "updated_at"])
        record_workflow_event(
            request,
            inscription,
            "refus",
            "Inscription refusée",
            message=f"L'inscription administrative de {inscription.etudiant} a été refusée.",
            recipients=_inscription_notification_recipients(request, inscription),
            metadata={
                "etudiant_id": inscription.etudiant_id,
                "formation_id": inscription.formation_id,
                "annee_universitaire_id": inscription.annee_universitaire_id,
                "motif_refus": motif,
            },
        )
        return Response({"detail": "Inscription refusée.", "id": inscription.id})

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow de l'inscription."""
        inscription = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(inscription), many=True)
        return Response(serializer.data)
