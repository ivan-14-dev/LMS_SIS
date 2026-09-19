"""API views for releves (ViewSets DRF) - SIS Supérieur."""

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Attestation, ReleveNotes, Transcript
from .serializers import (
    AttestationSerializer,
    ReleveNotesDetailSerializer,
    ReleveNotesListSerializer,
    TranscriptDetailSerializer,
    TranscriptListSerializer,
)


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "scolarite",
            "directeur_etudes",
            "doyen",
        )


class RelevesNotesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour relevés de notes."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["etudiant", "semestre", "signe", "mention"]
    search_fields = ["etudiant__matricule", "etudiant__user__last_name", "numero_serie"]
    ordering = ["-date_emission"]

    def get_queryset(self):
        return ReleveNotes.objects.select_related(
            "etudiant__user", "semestre", "signe_par"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ReleveNotesListSerializer
        return ReleveNotesDetailSerializer

    @action(detail=True, methods=["post"])
    def signer(self, request, pk=None):
        """Signe le relevé de notes."""
        releve = self.get_object()
        if releve.signe:
            return Response({"error": "Déjà signé."}, status=400)
        releve.signe = True
        releve.date_signature = timezone.now()
        releve.signe_par = request.user
        releve.save(update_fields=["signe", "date_signature", "signe_par"])
        return Response({"detail": "Relevé signé.", "id": releve.id})

    @action(detail=False, methods=["get"])
    def mes_releves(self, request):
        """Relevés de l'étudiant connecté."""
        etudiant = getattr(request.user, "etudiant", None)
        if not etudiant:
            return Response({"error": "Vous n'êtes pas étudiant."}, status=403)
        releves = self.get_queryset().filter(etudiant=etudiant)
        serializer = ReleveNotesListSerializer(releves, many=True)
        return Response(serializer.data)


class TranscriptsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour transcripts."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["etudiant", "diplome_prepare"]
    ordering = ["-date_emission"]

    def get_queryset(self):
        return Transcript.objects.select_related(
            "etudiant__user", "signe_par"
        ).prefetch_related("annees")

    def get_serializer_class(self):
        if self.action == "list":
            return TranscriptListSerializer
        return TranscriptDetailSerializer

    @action(detail=False, methods=["get"])
    def mes_transcripts(self, request):
        """Transcripts de l'étudiant connecté."""
        etudiant = getattr(request.user, "etudiant", None)
        if not etudiant:
            return Response({"error": "Vous n'êtes pas étudiant."}, status=403)
        transcripts = self.get_queryset().filter(etudiant=etudiant)
        serializer = TranscriptListSerializer(transcripts, many=True)
        return Response(serializer.data)


class AttestationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour attestations."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = AttestationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["etudiant", "type"]
    ordering = ["-date_emission"]

    def get_queryset(self):
        return Attestation.objects.select_related("etudiant__user", "signe_par")

    @action(detail=False, methods=["get"])
    def mes_attestations(self, request):
        """Attestations de l'étudiant connecté."""
        etudiant = getattr(request.user, "etudiant", None)
        if not etudiant:
            return Response({"error": "Vous n'êtes pas étudiant."}, status=403)
        attestations = self.get_queryset().filter(etudiant=etudiant)
        AttestationSerializer(attestations, many=True)
        return Response(attestations.data)
