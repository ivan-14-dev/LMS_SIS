"""API views for notes (ViewSets DRF) - SIS Supérieur."""

from django.db.models import Avg, Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import (
    filter_queryset_by_scopes,
    has_business_permission_or_role,
)
from sis_common.reporting import configured_report, export_queryset_csv

from .models import Evaluation, MoyenneECUE, MoyenneUE, Note, RegleValidation
from .serializers import (
    EvaluationDetailSerializer,
    EvaluationListSerializer,
    MoyenneECUESerializer,
    MoyenneUESerializer,
    NoteSaisieSerializer,
    NoteSerializer,
    RegleValidationSerializer,
)

REPORT_FIELDS = {
    "matricule": ("Matricule", "etudiant__matricule"),
    "etudiant": ("Étudiant", "etudiant__user__last_name"),
    "formation": (
        "Formation",
        "etudiant__inscriptions_admin__formation__nom",
    ),
    "ecue": ("ECUE", "evaluation__ecue__nom"),
    "ue": ("UE", "evaluation__ecue__ue__nom"),
    "evaluation": ("Évaluation", "evaluation__titre"),
    "note": ("Note", "valeur"),
    "bareme": ("Barème", "evaluation__bareme"),
    "appreciation": ("Appréciation", "appreciation"),
    "enseignant": ("Enseignant", "evaluation__enseignant__last_name"),
    "semestre": ("Semestre", "evaluation__semestre__numero"),
    "date": ("Date", "evaluation__date"),
}
REPORT_FILTERS = {
    "annee": "evaluation__semestre__annee_universitaire_id",
    "formation": "etudiant__inscriptions_admin__formation_id",
    "ecue": "evaluation__ecue_id",
    "ue": "evaluation__ecue__ue_id",
    "enseignant": "evaluation__enseignant_id",
    "semestre": "evaluation__semestre_id",
    "statut": "statut",
}
REPORT_GROUPS = {
    "formation": "etudiant__inscriptions_admin__formation__nom",
    "ecue": "evaluation__ecue__nom",
    "ue": "evaluation__ecue__ue__nom",
    "enseignant": "evaluation__enseignant__last_name",
    "semestre": "evaluation__semestre__numero",
}


