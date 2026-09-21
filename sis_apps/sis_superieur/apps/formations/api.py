"""API views for formations (ViewSets DRF) - SIS Supérieur."""

from apps.core.serializers import WorkflowEventSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import has_business_permission_or_role
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

from .models import Formation, MaquetteFormation, Parcours
from .serializers import (
    FormationDetailSerializer,
    FormationListSerializer,
    MaquetteFormationSerializer,
    ParcoursSerializer,
)


def _formation_recipients(request, *profiles):
    recipients = [getattr(profile, "user", None) for profile in profiles if profile is not None]
    recipients = [recipient for recipient in recipients if recipient is not None]
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
        user = request.user
        return has_business_permission_or_role(
            user,
            "formations.change_formation",
            ("scolarite", "directeur_etudes", "responsable_formation", "doyen"),
        )


class FormationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour formations."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["type", "niveau", "departement", "regime", "actif"]
    search_fields = ["code", "nom", "description"]
    ordering_fields = ["code", "nom", "type", "created_at"]
    ordering = ["code"]

    def get_queryset(self):
        return Formation.objects.select_related("departement", "ecole_doctorale", "responsable")

    def get_serializer_class(self):
        if self.action == "list":
            return FormationListSerializer
        return FormationDetailSerializer

    def perform_create(self, serializer):
        formation = serializer.save()
        record_workflow_event(
            self.request,
            formation,
            "creation",
            "Formation créée",
            message=f"La formation {formation.nom} a été créée.",
            recipients=_formation_recipients(self.request, formation.responsable),
            metadata={"departement_id": formation.departement_id},
        )

    def perform_update(self, serializer):
        formation = serializer.save()
        record_workflow_event(
            self.request,
            formation,
            "mise_a_jour",
            "Formation mise à jour",
            message=f"La formation {formation.nom} a été mise à jour.",
            recipients=_formation_recipients(self.request, formation.responsable),
            metadata={"departement_id": formation.departement_id},
        )

    def perform_destroy(self, instance):
        record_workflow_event(
            self.request,
            instance,
            "suppression",
            "Formation supprimée",
            message=f"La formation {instance.nom} a été supprimée.",
            recipients=_formation_recipients(self.request, instance.responsable),
            metadata={"departement_id": instance.departement_id},
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def parcours(self, request, pk=None):
        """Liste les parcours de la formation."""
        formation = self.get_object()
        parcours = formation.parcours.all()
        serializer = ParcoursSerializer(parcours, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def maquettes(self, request, pk=None):
        """Liste les maquettes de la formation."""
        formation = self.get_object()
        maquettes = formation.maquettes.select_related("annee_universitaire")
        serializer = MaquetteFormationSerializer(maquettes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques de la formation."""
        formation = self.get_object()
        # Compter les étudiants inscrits via InscriptionAdministrative
        from apps.etudiants.models import InscriptionAdministrative

        nb_inscrits = InscriptionAdministrative.objects.filter(formation=formation, statut="validee").count()
        return Response(
            {
                "formation_id": formation.id,
                "nb_parcours": formation.parcours.count(),
                "nb_inscrits": nb_inscrits,
                "credits_total": formation.credits_total,
                "duree_annees": formation.duree_annees,
            }
        )

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow de la formation."""
        formation = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(formation), many=True)
        return Response(serializer.data)


class ParcoursViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour parcours."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = ParcoursSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["formation"]
    search_fields = ["code", "nom", "specialisation"]

    def get_queryset(self):
        return Parcours.objects.select_related("formation")

    def perform_create(self, serializer):
        parcours = serializer.save()
        record_workflow_event(
            self.request,
            parcours,
            "creation",
            "Parcours créé",
            message=f"Le parcours {parcours.nom} a été créé.",
            recipients=_formation_recipients(self.request, getattr(parcours.formation, "responsable", None)),
            metadata={"formation_id": parcours.formation_id},
        )

    def perform_update(self, serializer):
        parcours = serializer.save()
        record_workflow_event(
            self.request,
            parcours,
            "mise_a_jour",
            "Parcours mis à jour",
            message=f"Le parcours {parcours.nom} a été mis à jour.",
            recipients=_formation_recipients(self.request, getattr(parcours.formation, "responsable", None)),
            metadata={"formation_id": parcours.formation_id},
        )

    def perform_destroy(self, instance):
        record_workflow_event(
            self.request,
            instance,
            "suppression",
            "Parcours supprimé",
            message=f"Le parcours {instance.nom} a été supprimé.",
            recipients=_formation_recipients(self.request, getattr(instance.formation, "responsable", None)),
            metadata={"formation_id": instance.formation_id},
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow du parcours."""
        parcours = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(parcours), many=True)
        return Response(serializer.data)


class MaquettesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour maquettes de formation."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = MaquetteFormationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["formation", "annee_universitaire", "statut"]

    def get_queryset(self):
        return MaquetteFormation.objects.select_related("formation", "annee_universitaire")

    def perform_create(self, serializer):
        maquette = serializer.save()
        record_workflow_event(
            self.request,
            maquette,
            "creation",
            "Maquette créée",
            message=f"La maquette de {maquette.formation} a été créée.",
            recipients=_formation_recipients(self.request, getattr(maquette.formation, "responsable", None)),
            metadata={"formation_id": maquette.formation_id, "annee_universitaire_id": maquette.annee_universitaire_id},
        )

    def perform_update(self, serializer):
        maquette = serializer.save()
        record_workflow_event(
            self.request,
            maquette,
            "mise_a_jour",
            "Maquette mise à jour",
            message=f"La maquette de {maquette.formation} a été mise à jour.",
            recipients=_formation_recipients(self.request, getattr(maquette.formation, "responsable", None)),
            metadata={"formation_id": maquette.formation_id, "annee_universitaire_id": maquette.annee_universitaire_id},
        )

    def perform_destroy(self, instance):
        record_workflow_event(
            self.request,
            instance,
            "suppression",
            "Maquette supprimée",
            message=f"La maquette de {instance.formation} a été supprimée.",
            recipients=_formation_recipients(self.request, getattr(instance.formation, "responsable", None)),
            metadata={"formation_id": instance.formation_id, "annee_universitaire_id": instance.annee_universitaire_id},
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow de la maquette."""
        maquette = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(maquette), many=True)
        return Response(serializer.data)
