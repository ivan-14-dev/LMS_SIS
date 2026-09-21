"""API views for examens (ViewSets DRF) - SIS Secondaire."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count
from django.http import FileResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import request_has_business_access, user_has_any_role

from .models import (
    AffectationCorrection,
    AuditCopieExamen,
    ConvocationExamen,
    CopieExamen,
    CorrectionCopie,
    EpreuveExamen,
    ResultatExamen,
    SessionExamen,
)
from .serializers import (
    AffectationCorrectionSerializer,
    AuditCopieExamenSerializer,
    ConvocationExamenSerializer,
    CopieExamenSerializer,
    CorrectionCopieSerializer,
    EpreuveExamenDetailSerializer,
    EpreuveExamenListSerializer,
    ResultatExamenSerializer,
    SessionExamenSerializer,
)


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "examens.change_sessionexamen",
            ("direction", "responsable_pedagogique", "vie_scolaire"),
            tenant_group_codes=("exam_manager_secondary",),
        )


class IsExamManager(IsAuthenticated):
    """Réserve les données nominatives aux équipes chargées des examens."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request_has_business_access(
            request,
            "examens.view_convocationexamen",
            ("direction", "responsable_pedagogique", "vie_scolaire"),
            tenant_group_codes=("exam_manager_secondary",),
        )


class IsCorrectionParticipant(IsAuthenticated):
    """Autorise les gestionnaires et les enseignants affectés."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request_has_business_access(
            request,
            "examens.view_copieexamen",
            ("direction", "responsable_pedagogique", "vie_scolaire", "enseignant"),
            tenant_group_codes=("exam_manager_secondary",),
        )


class SessionsExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour sessions d'examen."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = SessionExamenSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["annee_scolaire", "type"]
    search_fields = ["nom"]
    ordering = ["-date_debut"]

    def get_queryset(self):
        return SessionExamen.objects.select_related("annee_scolaire").annotate(
            nb_epreuves_count=Count("epreuves")
        )

    @action(detail=True, methods=["get"])
    def epreuves(self, request, pk=None):
        """Liste les épreuves de la session."""
        session = self.get_object()
        epreuves = session.epreuves.select_related("matiere").order_by(
            "date", "heure_debut"
        )
        serializer = EpreuveExamenListSerializer(epreuves, many=True)
        return Response(serializer.data)


class EpreuvesExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour épreuves d'examen."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["session", "matiere", "date"]
    ordering = ["date", "heure_debut"]

    def get_queryset(self):
        return EpreuveExamen.objects.select_related(
            "session", "matiere", "salle_principale"
        ).prefetch_related("classes", "surveillants")

    def get_serializer_class(self):
        if self.action == "list":
            return EpreuveExamenListSerializer
        return EpreuveExamenDetailSerializer

    @action(detail=True, methods=["get"], permission_classes=[IsExamManager])
    def convocations(self, request, pk=None):
        """Liste les convocations de l'épreuve."""
        epreuve = self.get_object()
        convocations = epreuve.convocations.select_related("eleve__user").order_by(
            "numero_place"
        )
        serializer = ConvocationExamenSerializer(convocations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[IsExamManager])
    def resultats(self, request, pk=None):
        """Liste les résultats de l'épreuve."""
        epreuve = self.get_object()
        resultats = epreuve.resultats.select_related("eleve__user").order_by("-note")
        serializer = ResultatExamenSerializer(resultats, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[IsExamManager])
    def statistiques(self, request, pk=None):
        """Statistiques de l'épreuve."""
        epreuve = self.get_object()
        resultats = epreuve.resultats.all()
        stats = resultats.aggregate(moyenne=Avg("note"))
        stats["nb_inscrits"] = epreuve.convocations.count()
        stats["nb_presents"] = epreuve.convocations.filter(statut="present").count()
        stats["nb_absents"] = epreuve.convocations.filter(statut="absent").count()
        stats["nb_notes"] = resultats.exclude(note__isnull=True).count()
        return Response(stats)


class ConvocationsExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour convocations."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = ConvocationExamenSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["epreuve", "eleve", "statut"]
    ordering = ["numero_place"]

    def get_queryset(self):
        queryset = ConvocationExamen.objects.select_related(
            "epreuve__matiere", "eleve__user"
        )
        user = self.request.user
        if IsExamManager().has_permission(self.request, self):
            return queryset
        if user_has_any_role(user, ("eleve",)):
            return queryset.filter(eleve__user=user)
        if user_has_any_role(user, ("parent",)):
            return queryset.filter(
                eleve__tuteurs_lies__tuteur__user=user,
                eleve__tuteurs_lies__autorise_acces_portail=True,
            ).distinct()
        return queryset.none()

    @action(detail=True, methods=["post"])
    def marquer_present(self, request, pk=None):
        """Marque l'élève comme présent."""
        convocation = self.get_object()
        convocation.statut = "present"
        convocation.save(update_fields=["statut"])
        return Response({"detail": "Marqué présent.", "id": convocation.id})

    @action(detail=True, methods=["post"])
    def marquer_absent(self, request, pk=None):
        """Marque l'élève comme absent."""
        convocation = self.get_object()
        convocation.statut = "absent"
        convocation.save(update_fields=["statut"])
        return Response({"detail": "Marqué absent.", "id": convocation.id})


class ResultatsExamenViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour résultats d'examen."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = ResultatExamenSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["epreuve", "eleve", "admis"]
    ordering = ["-note"]

    def get_queryset(self):
        queryset = ResultatExamen.objects.select_related(
            "epreuve__matiere", "eleve__user"
        )
        user = self.request.user
        if IsExamManager().has_permission(self.request, self):
            return queryset
        if user_has_any_role(user, ("eleve",)):
            return queryset.filter(eleve__user=user)
        if user_has_any_role(user, ("parent",)):
            return queryset.filter(
                eleve__tuteurs_lies__tuteur__user=user,
                eleve__tuteurs_lies__autorise_acces_portail=True,
            ).distinct()
        return queryset.none()


class CopiesExamenViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Dépôt privé et consultation anonyme des copies."""

    serializer_class = CopieExamenSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["convocation__epreuve", "statut"]

    def get_permissions(self):
        permission = (
            IsExamManager
            if self.action in ("create", "moderer", "audit")
            else IsCorrectionParticipant
        )
        return [permission()]

    def get_queryset(self):
        queryset = CopieExamen.objects.select_related(
            "convocation__epreuve", "deposee_par", "moderee_par"
        ).prefetch_related("affectations")
        user = self.request.user
        if IsExamManager().has_permission(self.request, self):
            return queryset
        return queryset.filter(affectations__correcteur=user).distinct()

    def perform_create(self, serializer):
        copie = serializer.save()
        AuditCopieExamen.objects.create(
            copie=copie,
            acteur=self.request.user,
            action="depot",
            details={
                "empreinte_sha256": copie.empreinte_sha256,
                "taille_octets": copie.taille_octets,
            },
        )

    @action(detail=True, methods=["get"])
    def telecharger(self, request, pk=None):
        copie = self.get_object()
        fichier = copie.fichier.open("rb")
        AuditCopieExamen.objects.create(
            copie=copie, acteur=request.user, action="telechargement"
        )
        return FileResponse(
            fichier,
            as_attachment=True,
            filename=f"{copie.numero_anonyme}.pdf",
            content_type="application/pdf",
        )

    @action(detail=True, methods=["post"], permission_classes=[IsExamManager])
    def moderer(self, request, pk=None):
        with transaction.atomic():
            copie = (
                CopieExamen.objects.select_for_update()
                .select_related("convocation__epreuve")
                .get(pk=self.get_object().pk)
            )
            if copie.statut != "a_moderer":
                return Response(
                    {"error": "Cette copie n'est pas prête pour la modération."},
                    status=status.HTTP_409_CONFLICT,
                )
            corrections = list(
                copie.affectations.filter(statut="soumise").select_related("correction")
            )
            if len(corrections) != copie.epreuve.nombre_corrections:
                return Response(
                    {"error": "Toutes les corrections attendues ne sont pas soumises."},
                    status=status.HTTP_409_CONFLICT,
                )
            moyenne = sum(item.correction.note for item in corrections) / Decimal(
                len(corrections)
            )
            try:
                proposed = request.data.get("note_finale")
                note_finale = (
                    Decimal(str(proposed)) if proposed is not None else moyenne
                )
            except (ArithmeticError, TypeError, ValueError):
                return Response({"note_finale": "Note invalide."}, status=400)
            if note_finale < 0 or note_finale > copie.epreuve.bareme:
                return Response(
                    {"note_finale": "La note doit respecter le barème."}, status=400
                )
            motif = request.data.get("motif", "").strip()
            if note_finale != moyenne and not motif:
                return Response(
                    {
                        "motif": "Un motif est obligatoire lorsque la note finale diffère de la moyenne."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            copie.note_finale = note_finale
            copie.moderee_par = request.user
            copie.moderee_le = timezone.now()
            copie.motif_moderation = motif
            copie.statut = "finalisee"
            copie.save(
                update_fields=[
                    "note_finale",
                    "moderee_par",
                    "moderee_le",
                    "motif_moderation",
                    "statut",
                ]
            )
            ResultatExamen.objects.update_or_create(
                epreuve=copie.epreuve,
                eleve=copie.convocation.eleve,
                defaults={
                    "note": note_finale,
                    "numero_anonyme": copie.numero_anonyme,
                },
            )
            AuditCopieExamen.objects.create(
                copie=copie,
                acteur=request.user,
                action="moderation",
                details={"note_finale": str(note_finale)},
            )
        return Response(self.get_serializer(copie).data)

    @action(detail=True, methods=["get"], permission_classes=[IsExamManager])
    def audit(self, request, pk=None):
        copie = self.get_object()
        serializer = AuditCopieExamenSerializer(copie.audit.all(), many=True)
        return Response(serializer.data)


class AffectationsCorrectionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = AffectationCorrectionSerializer

    def get_permissions(self):
        permission = (
            IsExamManager if self.action == "create" else IsCorrectionParticipant
        )
        return [permission()]

    def get_queryset(self):
        queryset = AffectationCorrection.objects.select_related(
            "copie__convocation__epreuve", "correcteur"
        )
        if IsExamManager().has_permission(self.request, self):
            return queryset
        return queryset.filter(correcteur=self.request.user)

    def perform_create(self, serializer):
        with transaction.atomic():
            copie = (
                CopieExamen.objects.select_for_update()
                .select_related("convocation__epreuve")
                .get(pk=serializer.validated_data["copie"].pk)
            )
            if (
                copie.statut not in ("deposee", "affectee")
                or copie.affectations.count() >= copie.epreuve.nombre_corrections
            ):
                raise ValidationError(
                    {"copie": "Cette copie n'accepte plus de nouvelles affectations."}
                )
            affectation = serializer.save(copie=copie)
            affectation.copie.statut = "affectee"
            affectation.copie.save(update_fields=["statut"])
            AuditCopieExamen.objects.create(
                copie=affectation.copie,
                acteur=self.request.user,
                action="affectation",
                details={
                    "correcteur_id": affectation.correcteur_id,
                    "ordre": affectation.ordre,
                },
            )


class CorrectionsCopieViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsCorrectionParticipant]
    serializer_class = CorrectionCopieSerializer

    def get_queryset(self):
        queryset = CorrectionCopie.objects.select_related(
            "affectation__copie__convocation__epreuve", "affectation__correcteur"
        )
        if IsExamManager().has_permission(self.request, self):
            return queryset
        return queryset.filter(affectation__correcteur=self.request.user)

    def perform_create(self, serializer):
        with transaction.atomic():
            affectation = (
                AffectationCorrection.objects.select_for_update()
                .select_related("copie__convocation__epreuve")
                .get(pk=serializer.validated_data["affectation"].pk)
            )
            copie = CopieExamen.objects.select_for_update().get(pk=affectation.copie_id)
            if affectation.statut != "assignee" or copie.statut not in (
                "affectee",
                "correction",
            ):
                raise ValidationError(
                    {"affectation": "Cette affectation n'accepte plus de correction."}
                )
            serializer.save(affectation=affectation)
            affectation.statut = "soumise"
            affectation.save(update_fields=["statut"])
            submitted = copie.affectations.filter(statut="soumise").count()
            copie.statut = (
                "a_moderer"
                if submitted >= copie.epreuve.nombre_corrections
                else "correction"
            )
            copie.save(update_fields=["statut"])
            AuditCopieExamen.objects.create(
                copie=copie,
                acteur=self.request.user,
                action="correction_soumise",
                details={"ordre": affectation.ordre},
            )
