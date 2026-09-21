"""API views for notes (ViewSets DRF) - SIS Secondaire."""

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
    request_has_business_access,
    user_has_any_role,
)
from sis_common.academic_configuration import resolve_validation_policy
from sis_common.reporting import configured_report, export_queryset_csv
from sis_common.document_policies import enforce_financial_clearance, get_action_object

from .models import Bulletin, Evaluation, Note, RegleValidation
from .serializers import (
    BulletinDetailSerializer,
    BulletinListSerializer,
    EvaluationDetailSerializer,
    EvaluationListSerializer,
    NoteSaisieSerializer,
    NoteSerializer,
    RegleValidationSerializer,
)

REPORT_FIELDS = {
    "matricule": ("Matricule", "eleve__matricule"),
    "eleve": ("Élève", "eleve__user__last_name"),
    "classe": ("Classe", "evaluation__classe__nom"),
    "matiere": ("Matière", "evaluation__matiere__nom"),
    "evaluation": ("Évaluation", "evaluation__titre"),
    "note": ("Note", "valeur"),
    "bareme": ("Barème", "evaluation__bareme"),
    "appreciation": ("Appréciation", "appreciation"),
    "enseignant": ("Enseignant", "evaluation__enseignant__user__last_name"),
    "periode": ("Période", "evaluation__periode__libelle"),
    "date": ("Date", "evaluation__date"),
}
REPORT_FILTERS = {
    "annee": "evaluation__classe__annee_scolaire_id",
    "classe": "evaluation__classe_id",
    "matiere": "evaluation__matiere_id",
    "enseignant": "evaluation__enseignant_id",
    "periode": "evaluation__periode_id",
    "statut": "statut",
}
REPORT_GROUPS = {
    "classe": "evaluation__classe__nom",
    "matiere": "evaluation__matiere__nom",
    "enseignant": "evaluation__enseignant__user__last_name",
    "periode": "evaluation__periode__libelle",
}