class IsEnseignantOrScolarite(IsAuthenticated):
    """Permission: enseignant ou scolarité."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "enseignant",
            "scolarite",
            "directeur_etudes",
        )


class IsAcademicAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(
            request, view
        ) and has_business_permission_or_role(
            request.user,
            "notes.change_reglevalidation",
            ("president", "vice_president", "doyen", "directeur_etudes", "scolarite"),
        )


class EvaluationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour évaluations."""

    permission_classes = [IsEnseignantOrScolarite]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["ecue", "semestre", "modalite", "enseignant", "anonyme"]
    search_fields = ["titre", "description"]
    ordering_fields = ["date", "titre", "created_at"]
    ordering = ["-date"]

    def get_queryset(self):
        return Evaluation.objects.select_related("ecue", "semestre", "enseignant")

    def get_serializer_class(self):
        if self.action == "list":
            return EvaluationListSerializer
        return EvaluationDetailSerializer

    @action(detail=True, methods=["get"])
    def notes(self, request, pk=None):
        """Liste les notes d'une évaluation."""
        evaluation = self.get_object()
        notes = evaluation.notes.select_related("etudiant__user").order_by(
            "etudiant__user__last_name"
        )
        serializer = NoteSerializer(notes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def saisir_notes(self, request, pk=None):
        """Saisie en masse des notes."""
        evaluation = self.get_object()
        serializer = NoteSaisieSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        created = 0
        updated = 0
        for item in serializer.validated_data:
            note, was_created = Note.objects.update_or_create(
                evaluation=evaluation,
                etudiant_id=item["etudiant_id"],
                defaults={
                    "valeur": item["valeur"],
                    "statut": item.get("statut", "presente"),
                    "appreciation": item.get("appreciation", ""),
                    "saisi_par": request.user,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
                note.modifie_le = timezone.now()
                note.modifie_par = request.user
                note.save(update_fields=["modifie_le", "modifie_par"])

        return Response(
            {
                "evaluation_id": evaluation.id,
                "notes_creees": created,
                "notes_modifiees": updated,
            }
        )

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques de l'évaluation."""
        evaluation = self.get_object()
        notes = evaluation.notes.filter(valeur__isnull=False)
        stats = notes.aggregate(
            moyenne=Avg("valeur"),
            nb_notes=Count("id"),
        )
        absents = evaluation.notes.filter(statut="absente").count()
        return Response(
            {
                "evaluation_id": evaluation.id,
                "moyenne": float(stats["moyenne"]) if stats["moyenne"] else None,
                "nb_notes": stats["nb_notes"],
                "nb_absents": absents,
                "bareme": float(evaluation.bareme),
            }
        )


class NotesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour notes."""

    permission_classes = [IsEnseignantOrScolarite]
    serializer_class = NoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["evaluation", "etudiant", "statut"]
    ordering = ["etudiant__user__last_name"]

    def get_queryset(self):
        qs = Note.objects.select_related("evaluation", "etudiant__user")
        # Un étudiant ne voit que ses propres notes
        user = self.request.user
        if hasattr(user, "etudiant_profile"):
            if not user.is_staff and getattr(user, "role", "") == "etudiant":
                qs = qs.filter(etudiant__user=user)
        if not user.is_staff and getattr(user, "role", "") in (
            "enseignant",
            "chercheur",
        ):
            qs = qs.filter(evaluation__enseignant=user)
        allowed_roles = {
            "president",
            "vice_president",
            "doyen",
            "directeur_dept",
            "responsable_formation",
            "directeur_etudes",
            "scolarite",
            "enseignant",
            "chercheur",
            "etudiant",
            "doctorant",
        }
        if (
            not user.is_staff
            and not user.has_perm("notes.view_note")
            and getattr(user, "role", "") not in allowed_roles
        ):
            return qs.none()
        return filter_queryset_by_scopes(
            qs,
            user,
            "notes.view_note",
            {
                "formations": "etudiant__inscriptions_admin__formation_id",
                "facultes": (
                    "etudiant__inscriptions_admin__formation__departement__faculte_id"
                ),
                "departements": (
                    "etudiant__inscriptions_admin__formation__departement_id"
                ),
                "annees": "evaluation__semestre__annee_universitaire_id",
                "semestres": "evaluation__semestre_id",
                "ues": "evaluation__ecue__ue_id",
                "ecues": "evaluation__ecue_id",
            },
        )

    @action(detail=False, methods=["get"])
    def bilan(self, request):
        group_by = request.query_params.get("group_by", "ecue")
        group_field = REPORT_GROUPS.get(group_by)
        if not group_field:
            return Response(
                {"group_by": f"Valeurs acceptées: {', '.join(REPORT_GROUPS)}."},
                status=400,
            )
        rows = (
            self.filter_queryset(self.get_queryset())
            .filter(valeur__isnull=False)
            .values(group_field)
            .annotate(moyenne=Avg("valeur"), nombre=Count("id"))
            .order_by(group_field)
        )
        return Response(
            [
                {
                    "groupe": row[group_field],
                    "moyenne": row["moyenne"],
                    "nombre": row["nombre"],
                }
                for row in rows
            ]
        )

    @action(detail=False, methods=["post"])
    def exporter(self, request):
        report = configured_report(request, request.data.get("report"))
        return export_queryset_csv(
            self.filter_queryset(self.get_queryset()),
            report,
            REPORT_FIELDS,
            REPORT_FILTERS,
            request.data.get("filters", {}),
        )


class MoyennesECUEViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet lecture seule pour moyennes ECUE."""

    permission_classes = [IsAuthenticated]
    serializer_class = MoyenneECUESerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["etudiant", "ecue", "semestre", "valide"]

    def get_queryset(self):
        qs = MoyenneECUE.objects.select_related("etudiant__user", "ecue", "semestre")
        user = self.request.user
        if hasattr(user, "etudiant_profile"):
            if not user.is_staff and getattr(user, "role", "") == "etudiant":
                qs = qs.filter(etudiant__user=user)
        return qs


class MoyennesUEViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet lecture seule pour moyennes UE."""

    permission_classes = [IsAuthenticated]
    serializer_class = MoyenneUESerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["etudiant", "ue", "semestre", "capitalisee"]

    def get_queryset(self):
        qs = MoyenneUE.objects.select_related("etudiant__user", "ue", "semestre")
        user = self.request.user
        if hasattr(user, "etudiant_profile"):
            if not user.is_staff and getattr(user, "role", "") == "etudiant":
                qs = qs.filter(etudiant__user=user)
        return qs


class ReglesValidationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAcademicAdmin]
    serializer_class = RegleValidationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["annee_universitaire", "formation", "semestre", "actif"]
    ordering = ["priorite", "code"]

    def get_queryset(self):
        return RegleValidation.objects.select_related(
            "annee_universitaire", "formation", "semestre"
        )

    @action(detail=True, methods=["post"])
    def evaluer(self, request, pk=None):
        serializer = EvaluationRegleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self.get_object().evaluer(**serializer.validated_data))


class EvaluationRegleInputSerializer(serializers.Serializer):
    moyenne = serializers.DecimalField(max_digits=7, decimal_places=2)
    credits = serializers.DecimalField(max_digits=7, decimal_places=2, default=0)
    ecues_echoues = serializers.IntegerField(min_value=0, default=0)
    note_minimale = serializers.DecimalField(
        max_digits=7, decimal_places=2, required=False, allow_null=True
    )
