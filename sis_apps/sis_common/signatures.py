"""Independently approved institutional signing identities and bounded mandates."""

import base64
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from sis_common.authorization import has_business_permission
from sis_common.complaints import eligible_agents, user_label
from sis_common.delegations import LEARNERS, ActiveTenantAccess
from sis_common.encryption import encrypt_value
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

Signature = apps.get_model("core.SignatureApproval")
Mandate = apps.get_model("core.SignatureMandate")
REQUEST = "core.request_signature"
APPROVE = "core.approve_signature"
USE = "core.use_signature"


def allowed(user, permission, tenant):
    return (
        user.is_active
        and user.etablissement_id == tenant.pk
        and (user.is_superuser or user.role not in (*LEARNERS, "parent"))
        and has_business_permission(user, permission, context={"etablissement_id": tenant.pk})
    )


def document_types():
    if settings.SIS_VARIANT == "secondaire":
        return [("notes.bulletin", "Bulletins publiés")]
    return [
        ("releves.relevenotes", "Relevés validés"),
        ("releves.transcript", "Transcripts validés"),
        ("releves.attestation", "Attestations validées"),
    ]


def public_fingerprint(key):
    return hashlib.sha256(base64.b64decode(key, validate=True)).hexdigest() if key else ""


def signing_mandate(signature, operator, tenant):
    if not signature.utilisable or not allowed(signature.titulaire, USE, tenant):
        raise PermissionDenied("La signature n'est pas approuvée, active ou dans sa période autorisée.")
    if signature.etablissement_id != tenant.pk or not allowed(operator, USE, tenant):
        raise PermissionDenied("Vous n'êtes pas habilité à apposer cette signature.")
    if signature.titulaire_id == operator.pk:
        return None
    now = timezone.now()
    mandate = (
        signature.mandats.select_for_update()
        .filter(operateur=operator, debut__lte=now, fin__gt=now, revoque_le__isnull=True)
        .first()
    )
    if mandate is None:
        raise PermissionDenied("Une délégation de signature explicite et active est nécessaire.")
    return mandate


class SignatureSerializer(serializers.ModelSerializer):
    titulaire_nom = serializers.SerializerMethodField()
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    utilisable = serializers.BooleanField(read_only=True)
    empreinte_cle = serializers.SerializerMethodField()
    types_documents = serializers.ListField(child=serializers.CharField(), min_length=1)

    class Meta:
        model = Signature
        fields = [
            "id",
            "titulaire_nom",
            "fonction",
            "types_documents",
            "debut",
            "fin",
            "statut",
            "statut_display",
            "utilisable",
            "valide_le",
            "cle_publique",
            "empreinte_cle",
            "created_at",
        ]
        read_only_fields = ["id", "statut", "valide_le", "cle_publique", "created_at"]

    def get_titulaire_nom(self, obj):
        return user_label(obj.titulaire)

    def get_empreinte_cle(self, obj):
        return public_fingerprint(obj.cle_publique)

    def validate(self, attrs):
        if not set(attrs["types_documents"]).issubset(dict(document_types())):
            raise ValidationError({"types_documents": "Un type de document n'est pas pris en charge."})
        attrs["types_documents"] = sorted(set(attrs["types_documents"]))
        if attrs["fin"] <= attrs["debut"] or attrs["fin"] <= timezone.now():
            raise ValidationError({"fin": "La fin doit être future et postérieure au début."})
        return attrs


class SignatureViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [ActiveTenantAccess]
    serializer_class = SignatureSerializer

    def get_queryset(self):
        request = self.request
        now = timezone.now()
        queryset = Signature.objects.filter(etablissement=request.tenant).select_related("titulaire")
        mandates = Q(
            pk__in=Mandate.objects.filter(
                operateur=request.user,
                debut__lte=now,
                fin__gt=now,
                revoque_le__isnull=True,
            ).values("signature_id")
        )
        own = Q(titulaire=request.user)
        view = request.query_params.get("vue")
        if view == "validation":
            if not allowed(request.user, APPROVE, request.tenant):
                raise PermissionDenied("Une habilitation de validation est nécessaire.")
            queryset = queryset.exclude(titulaire=request.user)
        elif view == "personnel":
            queryset = queryset.filter(own)
        elif view == "utilisables":
            queryset = queryset.filter(
                own | mandates, statut="validee", debut__lte=now, fin__gt=now, titulaire__is_active=True
            )
        elif not allowed(request.user, APPROVE, request.tenant):
            queryset = queryset.filter(own | mandates)
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not allowed(request.user, REQUEST, request.tenant):
            raise PermissionDenied("Vous n'êtes pas habilité à demander une signature institutionnelle.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        signature = serializer.save(titulaire=self.request.user, etablissement=self.request.tenant)
        reviewers = [
            user
            for user in eligible_agents(self.request.tenant, APPROVE)
            if user.pk != self.request.user.pk and allowed(user, APPROVE, self.request.tenant)
        ]
        record_workflow_event(
            self.request,
            signature,
            "signature_demandee",
            "Signature en attente d'approbation",
            recipients=[self.request.user, *reviewers],
        )

    @action(detail=False, methods=["get"])
    def types(self, request):
        return Response([{"value": code, "label": label} for code, label in document_types()])

    @action(detail=False, methods=["get"])
    def operateurs(self, request):
        if not allowed(request.user, REQUEST, request.tenant):
            raise PermissionDenied("Vous n'êtes pas habilité à déléguer une signature.")
        users = [user for user in eligible_agents(request.tenant, USE) if allowed(user, USE, request.tenant)]
        return self.get_paginated_response(
            [
                {"id": user.pk, "label": f"{user_label(user)} ({user.username})"}
                for user in self.paginate_queryset(users)
            ]
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def decider(self, request, pk=None):
        signature = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
        decision = serializers.ChoiceField(choices=["validee", "refusee", "suspendue", "revoquee"]).run_validation(
            request.data.get("decision")
        )
        motif = serializers.CharField(trim_whitespace=True).run_validation(request.data.get("motif"))
        owner = signature.titulaire_id == request.user.pk
        if owner and decision in ("validee", "refusee"):
            raise PermissionDenied("La validation doit être faite par une autre personne habilitée.")
        if not (owner and decision in ("suspendue", "revoquee")) and not allowed(request.user, APPROVE, request.tenant):
            raise PermissionDenied("Vous n'êtes pas habilité à prendre cette décision.")
        transitions = {
            "en_attente": {"validee", "refusee", "revoquee"},
            "validee": {"suspendue", "revoquee"},
            "suspendue": {"validee", "revoquee"},
        }
        if decision not in transitions.get(signature.statut, set()):
            raise ValidationError("Cette transition n'est pas permise.")
        if decision == "validee":
            if signature.fin <= timezone.now() or not allowed(signature.titulaire, USE, request.tenant):
                raise ValidationError("Le titulaire ou la période n'autorise plus cette signature.")
            if not signature.cle_publique:
                key = Ed25519PrivateKey.generate()
                signature.cle_publique = base64.b64encode(key.public_key().public_bytes_raw()).decode("ascii")
                signature.cle_privee_chiffree = encrypt_value(base64.b64encode(key.private_bytes_raw()).decode("ascii"))
                signature.valide_par = request.user
                signature.valide_le = timezone.now()
        signature.statut = decision
        signature.save()
        record_workflow_event(
            request,
            signature,
            f"signature_{decision}",
            "Décision sur une signature",
            message=motif,
            recipients=[signature.titulaire],
        )
        return Response(self.get_serializer(signature).data)

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        from apps.core.serializers import WorkflowEventSerializer

        signature = self.get_object()
        if signature.titulaire_id != request.user.pk and not allowed(request.user, APPROVE, request.tenant):
            raise PermissionDenied("Cet historique est réservé au titulaire et aux validateurs.")
        return Response(WorkflowEventSerializer(workflow_history_queryset(signature), many=True).data)

    @action(detail=True, methods=["get"])
    def usages(self, request, pk=None):
        signature = self.get_object()
        if signature.titulaire_id != request.user.pk and not allowed(request.user, APPROVE, request.tenant):
            raise PermissionDenied("Cet historique est réservé au titulaire et aux validateurs.")
        archives = signature.usages.select_related("operateur").order_by("-created_at")
        return self.get_paginated_response(
            [
                {
                    "id": str(item.pk),
                    "date": item.created_at,
                    "type": item.source_type,
                    "version": item.version,
                    "sha256": item.sha256,
                    "operateur": user_label(item.operateur),
                    "mandat": item.mandat_id,
                }
                for item in self.paginate_queryset(archives)
            ]
        )


class MandateSerializer(serializers.ModelSerializer):
    titulaire_nom = serializers.SerializerMethodField()
    operateur_nom = serializers.SerializerMethodField()
    statut = serializers.CharField(read_only=True)

    class Meta:
        model = Mandate
        fields = ["id", "signature", "titulaire_nom", "operateur", "operateur_nom", "debut", "fin", "motif", "statut"]
        read_only_fields = ["id"]

    def get_titulaire_nom(self, obj):
        return user_label(obj.signature.titulaire)

    def get_operateur_nom(self, obj):
        return user_label(obj.operateur)

    def validate(self, attrs):
        request = self.context["request"]
        signature = attrs["signature"]
        if signature.titulaire_id != request.user.pk or signature.etablissement_id != request.tenant.pk:
            raise PermissionDenied("Seul le titulaire peut déléguer sa signature.")
        if not signature.utilisable or not allowed(request.user, USE, request.tenant):
            raise ValidationError("Cette signature n'est pas utilisable.")
        if attrs["operateur"].pk == request.user.pk or not allowed(attrs["operateur"], USE, request.tenant):
            raise ValidationError({"operateur": "Choisissez une autre personne habilitée de l'établissement."})
        if not (signature.debut <= attrs["debut"] < attrs["fin"] <= signature.fin and attrs["fin"] > timezone.now()):
            raise ValidationError(
                {"fin": "La délégation doit être future et comprise dans la période de la signature."}
            )
        return attrs


class SignatureMandateViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [ActiveTenantAccess]
    serializer_class = MandateSerializer

    def get_queryset(self):
        queryset = Mandate.objects.filter(signature__etablissement=self.request.tenant).select_related(
            "signature__titulaire", "operateur"
        )
        if not allowed(self.request.user, APPROVE, self.request.tenant):
            queryset = queryset.filter(Q(signature__titulaire=self.request.user) | Q(operateur=self.request.user))
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not allowed(request.user, REQUEST, request.tenant):
            raise PermissionDenied("Vous n'êtes pas habilité à déléguer une signature.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        signature = Signature.objects.select_for_update().get(pk=serializer.validated_data["signature"].pk)
        if not signature.utilisable:
            raise ValidationError("Cette signature n'est plus utilisable.")
        mandate = serializer.save()
        record_workflow_event(
            self.request,
            mandate,
            "mandat_signature_accorde",
            "Délégation de signature accordée",
            message=mandate.motif,
            recipients=[self.request.user, mandate.operateur],
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def revoquer(self, request, pk=None):
        mandate = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
        if mandate.signature.titulaire_id != request.user.pk and not allowed(request.user, APPROVE, request.tenant):
            raise PermissionDenied("Seul le titulaire ou un validateur peut révoquer cette délégation.")
        motif = serializers.CharField(trim_whitespace=True).run_validation(request.data.get("motif"))
        if mandate.revoque_le:
            raise ValidationError("Cette délégation est déjà révoquée.")
        mandate.revoque_le = timezone.now()
        mandate.save(update_fields=["revoque_le"])
        record_workflow_event(
            request,
            mandate,
            "mandat_signature_revoque",
            "Délégation de signature révoquée",
            message=motif,
            recipients=[mandate.signature.titulaire, mandate.operateur],
        )
        return Response(self.get_serializer(mandate).data)
