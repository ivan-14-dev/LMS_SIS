"""Private PDF archives with detached Ed25519 evidence, not qualified signatures."""

import base64
import hashlib
import json
import logging
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.db.models import Exists, Max, OuterRef, Q
from django.http import HttpResponse
from django_tenants.utils import get_public_schema_name
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ParseError, PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.request import clone_request
from rest_framework.response import Response

from sis_common.authorization import filter_queryset_by_scopes
from sis_common.complaints import user_label
from sis_common.delegations import ActiveTenantAccess
from sis_common.encryption import decrypt_value
from sis_common.exam_files import hash_uploaded_file, validate_exam_copy
from sis_common.official_documents import verify_official_archive
from sis_common.signatures import USE, Signature, allowed, document_types, public_fingerprint, signing_mandate
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

Archive = apps.get_model("core.DocumentArchive")
Revocation = apps.get_model("core.ArchiveRevocation")
logger = logging.getLogger("apps.signatures")
MAX_PUBLIC_VERIFICATION_PDF_BYTES = 10 * 1024 * 1024


def canonical_manifest(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def source_view(request, source_type):
    if source_type not in dict(document_types()):
        raise ValidationError({"source_type": "Type de document non pris en charge."})
    if source_type == "notes.bulletin":
        from apps.notes.api import BulletinsViewSet

        cls = BulletinsViewSet
        owner = "eleve__user_id"
        scopes = {"classes": "classe_id", "annees": "classe__annee_scolaire_id", "periodes": "periode_id"}
    else:
        from apps.releves.api import AttestationsViewSet, RelevesNotesViewSet, TranscriptsViewSet

        cls = {
            "releves.relevenotes": RelevesNotesViewSet,
            "releves.transcript": TranscriptsViewSet,
            "releves.attestation": AttestationsViewSet,
        }[source_type]
        owner = "etudiant__user_id"
        scopes = {"etudiants": "etudiant_id"}
        if source_type == "releves.relevenotes":
            scopes.update(semestres="semestre_id", annees="semestre__annee_universitaire_id")
        elif source_type == "releves.transcript":
            scopes["annees"] = "annees__id"
    read_request = clone_request(request, "GET")
    view = cls(request=read_request, action="pdf_officiel", kwargs={}, format_kwarg=None)
    view.check_permissions(read_request)
    return view, owner, scopes


def writable_sources(request, source_type):
    view, owner, scopes = source_view(request, source_type)
    app, name = source_type.split(".")
    permission = f"{app}.change_{name}"
    if not request.user.has_perm(permission):
        raise PermissionDenied("La signature exige aussi le droit de modification du document source.")
    queryset = filter_queryset_by_scopes(view.get_queryset(), request.user, permission, scopes)
    approved = (
        {"publie": True}
        if source_type == "notes.bulletin"
        else ({"signe": True} if source_type == "releves.relevenotes" else {"signe_par__isnull": False})
    )
    return view, owner, queryset.filter(**approved)


def check_integrity(archive, pdf_hash):
    try:
        key = archive.signature.cle_publique
        if key != archive.cle_publique or public_fingerprint(key) != archive.manifeste["empreinte_cle"]:
            raise InvalidSignature
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key, validate=True)).verify(
            base64.b64decode(archive.preuve, validate=True), canonical_manifest(archive.manifeste)
        )
        if pdf_hash != archive.sha256 or pdf_hash != archive.manifeste["sha256"]:
            raise InvalidSignature
    except (InvalidSignature, ValueError, KeyError) as exc:
        raise ValidationError("L'intégrité du PDF ou de sa preuve ne peut pas être confirmée.") from exc


class ArchiveSerializer(serializers.ModelSerializer):
    titulaire_nom = serializers.SerializerMethodField()
    beneficiaire_nom = serializers.SerializerMethodField()
    statut = serializers.SerializerMethodField()
    motif_revocation = serializers.SerializerMethodField()

    class Meta:
        model = Archive
        fields = [
            "id",
            "source_type",
            "source_id",
            "beneficiaire_nom",
            "titulaire_nom",
            "version",
            "sha256",
            "created_at",
            "statut",
            "motif_revocation",
        ]
        read_only_fields = fields

    def get_titulaire_nom(self, obj):
        return user_label(obj.signature.titulaire)

    def get_beneficiaire_nom(self, obj):
        return user_label(obj.beneficiaire)

    def get_statut(self, obj):
        return "revoque" if hasattr(obj, "revocation") else "valide"

    def get_motif_revocation(self, obj):
        return obj.revocation.motif if hasattr(obj, "revocation") else ""


class CreateArchiveSerializer(serializers.Serializer):
    source_type = serializers.CharField()
    source_id = serializers.IntegerField(min_value=1)
    signature = serializers.UUIDField()
    idempotency_key = serializers.UUIDField()


class SignedDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [ActiveTenantAccess]
    serializer_class = ArchiveSerializer

    def get_queryset(self):
        access = Q(beneficiaire=self.request.user)
        for source_type, _ in document_types():
            view, owner, _ = source_view(self.request, source_type)
            sources = view.get_queryset().filter(pk=OuterRef("source_id"), **{owner: OuterRef("beneficiaire_id")})
            access |= Q(Exists(sources), source_type=source_type)
        return (
            Archive.objects.filter(etablissement=self.request.tenant)
            .filter(access)
            .select_related("signature__titulaire", "beneficiaire", "revocation")
            .defer("pdf")
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="verification-publique",
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def verification_publique(self, request):
        """Check archive_id and a presented PDF; never return archive metadata."""

        def result(valid=False):
            response = Response({"valide": valid})
            response["Cache-Control"] = "no-store"
            return response

        tenant = getattr(request, "tenant", None)
        if (
            tenant is None
            or getattr(tenant, "pk", None) is None
            or getattr(tenant, "schema_name", get_public_schema_name()) == get_public_schema_name()
        ):
            return result()
        try:
            content_length = int(request.META.get("CONTENT_LENGTH", ""))
        except (ValueError, TypeError):
            return result()
        if (
            content_length <= 0
            or content_length > MAX_PUBLIC_VERIFICATION_PDF_BYTES + 65536
            or request.content_type.split(";", 1)[0].strip().lower() != "multipart/form-data"
        ):
            return result()
        try:
            uploaded = request.FILES.get("pdf")
            if uploaded is None or uploaded.size > MAX_PUBLIC_VERIFICATION_PDF_BYTES:
                return result()
            archive_id = uuid.UUID(str(request.data.get("archive_id")))
        except (ParseError, ValueError, TypeError, AttributeError):
            return result()
        pdf = uploaded.read(MAX_PUBLIC_VERIFICATION_PDF_BYTES + 1)
        if not pdf.startswith(b"%PDF-") or len(pdf) > MAX_PUBLIC_VERIFICATION_PDF_BYTES:
            return result()
        archive = (
            Archive.objects.filter(pk=archive_id, etablissement_id=tenant.pk)
            .select_related("signature", "revocation")
            .defer("pdf")
            .first()
        )
        return result(verify_official_archive(archive, pdf)["valide"])

    @action(detail=False, methods=["get"])
    def sources(self, request):
        if not allowed(request.user, USE, request.tenant):
            raise PermissionDenied("Vous n'êtes pas habilité à apposer une signature.")
        _, _, queryset = writable_sources(request, request.query_params.get("source_type"))
        page = self.paginate_queryset(queryset.order_by("pk"))
        return self.get_paginated_response([{"id": item.pk, "label": str(item)} for item in page])

    @transaction.atomic
    def create(self, request):
        if not allowed(request.user, USE, request.tenant):
            raise PermissionDenied("Vous n'êtes pas habilité à apposer une signature.")
        serializer = CreateArchiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        previous = Archive.objects.filter(operateur=request.user, idempotency_key=values["idempotency_key"]).first()
        if previous:
            if (previous.source_type, previous.source_id, previous.signature_id) != (
                values["source_type"],
                values["source_id"],
                values["signature"],
            ):
                return Response({"detail": "Cette clé a déjà servi pour une autre apposition."}, status=409)
            self.kwargs["pk"] = previous.pk
            return Response(self.get_serializer(self.get_object()).data)
        view, owner, queryset = writable_sources(request, values["source_type"])
        source = get_object_or_404(queryset, pk=values["source_id"])
        source = type(source).objects.select_for_update().get(pk=source.pk)
        source = get_object_or_404(queryset, pk=source.pk)
        signature = get_object_or_404(
            Signature.objects.select_for_update(of=("self",)).select_related("titulaire"),
            pk=values["signature"],
            etablissement=request.tenant,
        )
        mandate = signing_mandate(signature, request.user, request.tenant)
        if values["source_type"] not in signature.types_documents:
            raise PermissionDenied("Cette signature n'autorise pas ce type de document.")
        beneficiary = source.eleve.user if owner.startswith("eleve") else source.etudiant.user
        view.kwargs = {"pk": source.pk}
        pdf = bytes(view.pdf_officiel.render_document(view, request, pk=source.pk).content)
        if not pdf.startswith(b"%PDF-"):
            raise APIException("Le générateur n'a pas produit de PDF valide.")
        archive = Archive(
            etablissement=request.tenant,
            source_type=values["source_type"],
            source_id=source.pk,
            beneficiaire=beneficiary,
            signature=signature,
            operateur=request.user,
            mandat=mandate,
            idempotency_key=values["idempotency_key"],
            pdf=pdf,
            sha256=hashlib.sha256(pdf).hexdigest(),
            cle_publique=signature.cle_publique,
            version=(
                Archive.objects.filter(source_type=values["source_type"], source_id=source.pk).aggregate(
                    last=Max("version")
                )["last"]
                or 0
            )
            + 1,
        )
        archive.manifeste = {
            "format": "LMS_SIS-Ed25519-detached-v1",
            "archive": str(archive.pk),
            "etablissement": request.tenant.pk,
            "source_type": archive.source_type,
            "source_id": source.pk,
            "beneficiaire": beneficiary.pk,
            "version": archive.version,
            "sha256": archive.sha256,
            "signature": str(signature.pk),
            "titulaire": signature.titulaire_id,
            "fonction": signature.fonction,
            "approbateur": signature.valide_par_id,
            "approbation": signature.valide_le.isoformat(),
            "operateur": request.user.pk,
            "mandat": mandate.pk if mandate else None,
            "date": archive.created_at.isoformat(),
            "empreinte_cle": public_fingerprint(signature.cle_publique),
        }
        try:
            key = Ed25519PrivateKey.from_private_bytes(
                base64.b64decode(decrypt_value(signature.cle_privee_chiffree), validate=True)
            )
            if base64.b64encode(key.public_key().public_bytes_raw()).decode("ascii") != signature.cle_publique:
                raise ValueError("Signing key mismatch")
        except (InvalidToken, ValueError, UnicodeError) as exc:
            logger.error("Clé de signature indisponible", extra={"signature_id": str(signature.pk)})
            raise APIException(
                "La clé de signature ne peut pas être déchiffrée ou vérifiée. Contactez l'administrateur."
            ) from exc
        archive.preuve = base64.b64encode(key.sign(canonical_manifest(archive.manifeste))).decode("ascii")
        archive.save()
        record_workflow_event(
            request,
            archive,
            "signature_apposee",
            "Signature apposée sur un document archivé",
            message=f"{archive.source_type} #{archive.source_id}, version {archive.version}.",
            recipients=list({signature.titulaire, beneficiary}),
            metadata={
                "signature_id": str(signature.pk),
                "archive_id": str(archive.pk),
                "sha256": archive.sha256,
                "operateur_id": request.user.pk,
            },
        )
        return Response(self.get_serializer(archive).data, status=201)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        archive = self.get_object()
        content = bytes(archive.pdf)
        check_integrity(archive, hashlib.sha256(content).hexdigest())
        record_workflow_event(request, archive, "archive_telechargee", "Version archivée téléchargée")
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="archive-{archive.pk}-v{archive.version}.pdf"'
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @action(detail=True, methods=["get"])
    def preuve(self, request, pk=None):
        archive = self.get_object()
        check_integrity(archive, hashlib.sha256(bytes(archive.pdf)).hexdigest())
        response = HttpResponse(
            json.dumps(
                {"manifeste": archive.manifeste, "preuve": archive.preuve, "cle_publique": archive.cle_publique},
                ensure_ascii=False,
                indent=2,
            ),
            content_type="application/json",
        )
        response["Content-Disposition"] = f'attachment; filename="preuve-{archive.pk}.json"'
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @action(detail=True, methods=["post"])
    def verifier(self, request, pk=None):
        archive = self.get_object()
        uploaded = request.FILES.get("pdf")
        if uploaded is not None:
            try:
                validate_exam_copy(uploaded)
            except ModelValidationError as exc:
                raise ValidationError({"pdf": exc.messages}) from exc
            digest = hash_uploaded_file(uploaded)
        else:
            digest = hashlib.sha256(bytes(archive.pdf)).hexdigest()
        check_integrity(archive, digest)
        return Response(
            {
                "integrite": True,
                "statut": "revoque" if hasattr(archive, "revocation") else "valide",
                "sha256": digest,
                "empreinte_cle": public_fingerprint(archive.cle_publique),
                "qualification": "Preuve technique institutionnelle détachée, non qualifiée juridiquement.",
            }
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def revoquer(self, request, pk=None):
        if not allowed(request.user, "core.revoke_documentarchive", request.tenant):
            raise PermissionDenied("Une habilitation de révocation est nécessaire.")
        archive = self.get_object()
        Archive.objects.select_for_update().get(pk=archive.pk)
        motif = serializers.CharField(trim_whitespace=True).run_validation(request.data.get("motif"))
        if Revocation.objects.filter(archive=archive).exists():
            raise ValidationError("Cette version est déjà révoquée.")
        Revocation.objects.create(archive=archive, auteur=request.user, motif=motif)
        record_workflow_event(
            request,
            archive,
            "archive_revoquee",
            "Version archivée révoquée",
            message=motif,
            recipients=list({archive.signature.titulaire, archive.beneficiaire}),
        )
        return Response({"detail": "Version révoquée ; le PDF et sa preuve sont conservés."})

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        from apps.core.serializers import WorkflowEventSerializer

        return Response(WorkflowEventSerializer(workflow_history_queryset(self.get_object()), many=True).data)
