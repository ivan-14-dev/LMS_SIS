"""API views for etudiants (ViewSets DRF) - SIS Supérieur."""

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.core.serializers import WorkflowEventSerializer
from sis_common.authorization import request_has_business_access
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

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
        return request_has_business_access(
            request,
            "etudiants.change_etudiant",
            ("scolarite", "directeur_etudes", "responsable_formation", "doyen"),
            tenant_group_codes=("student_manager_superieur",),
        )


class EtudiantsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour étudiants."""

    permission_classes = [IsScolariteOrReadOnly]
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
        qs = Etudiant.objects.select_related(
            "user", "universite", "annee_universitaire_actuelle"
        )

        # Filtrer par université du tenant
        request = self.request
        if hasattr(request, "tenant"):
            qs = qs.filter(universite=request.tenant)

        # Un étudiant ne voit que son propre profil
        user = request.user
        if hasattr(user, "etudiant_profile"):
            if not user.is_staff and getattr(user, "role", "") == "etudiant":
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
                {
                    "error": f"Statut invalide. Valeurs possibles: {list(dict(Etudiant.STATUT_CHOICES).keys())}"
                },
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
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
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
        affectation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InscriptionsAdminViewSet(viewsets.ModelViewSet):
    """ViewSet pour les inscriptions administratives."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = InscriptionAdministrativeSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["statut", "annee_universitaire", "formation", "regime"]
    ordering = ["-annee_universitaire__date_debut", "-date_inscription"]

    def get_queryset(self):
        return InscriptionAdministrative.objects.select_related(
            "etudiant__user", "annee_universitaire", "formation", "parcours"
        )

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        """Valide une inscription administrative."""
        inscription = self.get_object()
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
    def refuser(self, request, pk=None):
        """Refuse une inscription administrative."""
        inscription = self.get_object()
        motif = request.data.get("motif", "")
        if not motif:
            return Response(
                {"error": "Le motif de refus est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        inscription.statut = "refusee"
        inscription.motif_refus = motif
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