class IsEnseignantOrVieScolarite(IsAuthenticated):
    """Permission: enseignant ou vie scolaire."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        model_name = getattr(view, "permission_model", "note")
        action_name = {
            "create": "add",
            "destroy": "delete",
        }.get(view.action, "change")
        return has_business_permission_or_role(
            user,
            f"notes.{action_name}_{model_name}",
            ("enseignant", "vie_scolaire", "direction", "responsable_pedagogique"),
        )


class IsAcademicAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(
            request, view
        ) and has_business_permission_or_role(
            request.user,
            "notes.change_reglevalidation",
            ("direction", "responsable_pedagogique", "vie_scolaire"),
        )


class EvaluationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour évaluations."""

    permission_classes = [IsEnseignantOrVieScolarite]
    permission_model = "evaluation"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["matiere", "classe", "periode", "type", "enseignant"]
    search_fields = ["titre", "description"]
    ordering_fields = ["date", "titre", "created_at"]
    ordering = ["-date"]

    def get_queryset(self):
        qs = Evaluation.objects.select_related(
            "matiere", "classe", "periode", "enseignant__user"
        )
        user = self.request.user
        if not user.is_staff and user_has_any_role(user, ("enseignant",)):
            if hasattr(user, "personnel_profile"):
                return qs.filter(enseignant=user.personnel_profile)
            return qs.none()
        if request_has_business_access(
            self.request,
            "notes.view_evaluation",
            ("direction", "responsable_pedagogique", "vie_scolaire"),
        ):
            return filter_queryset_by_scopes(
                qs,
                user,
                "notes.view_evaluation",
                {
                    "classes": "classe_id",
                    "matieres": "matiere_id",
                    "annees": "classe__annee_scolaire_id",
                    "periodes": "periode_id",
                },
            )
        return qs.none()

    def get_serializer_class(self):
        if self.action == "list":
            return EvaluationListSerializer
        return EvaluationDetailSerializer

    @action(detail=True, methods=["get"])
    def notes(self, request, pk=None):
        """Liste les notes d'une évaluation."""
        evaluation = self.get_object()
        notes = evaluation.notes.select_related("eleve__user").order_by(
            "eleve__user__last_name"
        )
        serializer = NoteSerializer(notes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def saisir_notes(self, request, pk=None):
        """Saisie en masse des notes."""
        evaluation = self.get_object()
        serializer = NoteSaisieSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        student_ids = {item["eleve_id"] for item in serializer.validated_data}
        eligible_student_ids = set(
            evaluation.classe.eleves_actuels.filter(pk__in=student_ids).values_list(
                "pk", flat=True
            )
        )
        eligible_student_ids.update(
            evaluation.classe.inscriptions.filter(
                eleve_id__in=student_ids,
                statut__in=("en_cours", "validee"),
            ).values_list("eleve_id", flat=True)
        )
        invalid_student_ids = sorted(student_ids - eligible_student_ids)
        if invalid_student_ids:
            raise serializers.ValidationError(
                {
                    "eleve_id": f"Élèves non inscrits dans cette classe: {invalid_student_ids}."
                }
            )

        created = 0
        updated = 0
        saisi_par = None
        if hasattr(request.user, "personnel_profile"):
            saisi_par = request.user.personnel_profile

        for item in serializer.validated_data:
            note, was_created = Note.objects.update_or_create(
                evaluation=evaluation,
                eleve_id=item["eleve_id"],
                defaults={
                    "valeur": item["valeur"],
                    "statut": item.get("statut", "presente"),
                    "appreciation": item.get("appreciation", ""),
                    "saisi_par": saisi_par,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
                note.modifie_le = timezone.now()
                note.modifie_par = saisi_par
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

    permission_classes = [IsEnseignantOrVieScolarite]
    permission_model = "note"
    serializer_class = NoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["evaluation", "eleve", "statut"]
    ordering = ["eleve__user__last_name"]

    def get_queryset(self):
        qs = Note.objects.select_related("evaluation", "eleve__user")
        user = self.request.user
        if hasattr(user, "eleve_profile"):
            if not user.is_staff and user_has_any_role(user, ("eleve",)):
                return qs.filter(eleve__user=user)
        if (
            not user.is_staff
            and user_has_any_role(user, ("enseignant",))
            and hasattr(user, "personnel_profile")
        ):
            return qs.filter(evaluation__enseignant=user.personnel_profile)
        if hasattr(user, "tuteur_profile"):
            from apps.eleves.models import EleveTuteur

            eleves_ids = EleveTuteur.objects.filter(
                tuteur=user.tuteur_profile, autorise_acces_portail=True
            ).values_list("eleve_id", flat=True)
            return qs.filter(eleve_id__in=eleves_ids)
        if not request_has_business_access(
            self.request,
            "notes.view_note",
            ("direction", "responsable_pedagogique", "vie_scolaire"),
        ):
            return qs.none()
        return filter_queryset_by_scopes(
            qs,
            user,
            "notes.view_note",
            {
                "classes": "evaluation__classe_id",
                "matieres": "evaluation__matiere_id",
                "annees": "evaluation__classe__annee_scolaire_id",
                "periodes": "evaluation__periode_id",
            },
        )

    @action(detail=False, methods=["get"])
    def bilan(self, request):
        group_by = request.query_params.get("group_by", "matiere")
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


class BulletinsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour bulletins."""

    permission_classes = [IsEnseignantOrVieScolarite]
    permission_model = "bulletin"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["eleve", "classe", "periode", "publie"]
    ordering = ["-periode__date_fin"]

    def get_queryset(self):
        qs = Bulletin.objects.select_related("eleve__user", "classe", "periode")
        user = self.request.user
        if hasattr(user, "eleve_profile"):
            if not user.is_staff and user_has_any_role(user, ("eleve",)):
                return qs.filter(eleve__user=user, publie=True)
        if hasattr(user, "tuteur_profile"):
            from apps.eleves.models import EleveTuteur

            eleves_ids = EleveTuteur.objects.filter(
                tuteur=user.tuteur_profile, autorise_acces_portail=True
            ).values_list("eleve_id", flat=True)
            return qs.filter(eleve_id__in=eleves_ids, publie=True)
        if not user.is_staff and user_has_any_role(user, ("enseignant",)) and hasattr(
            user, "personnel_profile"
        ):
            return qs.filter(classe__prof_principal=user.personnel_profile)
        if not request_has_business_access(
            self.request,
            "notes.view_bulletin",
            ("direction", "responsable_pedagogique", "vie_scolaire"),
        ):
            return qs.none()
        return filter_queryset_by_scopes(
            qs,
            user,
            "notes.view_bulletin",
            {
                "classes": "classe_id",
                "annees": "classe__annee_scolaire_id",
                "periodes": "periode_id",
            },
        )

    def get_serializer_class(self):
        if self.action == "list":
            return BulletinListSerializer
        return BulletinDetailSerializer

    @action(detail=True, methods=["post"])
    @enforce_financial_clearance(
        candidates_getter=lambda _view, request, bulletin: [
            {"scope": "class", "context": {"class_id": bulletin.classe_id}},
            {"scope": "level", "context": {"level_id": bulletin.classe.niveau_id}},
            {"scope": "academic_year", "context": {"academic_year_id": bulletin.classe.annee_scolaire_id}},
            {"scope": "tenant", "context": {"tenant_id": getattr(request.tenant, "id", None)}},
        ],
        subject_getter=lambda _view, _request, bulletin: bulletin.eleve,
        academic_year_ids_getter=lambda _view, _request, bulletin: [bulletin.classe.annee_scolaire_id],
        invoice_model_label="paiements.Facture",
        invoice_subject_field="eleve",
        invoice_year_lookup="type_frais__annee_scolaire_id",
        message="La publication du bulletin exige une situation financière régularisée.",
    )
    def publier(self, request, pk=None):
        """Publie un bulletin."""
        bulletin = get_action_object(self)
        if bulletin.publie:
            return Response({"error": "Ce bulletin est déjà publié."}, status=400)
        bulletin.publie = True
        bulletin.date_publication = timezone.now()
        bulletin.save(update_fields=["publie", "date_publication", "updated_at"])
        return Response({"detail": "Bulletin publié.", "id": bulletin.id})

    @action(detail=True, methods=["post"])
    def signer(self, request, pk=None):
        """Signe un bulletin (par le chef d'établissement)."""
        bulletin = self.get_object()
        if bulletin.signe:
            return Response({"error": "Ce bulletin est déjà signé."}, status=400)
        bulletin.signe = True
        bulletin.date_signature = timezone.now()
        bulletin.save(update_fields=["signe", "date_signature", "updated_at"])
        return Response({"detail": "Bulletin signé.", "id": bulletin.id})


class ReglesValidationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAcademicAdmin]
    serializer_class = RegleValidationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["annee_scolaire", "niveau", "classe", "actif"]
    ordering = ["priorite", "code"]

    def get_queryset(self):
        return RegleValidation.objects.select_related(
            "annee_scolaire", "niveau", "classe"
        )

    @action(detail=True, methods=["post"])
    def evaluer(self, request, pk=None):
        serializer = EvaluationRegleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = self.get_object()
        policy = resolve_validation_policy(
            getattr(request.tenant, "configuration_academique", {}),
            [
                {"scope": "class", "context": {"class_id": rule.classe_id}},
                {"scope": "level", "context": {"level_id": rule.niveau_id}},
                {"scope": "academic_year", "context": {"academic_year_id": rule.annee_scolaire_id}},
                {"scope": "tenant", "context": {"tenant_id": getattr(request.tenant, "id", None)}},
            ],
        )
        return Response(rule.evaluer(**serializer.validated_data, policy=policy))


class EvaluationRegleInputSerializer(serializers.Serializer):
    moyenne = serializers.DecimalField(max_digits=7, decimal_places=2)
    credits = serializers.DecimalField(max_digits=7, decimal_places=2, default=0)
    matieres_echouees = serializers.IntegerField(min_value=0, default=0)
    note_minimale = serializers.DecimalField(
        max_digits=7, decimal_places=2, required=False, allow_null=True
    )
    donnees = serializers.JSONField(default=dict)
