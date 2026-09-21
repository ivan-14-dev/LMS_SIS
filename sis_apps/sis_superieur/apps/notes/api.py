"""API views for notes (ViewSets DRF) - SIS Supérieur."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Exists, OuterRef, Q
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
from sis_common.reporting import configured_report, export_queryset
from sis_common.spreadsheets import load_excel_rows, template_response
from sis_common.submission_windows import apply_submission_window_defaults

from apps.etudiants.models import AffectationECUEIndividuelle

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

NOTE_REPORT_FIELDS = {
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
    "parcours_individualise": ("Parcours individualisé", "parcours_individualise"),
}
NOTE_REPORT_FILTERS = {
    "annee": "evaluation__semestre__annee_universitaire_id",
    "formation": "etudiant__inscriptions_admin__formation_id",
    "ecue": "evaluation__ecue_id",
    "ue": "evaluation__ecue__ue_id",
    "enseignant": "evaluation__enseignant_id",
    "semestre": "evaluation__semestre_id",
    "statut": "statut",
}
NOTE_REPORT_GROUPS = {
    "formation": "etudiant__inscriptions_admin__formation__nom",
    "ecue": "evaluation__ecue__nom",
    "ue": "evaluation__ecue__ue__nom",
    "enseignant": "evaluation__enseignant__last_name",
    "semestre": "evaluation__semestre__numero",
}
EVALUATION_REPORT_FIELDS = {
    "titre": ("Titre", "titre"),
    "modalite": ("Modalité", "modalite"),
    "ecue": ("ECUE", "ecue__nom"),
    "ue": ("UE", "ecue__ue__nom"),
    "formation": ("Formation", "semestre__formation__nom"),
    "semestre": ("Semestre", "semestre__numero"),
    "enseignant": ("Enseignant", "enseignant__last_name"),
    "date": ("Date", "date"),
    "bareme": ("Barème", "bareme"),
    "coefficient": ("Coefficient", "coefficient"),
    "ponderation": ("Pondération", "ponderation"),
    "anonyme": ("Anonyme", "anonyme"),
}
EVALUATION_REPORT_FILTERS = {
    "ecue": "ecue_id",
    "ue": "ecue__ue_id",
    "semestre": "semestre_id",
    "formation": "semestre__formation_id",
    "modalite": "modalite",
    "enseignant": "enseignant_id",
    "anonyme": "anonyme",
}
ECUE_AVERAGE_REPORT_FIELDS = {
    "matricule": ("Matricule", "etudiant__matricule"),
    "etudiant": ("Étudiant", "etudiant__user__last_name"),
    "formation": ("Formation", "etudiant__inscriptions_admin__formation__nom"),
    "ecue": ("ECUE", "ecue__nom"),
    "ue": ("UE", "ecue__ue__nom"),
    "semestre": ("Semestre", "semestre__numero"),
    "moyenne": ("Moyenne", "moyenne"),
    "valide": ("Validé", "valide"),
    "parcours_individualise": ("Parcours individualisé", "parcours_individualise"),
}
ECUE_AVERAGE_REPORT_FILTERS = {
    "etudiant": "etudiant_id",
    "formation": "etudiant__inscriptions_admin__formation_id",
    "ecue": "ecue_id",
    "ue": "ecue__ue_id",
    "semestre": "semestre_id",
    "valide": "valide",
}
UE_AVERAGE_REPORT_FIELDS = {
    "matricule": ("Matricule", "etudiant__matricule"),
    "etudiant": ("Étudiant", "etudiant__user__last_name"),
    "formation": ("Formation", "etudiant__inscriptions_admin__formation__nom"),
    "ue": ("UE", "ue__nom"),
    "semestre": ("Semestre", "semestre__numero"),
    "moyenne": ("Moyenne", "moyenne"),
    "credits_obtenus": ("Crédits obtenus", "credits_obtenus"),
    "capitalisee": ("Capitalisée", "capitalisee"),
    "parcours_individualise": ("Parcours individualisé", "parcours_individualise"),
}
UE_AVERAGE_REPORT_FILTERS = {
    "etudiant": "etudiant_id",
    "formation": "etudiant__inscriptions_admin__formation_id",
    "ue": "ue_id",
    "semestre": "semestre_id",
    "capitalisee": "capitalisee",
}

CONTINUOUS_ASSESSMENT_IMPORT_COLUMNS = [
    "matricule",
    "note",
    "appreciation",
    "statut",
]
CONTINUOUS_ASSESSMENT_MODALITIES = {"cc", "tp", "projet"}


def _continuous_assessment_template_enabled(request):
    templates = (
        getattr(getattr(request, "tenant", None), "configuration_academique", {}) or {}
    ).get("import_templates", [])
    return any(template.get("code") == "continuous_assessment_grades" for template in templates)


def _ensure_submission_window(obj, label="La période de soumission"):
    now = timezone.now()
    if getattr(obj, "debut_soumission", None) and now < obj.debut_soumission:
        raise serializers.ValidationError(
            {"soumission": f"{label} n'est pas encore ouverte."}
        )
    if getattr(obj, "fin_soumission", None) and now > obj.fin_soumission:
        raise serializers.ValidationError({"soumission": f"{label} est expirée."})


def _ensure_superior_continuous_assessment(evaluation):
    if evaluation.modalite not in CONTINUOUS_ASSESSMENT_MODALITIES:
        raise serializers.ValidationError(
            {
                "evaluation": (
                    "Seules les évaluations de contrôle continu peuvent être importées ici."
                )
            }
        )
    _ensure_submission_window(evaluation)
    if evaluation.semestre.cloture or evaluation.semestre.annee_universitaire.cloturee:
        raise serializers.ValidationError(
            {
                "evaluation": (
                    "Cette évaluation est verrouillée car le semestre ou l'année est clôturé."
                )
            }
        )


def _superior_eligible_student_map(evaluation, matricules):
    enrollments = (
        evaluation.semestre.inscriptions_peda.filter(
            inscription_admin__etudiant__matricule__in=matricules,
            statut="validee",
        )
        .filter(Q(ecues=evaluation.ecue) | Q(ues=evaluation.ecue.ue))
        .select_related("inscription_admin__etudiant")
        .distinct()
    )
    eligible = {
        inscription.inscription_admin.etudiant.matricule: inscription.inscription_admin.etudiant
        for inscription in enrollments
    }
    custom_assignments = (
        AffectationECUEIndividuelle.objects.filter(
            inscription_admin__etudiant__matricule__in=matricules,
            inscription_admin__annee_universitaire=evaluation.semestre.annee_universitaire,
            ecue=evaluation.ecue,
        )
        .select_related("inscription_admin__etudiant")
        .distinct()
    )
    for affectation in custom_assignments:
        eligible[affectation.inscription_admin.etudiant.matricule] = (
            affectation.inscription_admin.etudiant
        )
    return eligible


def _import_superior_notes(evaluation, rows, request):
    _ensure_superior_continuous_assessment(evaluation)
    matricules = [str(row["matricule"]).strip() for row in rows]
    eligible_map = _superior_eligible_student_map(evaluation, matricules)
    created = 0
    updated = 0
    seen = set()
    valid_statuses = {code for code, _label in Note.STATUT_CHOICES}
    with transaction.atomic():
        for row in rows:
            row_number = row["__row_number__"]
            matricule = str(row["matricule"]).strip()
            if not matricule:
                raise serializers.ValidationError(
                    {"matricule": f"Ligne {row_number}: matricule requis."}
                )
            if matricule in seen:
                raise serializers.ValidationError(
                    {"file": f"Ligne {row_number}: doublon incohérent détecté pour {matricule}."}
                )
            seen.add(matricule)
            etudiant = eligible_map.get(matricule)
            if etudiant is None:
                raise serializers.ValidationError(
                    {
                        "file": (
                            f"Ligne {row_number}: étudiant hors périmètre pour cette évaluation."
                        )
                    }
                )
            statut = str(row.get("statut") or "presente").strip() or "presente"
            if statut not in valid_statuses:
                raise serializers.ValidationError(
                    {"statut": f"Ligne {row_number}: statut invalide."}
                )
            raw_note = row.get("note")
            valeur = None
            if raw_note not in (None, ""):
                try:
                    valeur = Decimal(str(raw_note))
                except (ArithmeticError, TypeError, ValueError):
                    raise serializers.ValidationError(
                        {"note": f"Ligne {row_number}: note invalide."}
                    )
                if valeur < 0 or valeur > evaluation.bareme:
                    raise serializers.ValidationError(
                        {"note": f"Ligne {row_number}: la note doit respecter le barème."}
                    )
            elif statut == "presente":
                raise serializers.ValidationError(
                    {"note": f"Ligne {row_number}: une note est requise pour une copie présentée."}
                )
            note, was_created = Note.objects.update_or_create(
                evaluation=evaluation,
                etudiant=etudiant,
                defaults={
                    "valeur": valeur,
                    "statut": statut,
                    "appreciation": str(row.get("appreciation") or "").strip(),
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
    return created, updated


class IsEnseignantOrScolarite(IsAuthenticated):
    """Permission: enseignant ou scolarité."""

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
            ("enseignant", "chercheur", "scolarite", "directeur_etudes"),
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
    permission_model = "evaluation"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["ecue", "semestre", "modalite", "enseignant", "anonyme"]
    search_fields = ["titre", "description"]
    ordering_fields = ["date", "titre", "created_at"]
    ordering = ["-date"]

    def get_queryset(self):
        qs = Evaluation.objects.select_related("ecue", "semestre", "enseignant")
        user = self.request.user
        if not user.is_staff and user_has_any_role(user, ("enseignant", "chercheur")):
            return qs.filter(enseignant=user)
        if not request_has_business_access(
            self.request,
            "notes.view_evaluation",
            ("president", "vice_president", "doyen", "directeur_etudes", "scolarite"),
        ):
            return qs.none()
        return filter_queryset_by_scopes(
            qs,
            user,
            "notes.view_evaluation",
            {
                "formations": "semestre__formation_id",
                "facultes": "semestre__formation__departement__faculte_id",
                "departements": "semestre__formation__departement_id",
                "annees": "semestre__annee_universitaire_id",
                "semestres": "semestre_id",
                "ues": "ecue__ue_id",
                "ecues": "ecue_id",
            },
        )

    def get_serializer_class(self):
        if self.action == "list":
            return EvaluationListSerializer
        return EvaluationDetailSerializer

    def perform_create(self, serializer):
        evaluation = serializer.save()
        changed_fields = apply_submission_window_defaults(
            evaluation,
            getattr(getattr(self.request, "tenant", None), "configuration_academique", {}) or {},
            "evaluation",
        )
        if changed_fields:
            evaluation.save(update_fields=changed_fields)

    def perform_update(self, serializer):
        evaluation = serializer.save()
        changed_fields = apply_submission_window_defaults(
            evaluation,
            getattr(getattr(self.request, "tenant", None), "configuration_academique", {}) or {},
            "evaluation",
        )
        if changed_fields:
            evaluation.save(update_fields=changed_fields)

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
        _ensure_superior_continuous_assessment(evaluation)
        serializer = NoteSaisieSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        student_ids = {item["etudiant_id"] for item in serializer.validated_data}
        eligible_student_ids = set(
            evaluation.semestre.inscriptions_peda.filter(
                inscription_admin__etudiant_id__in=student_ids,
                statut="validee",
            )
            .filter(Q(ecues=evaluation.ecue) | Q(ues=evaluation.ecue.ue))
            .values_list("inscription_admin__etudiant_id", flat=True)
        )
        eligible_student_ids.update(
            AffectationECUEIndividuelle.objects.filter(
                inscription_admin__etudiant_id__in=student_ids,
                inscription_admin__annee_universitaire=evaluation.semestre.annee_universitaire,
                ecue=evaluation.ecue,
            ).values_list("inscription_admin__etudiant_id", flat=True)
        )
        invalid_student_ids = sorted(student_ids - eligible_student_ids)
        if invalid_student_ids:
            raise serializers.ValidationError(
                {
                    "etudiant_id": f"Étudiants non inscrits à cette évaluation: {invalid_student_ids}."
                }
            )

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
    def modele_import_notes(self, request, pk=None):
        if not _continuous_assessment_template_enabled(request):
            raise serializers.ValidationError(
                {"workflow": "Le modèle d'import des notes de contrôle continu n'est pas activé."}
            )
        evaluation = self.get_object()
        _ensure_superior_continuous_assessment(evaluation)
        return template_response(
            CONTINUOUS_ASSESSMENT_IMPORT_COLUMNS,
            f"modele-notes-evaluation-superieur-{evaluation.pk}.xlsx",
            sample_row=["SUP-001", "15.25", "Bon travail", "presente"],
        )

    @action(detail=True, methods=["post"])
    def importer_notes(self, request, pk=None):
        if not _continuous_assessment_template_enabled(request):
            raise serializers.ValidationError(
                {"workflow": "Le modèle d'import des notes de contrôle continu n'est pas activé."}
            )
        evaluation = self.get_object()
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            raise serializers.ValidationError({"file": "Un fichier Excel est requis."})
        rows = load_excel_rows(uploaded_file, CONTINUOUS_ASSESSMENT_IMPORT_COLUMNS)
        if not rows:
            raise serializers.ValidationError(
                {"file": "Le fichier ne contient aucune ligne exploitable."}
            )
        created, updated = _import_superior_notes(evaluation, rows, request)
        return Response(
            {
                "evaluation_id": evaluation.id,
                "notes_creees": created,
                "notes_modifiees": updated,
            }
        )

    @action(detail=False, methods=["post"])
    def exporter(self, request):
        report = configured_report(request, request.data.get("report"), allowed_datasets={"evaluations"})
        return export_queryset(
            request,
            self.filter_queryset(self.get_queryset()),
            report,
            EVALUATION_REPORT_FIELDS,
            EVALUATION_REPORT_FILTERS,
            request.data.get("filters", {}),
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
    permission_model = "note"
    serializer_class = NoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["evaluation", "etudiant", "statut"]
    ordering = ["etudiant__user__last_name"]

    def get_queryset(self):
        individualized_assignments = AffectationECUEIndividuelle.objects.filter(
            inscription_admin__etudiant_id=OuterRef("etudiant_id"),
            inscription_admin__annee_universitaire_id=OuterRef(
                "evaluation__semestre__annee_universitaire_id"
            ),
            semestre_cible_id=OuterRef("evaluation__semestre_id"),
            ecue_id=OuterRef("evaluation__ecue_id"),
        )
        qs = Note.objects.select_related("evaluation", "etudiant__user").annotate(
            parcours_individualise=Exists(individualized_assignments)
        )
        user = self.request.user
        if not user.is_staff and user_has_any_role(user, ("etudiant", "doctorant")):
            return qs.filter(etudiant__user=user)
        if not user.is_staff and user_has_any_role(user, ("enseignant", "chercheur")):
            return qs.filter(evaluation__enseignant=user)
        if not request_has_business_access(
            self.request,
            "notes.view_note",
            ("president", "vice_president", "doyen", "directeur_dept", "responsable_formation", "directeur_etudes", "scolarite"),
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
        group_field = NOTE_REPORT_GROUPS.get(group_by)
        if not group_field:
            return Response(
                {"group_by": f"Valeurs acceptées: {', '.join(NOTE_REPORT_GROUPS)}."},
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
        report = configured_report(request, request.data.get("report"), allowed_datasets={"notes"})
        return export_queryset(
            request,
            self.filter_queryset(self.get_queryset()),
            report,
            NOTE_REPORT_FIELDS,
            NOTE_REPORT_FILTERS,
            request.data.get("filters", {}),
        )

    def perform_create(self, serializer):
        evaluation = serializer.validated_data["evaluation"]
        _ensure_superior_continuous_assessment(evaluation)
        serializer.save(saisi_par=self.request.user)

    def perform_update(self, serializer):
        note = self.get_object()
        _ensure_superior_continuous_assessment(note.evaluation)
        serializer.save(modifie_le=timezone.now(), modifie_par=self.request.user)


class MoyennesECUEViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet lecture seule pour moyennes ECUE."""

    permission_classes = [IsAuthenticated]
    serializer_class = MoyenneECUESerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["etudiant", "ecue", "semestre", "valide"]

    def get_queryset(self):
        individualized_assignments = AffectationECUEIndividuelle.objects.filter(
            inscription_admin__etudiant_id=OuterRef("etudiant_id"),
            inscription_admin__annee_universitaire_id=OuterRef("semestre__annee_universitaire_id"),
            semestre_cible_id=OuterRef("semestre_id"),
            ecue_id=OuterRef("ecue_id"),
        )
        qs = MoyenneECUE.objects.select_related("etudiant__user", "ecue", "semestre").annotate(
            parcours_individualise=Exists(individualized_assignments)
        )
        user = self.request.user
        if not user.is_staff and user_has_any_role(user, ("etudiant", "doctorant")):
            return qs.filter(etudiant__user=user)
        if not request_has_business_access(
            self.request,
            "notes.view_moyenneecue",
            ("president", "vice_president", "doyen", "directeur_etudes", "scolarite"),
        ):
            return qs.none()
        return filter_queryset_by_scopes(
            qs,
            user,
            "notes.view_moyenneecue",
            {
                "formations": "etudiant__inscriptions_admin__formation_id",
                "facultes": "etudiant__inscriptions_admin__formation__departement__faculte_id",
                "departements": "etudiant__inscriptions_admin__formation__departement_id",
                "annees": "semestre__annee_universitaire_id",
                "semestres": "semestre_id",
                "ecues": "ecue_id",
                "ues": "ecue__ue_id",
            },
        )

    @action(detail=False, methods=["post"])
    def exporter(self, request):
        report = configured_report(request, request.data.get("report"), allowed_datasets={"averages_ecue"})
        return export_queryset(
            request,
            self.filter_queryset(self.get_queryset()),
            report,
            ECUE_AVERAGE_REPORT_FIELDS,
            ECUE_AVERAGE_REPORT_FILTERS,
            request.data.get("filters", {}),
        )


class MoyennesUEViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet lecture seule pour moyennes UE."""

    permission_classes = [IsAuthenticated]
    serializer_class = MoyenneUESerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["etudiant", "ue", "semestre", "capitalisee"]

    def get_queryset(self):
        individualized_assignments = AffectationECUEIndividuelle.objects.filter(
            inscription_admin__etudiant_id=OuterRef("etudiant_id"),
            inscription_admin__annee_universitaire_id=OuterRef("semestre__annee_universitaire_id"),
            semestre_cible_id=OuterRef("semestre_id"),
            ecue__ue_id=OuterRef("ue_id"),
        )
        qs = MoyenneUE.objects.select_related("etudiant__user", "ue", "semestre").annotate(
            parcours_individualise=Exists(individualized_assignments)
        )
        user = self.request.user
        if not user.is_staff and user_has_any_role(user, ("etudiant", "doctorant")):
            return qs.filter(etudiant__user=user)
        if not request_has_business_access(
            self.request,
            "notes.view_moyenneue",
            ("president", "vice_president", "doyen", "directeur_etudes", "scolarite"),
        ):
            return qs.none()
        return filter_queryset_by_scopes(
            qs,
            user,
            "notes.view_moyenneue",
            {
                "formations": "etudiant__inscriptions_admin__formation_id",
                "facultes": "etudiant__inscriptions_admin__formation__departement__faculte_id",
                "departements": "etudiant__inscriptions_admin__formation__departement_id",
                "annees": "semestre__annee_universitaire_id",
                "semestres": "semestre_id",
                "ues": "ue_id",
            },
        )

    @action(detail=False, methods=["post"])
    def exporter(self, request):
        report = configured_report(request, request.data.get("report"), allowed_datasets={"averages_ue"})
        return export_queryset(
            request,
            self.filter_queryset(self.get_queryset()),
            report,
            UE_AVERAGE_REPORT_FIELDS,
            UE_AVERAGE_REPORT_FILTERS,
            request.data.get("filters", {}),
        )


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
        rule = self.get_object()
        policy = resolve_validation_policy(
            getattr(request.tenant, "configuration_academique", {}),
            [
                {"scope": "semester", "context": {"semester_id": rule.semestre_id}},
                {"scope": "formation", "context": {"formation_id": rule.formation_id}},
                {"scope": "academic_year", "context": {"academic_year_id": rule.annee_universitaire_id}},
                {"scope": "tenant", "context": {"tenant_id": getattr(request.tenant, "id", None)}},
            ],
        )
        return Response(rule.evaluer(**serializer.validated_data, policy=policy))


class EvaluationRegleInputSerializer(serializers.Serializer):
    moyenne = serializers.DecimalField(max_digits=7, decimal_places=2)
    credits = serializers.DecimalField(max_digits=7, decimal_places=2, default=0)
    ecues_echoues = serializers.IntegerField(min_value=0, default=0)
    note_minimale = serializers.DecimalField(
        max_digits=7, decimal_places=2, required=False, allow_null=True
    )
    donnees = serializers.JSONField(default=dict)
