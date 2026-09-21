"""API views for releves (ViewSets DRF) - SIS Supérieur."""

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.core.serializers import WorkflowEventSerializer
from sis_common.document_policies import (
    enforce_financial_clearance,
    get_action_object,
)
from sis_common.official_documents import render_official_pdf, tenant_identity_rows
from sis_common.authorization import has_business_permission_or_role
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

from .models import Attestation, ReleveNotes, Transcript
from .serializers import (
    AttestationSerializer,
    ReleveNotesDetailSerializer,
    ReleveNotesListSerializer,
    TranscriptDetailSerializer,
    TranscriptListSerializer,
)


def _student_notification_recipients(request, etudiant):
    recipients = []
    user = getattr(etudiant, "user", None)
    if user is not None:
        recipients.append(user)
    actor = getattr(request, "user", None)
    if getattr(actor, "is_authenticated", False) and actor not in recipients:
        recipients.append(actor)
    return recipients


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        permission = getattr(view, "required_change_permission", "releves.change_relevenotes")
        return has_business_permission_or_role(
            request.user,
            permission,
            (
                "scolarite",
                "directeur_etudes",
                "doyen",
            ),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=("academic_registry_superieur", "document_signatory_superieur"),
        )


class RelevesNotesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour relevés de notes."""

    permission_classes = [IsScolariteOrReadOnly]
    required_change_permission = "releves.change_relevenotes"
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
    @enforce_financial_clearance(
        candidates_getter=lambda _view, request, releve: [
            {"scope": "semester", "context": {"semester_id": releve.semestre_id}},
            {"scope": "academic_year", "context": {"academic_year_id": releve.semestre.annee_universitaire_id}},
            {"scope": "tenant", "context": {"tenant_id": getattr(request.tenant, "id", None)}},
        ],
        subject_getter=lambda _view, _request, releve: releve.etudiant,
        academic_year_ids_getter=lambda _view, _request, releve: [releve.semestre.annee_universitaire_id],
        invoice_model_label="paiements.FactureFrais",
        invoice_subject_field="etudiant",
        invoice_year_lookup="type_frais__annee_universitaire_id",
        message="La signature du relevé exige une situation financière régularisée.",
    )
    def signer(self, request, pk=None):
        """Signe le relevé de notes."""
        releve = get_action_object(self)
        if releve.signe:
            return Response({"error": "Déjà signé."}, status=400)
        releve.signe = True
        releve.date_signature = timezone.now()
        releve.signe_par = request.user
        releve.save(update_fields=["signe", "date_signature", "signe_par"])
        record_workflow_event(
            request,
            releve,
            "signature",
            "Relevé signé",
            message=f"Le relevé {releve.numero_serie} de {releve.etudiant} a été signé.",
            recipients=_student_notification_recipients(request, releve.etudiant),
            metadata={"etudiant_id": releve.etudiant_id, "semestre_id": releve.semestre_id},
        )
        return Response({"detail": "Relevé signé.", "id": releve.id})

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow du relevé."""
        releve = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(releve), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def pdf_officiel(self, request, pk=None):
        """Génère le PDF officiel du relevé."""
        releve = self.get_object()
        serialized = ReleveNotesDetailSerializer(releve).data
        return render_official_pdf(
            f"releve-{releve.id}.pdf",
            f"Relevé de notes - {serialized.get('etudiant_nom')}",
            tenant_identity_rows(
                request,
                "Relevé de notes",
                serial=releve.numero_serie,
                issue_date=releve.date_emission,
            ),
            [
                {
                    "title": "Étudiant",
                    "rows": [
                        ("Étudiant", serialized.get("etudiant_nom")),
                        ("Matricule", serialized.get("etudiant_matricule")),
                        ("Semestre", serialized.get("semestre_nom")),
                    ],
                },
                {
                    "title": "Résultats",
                    "rows": [
                        ("Moyenne générale", serialized.get("moyenne_generale")),
                        ("Mention", serialized.get("mention")),
                        ("Crédits validés", serialized.get("credits_valides")),
                        ("Crédits totaux", serialized.get("credits_total")),
                        ("Classement", serialized.get("classement")),
                        ("Effectif", serialized.get("effectif")),
                    ],
                },
                {
                    "title": "ECUE individualisés",
                    "rows": [
                        (
                            item.get("ecue_nom"),
                            f"{item.get('ue_nom')} • {item.get('semestre_cible_libelle')}",
                        )
                        for item in serialized.get("matieres_individuelles", [])
                    ]
                    or [("Aucun", "Aucun ECUE individualisé pour ce semestre")],
                },
            ],
            footer_rows=[
                ("Signé", "Oui" if releve.signe else "Non"),
                ("Signé par", serialized.get("signe_par_nom")),
                ("QR vérification", serialized.get("qr_verification")),
            ],
        )

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
    required_change_permission = "releves.change_transcript"
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

    @action(detail=True, methods=["post"])
    @enforce_financial_clearance(
        candidates_getter=lambda _view, request, transcript: [
            {"scope": "academic_year", "context": {"academic_year_id": academic_year_id}}
            for academic_year_id in transcript.annees.values_list("id", flat=True)
        ] + [{"scope": "tenant", "context": {"tenant_id": getattr(request.tenant, "id", None)}}],
        subject_getter=lambda _view, _request, transcript: transcript.etudiant,
        academic_year_ids_getter=lambda _view, _request, transcript: list(
            transcript.annees.values_list("id", flat=True)
        ),
        invoice_model_label="paiements.FactureFrais",
        invoice_subject_field="etudiant",
        invoice_year_lookup="type_frais__annee_universitaire_id",
        message="La signature du transcript exige une situation financière régularisée.",
    )
    def signer(self, request, pk=None):
        """Signe le transcript officiel."""
        transcript = get_action_object(self)
        if transcript.signe_par_id:
            return Response({"error": "Déjà signé."}, status=400)
        transcript.signe_par = request.user
        transcript.save(update_fields=["signe_par"])
        record_workflow_event(
            request,
            transcript,
            "signature",
            "Transcript signé",
            message=f"Le transcript {transcript.numero_serie} de {transcript.etudiant} a été signé.",
            recipients=_student_notification_recipients(request, transcript.etudiant),
            metadata={"etudiant_id": transcript.etudiant_id},
        )
        return Response({"detail": "Transcript signé.", "id": transcript.id})

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow du transcript."""
        transcript = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(transcript), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def pdf_officiel(self, request, pk=None):
        """Génère le PDF officiel du transcript."""
        transcript = self.get_object()
        serialized = TranscriptDetailSerializer(transcript).data
        return render_official_pdf(
            f"transcript-{transcript.id}.pdf",
            f"Transcript - {serialized.get('etudiant_nom')}",
            tenant_identity_rows(
                request,
                "Transcript officiel",
                serial=transcript.numero_serie,
                issue_date=transcript.date_emission,
            ),
            [
                {
                    "title": "Étudiant",
                    "rows": [
                        ("Étudiant", serialized.get("etudiant_nom")),
                        ("Matricule", serialized.get("etudiant_matricule")),
                        ("Diplôme préparé", serialized.get("diplome_prepare")),
                    ],
                },
                {
                    "title": "Synthèse",
                    "rows": [
                        ("Crédits validés", serialized.get("credits_valides")),
                        ("Crédits totaux", serialized.get("credits_total")),
                        ("Moyenne pondérée", serialized.get("moyenne_ponderee")),
                        ("Mention finale", serialized.get("mention_finale")),
                    ],
                },
                {
                    "title": "Années couvertes",
                    "rows": [
                        (item.get("libelle"), item.get("id"))
                        for item in serialized.get("annees_list", [])
                    ],
                },
            ],
            footer_rows=[("Signé par", serialized.get("signe_par_nom"))],
        )


class AttestationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour attestations."""

    permission_classes = [IsScolariteOrReadOnly]
    required_change_permission = "releves.change_attestation"
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
        serializer = AttestationSerializer(attestations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @enforce_financial_clearance(
        candidates_getter=lambda _view, request, attestation: [
            {"scope": "academic_year", "context": {"academic_year_id": academic_year_id}}
            for academic_year_id in attestation.etudiant.inscriptions_admin.values_list("annee_universitaire_id", flat=True)
        ] + [{"scope": "tenant", "context": {"tenant_id": getattr(request.tenant, "id", None)}}],
        subject_getter=lambda _view, _request, attestation: attestation.etudiant,
        academic_year_ids_getter=lambda _view, _request, attestation: list(
            attestation.etudiant.inscriptions_admin.values_list("annee_universitaire_id", flat=True)
        ),
        invoice_model_label="paiements.FactureFrais",
        invoice_subject_field="etudiant",
        invoice_year_lookup="type_frais__annee_universitaire_id",
        message="La signature de l'attestation exige une situation financière régularisée.",
    )
    def signer(self, request, pk=None):
        """Signe une attestation."""
        attestation = get_action_object(self)
        if attestation.signe_par_id:
            return Response({"error": "Déjà signé."}, status=400)
        attestation.signe_par = request.user
        attestation.save(update_fields=["signe_par"])
        record_workflow_event(
            request,
            attestation,
            "signature",
            "Attestation signée",
            message=f"L'attestation {attestation.numero} de {attestation.etudiant} a été signée.",
            recipients=_student_notification_recipients(request, attestation.etudiant),
            metadata={"etudiant_id": attestation.etudiant_id, "type": attestation.type},
        )
        return Response({"detail": "Attestation signée.", "id": attestation.id})

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow de l'attestation."""
        attestation = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(attestation), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def pdf_officiel(self, request, pk=None):
        """Génère le PDF officiel de l'attestation."""
        attestation = self.get_object()
        serialized = AttestationSerializer(attestation).data
        return render_official_pdf(
            f"attestation-{attestation.id}.pdf",
            f"{serialized.get('type_display')} - {serialized.get('etudiant_nom')}",
            tenant_identity_rows(
                request,
                serialized.get("type_display") or "Attestation",
                serial=attestation.numero,
                issue_date=attestation.date_emission,
            ),
            [
                {
                    "title": "Bénéficiaire",
                    "rows": [
                        ("Étudiant", serialized.get("etudiant_nom")),
                        ("Matricule", serialized.get("etudiant_matricule")),
                    ],
                },
                {
                    "title": "Document",
                    "rows": [
                        ("Type", serialized.get("type_display")),
                        ("Date de validité", serialized.get("date_validite")),
                        ("Numéro", serialized.get("numero")),
                    ],
                },
            ],
            footer_rows=[("Signé par", serialized.get("signe_par_nom"))],
        )
