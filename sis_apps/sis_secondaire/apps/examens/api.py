"""API views for examens (ViewSets DRF) - SIS Secondaire."""

from datetime import timedelta
from decimal import Decimal

from apps.core.serializers import WorkflowEventSerializer
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
from sis_common.academic_configuration import resolve_exam_result_workflow
from sis_common.authorization import (
    request_has_business_access,
    user_has_any_role,
    user_in_configured_groups,
)
from sis_common.reporting import configured_report, export_queryset
from sis_common.spreadsheets import load_excel_rows, template_response
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

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


RESULT_EXPORT_FIELDS = {
    "session": ("Session", "epreuve__session__nom"),
    "matiere": ("Matière", "epreuve__matiere__nom"),
    "classe": ("Classe", "epreuve__classes__nom"),
    "matricule": ("Matricule", "eleve__matricule"),
    "eleve": ("Élève", "eleve__user__last_name"),
    "note": ("Note", "note"),
    "appreciation": ("Appréciation", "appreciation"),
    "statut": ("Statut", "statut"),
    "type_resultat": ("Type de résultat", "type_resultat"),
    "admis": ("Admis", "admis"),
    "mention": ("Mention", "mention"),
    "publie_le": ("Publié le", "publie_le"),
}

RESULT_EXPORT_FILTERS = {
    "annee": "epreuve__session__annee_scolaire_id",
    "session": "epreuve__session_id",
    "classe": "epreuve__classes__id",
    "matiere": "epreuve__matiere_id",
    "statut": "statut",
    "type_resultat": "type_resultat",
}

RESULT_IMPORT_COLUMNS = [
    "epreuve_id",
    "eleve_matricule",
    "note",
    "appreciation",
    "type_resultat",
]


def _exam_configuration(request):
    return getattr(getattr(request, "tenant", None), "configuration_academique", {}) or {}


def _exam_result_workflow(request, epreuve=None):
    academic_year_id = getattr(getattr(epreuve, "session", None), "annee_scolaire_id", None)
    candidates = [
        {"scope": "academic_year", "context": {"academic_year_id": academic_year_id}},
        {"scope": "tenant", "context": {"tenant_id": getattr(getattr(request, "tenant", None), "id", None)}},
    ]
    return resolve_exam_result_workflow(
        _exam_configuration(request),
        candidates,
        variant="secondaire",
    ) or {}


def _workflow_group_codes(workflow, key):
    return tuple(workflow.get(key) or ("exam_manager_secondary",))


def _configured_result_group_codes(configuration):
    group_codes = {"exam_manager_secondary"}
    for workflow in configuration.get("exam_result_workflows", []):
        for key in (
            "verification_group_codes",
            "validation_group_codes",
            "publication_group_codes",
        ):
            group_codes.update(workflow.get(key, []))
    return tuple(sorted(group_codes))


def _exam_notification_recipients(request):
    actor = getattr(request, "user", None)
    return [actor] if getattr(actor, "is_authenticated", False) else []


def _ensure_workflow_access(request, workflow, key):
    if request.user.is_staff or request.user.is_superuser:
        return
    configuration = _exam_configuration(request)
    allowed = user_in_configured_groups(
        request.user,
        configuration=configuration,
        group_codes=_workflow_group_codes(workflow, key),
    ) or request_has_business_access(
        request,
        "examens.change_resultatexamen",
        ("direction", "responsable_pedagogique", "vie_scolaire"),
        tenant_group_codes=_workflow_group_codes(workflow, key),
    )
    if not allowed:
        raise ValidationError({"workflow": "Vous n'êtes pas autorisé pour cette étape."})


def _ensure_result_mutable(result, workflow):
    if result.statut in ("validated", "published", "closed"):
        raise ValidationError(
            {"workflow": "Le résultat est verrouillé. Réouvrez-le explicitement avant modification."}
        )
    if result.statut == "reopened":
        days = workflow.get("correction_window_days", 0)
        if days and result.reouvert_le and timezone.now() > result.reouvert_le + timedelta(days=days):
            raise ValidationError({"workflow": "La fenêtre de réouverture est expirée."})


def _ensure_entry_allowed(epreuve, type_resultat, workflow):
    session = epreuve.session
    if session.cloturee or session.annee_scolaire.cloturee:
        allow_retake = workflow.get("allow_retake_after_closure", False)
        if not (allow_retake and type_resultat == "retake"):
            raise ValidationError(
                {"workflow": "La session ou l'année est clôturée; seules les saisies de rattrapage autorisées restent possibles."}
            )


def _apply_result_outcome(result, pass_mark):
    if result.note is None:
        result.admis = False
        result.mention = ""
        return
    result.admis = result.note >= pass_mark
    if result.note >= Decimal("16"):
        result.mention = "Très bien"
    elif result.note >= Decimal("14"):
        result.mention = "Bien"
    elif result.note >= Decimal("12"):
        result.mention = "Assez bien"
    elif result.note >= pass_mark:
        result.mention = "Passable"
    else:
        result.mention = ""


def _set_result_status(result, statut, user, pass_mark):
    now = timezone.now()
    fields = ["statut", "updated_at"]
    result.statut = statut
    if statut == "submitted":
        result.saisi_par = user
        result.saisi_le = now
        fields.extend(["saisi_par", "saisi_le"])
    elif statut == "verified":
        result.verifie_par = user
        result.verifie_le = now
        fields.extend(["verifie_par", "verifie_le"])
    elif statut == "validated":
        result.valide_par = user
        result.valide_le = now
        fields.extend(["valide_par", "valide_le"])
    elif statut == "published":
        result.publie_par = user
        result.publie_le = now
        _apply_result_outcome(result, pass_mark)
        fields.extend(["publie_par", "publie_le", "admis", "mention"])
    elif statut == "reopened":
        result.reouvert_par = user
        result.reouvert_le = now
        fields.extend(["reouvert_par", "reouvert_le"])
    elif statut == "closed":
        result.cloture_par = user
        result.cloture_le = now
        fields.extend(["cloture_par", "cloture_le"])
    result.save(update_fields=fields)


def _pass_mark(request):
    grading_scale = _exam_configuration(request).get("grading_scale", {})
    return Decimal(str(grading_scale.get("pass_mark", 10)))


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

    def perform_create(self, serializer):
        session = serializer.save()
        record_workflow_event(
            self.request,
            session,
            "creation",
            "Session d'examen créée",
            message=f"La session d'examen {session.nom} a été créée.",
            recipients=_exam_notification_recipients(self.request),
            metadata={"annee_scolaire_id": session.annee_scolaire_id, "type": session.type},
        )

    def perform_update(self, serializer):
        session = serializer.save()
        record_workflow_event(
            self.request,
            session,
            "mise_a_jour",
            "Session d'examen mise à jour",
            message=f"La session d'examen {session.nom} a été mise à jour.",
            recipients=_exam_notification_recipients(self.request),
            metadata={"annee_scolaire_id": session.annee_scolaire_id, "type": session.type},
        )

    def perform_destroy(self, instance):
        record_workflow_event(
            self.request,
            instance,
            "suppression",
            "Session d'examen supprimée",
            message=f"La session d'examen {instance.nom} a été supprimée.",
            recipients=_exam_notification_recipients(self.request),
            metadata={"annee_scolaire_id": instance.annee_scolaire_id, "type": instance.type},
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def epreuves(self, request, pk=None):
        """Liste les épreuves de la session."""
        session = self.get_object()
        epreuves = session.epreuves.select_related("matiere").order_by(
            "date", "heure_debut"
        )
        serializer = EpreuveExamenListSerializer(epreuves, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        session = self.get_object()
        if session.cloturee:
            return Response({"error": "Cette session est déjà clôturée."}, status=400)
        session.cloturee = True
        session.save(update_fields=["cloturee"])
        record_workflow_event(
            request,
            session,
            "cloture",
            "Session d'examen clôturée",
            message=f"La session d'examen {session.nom} a été clôturée.",
            recipients=_exam_notification_recipients(request),
            metadata={"annee_scolaire_id": session.annee_scolaire_id, "type": session.type},
        )
        return Response({"detail": "Session clôturée.", "id": session.id})

    @action(detail=True, methods=["post"])
    def reouvrir(self, request, pk=None):
        session = self.get_object()
        if not session.cloturee:
            return Response({"error": "Cette session est déjà ouverte."}, status=400)
        session.cloturee = False
        session.save(update_fields=["cloturee"])
        record_workflow_event(
            request,
            session,
            "reouverture",
            "Session d'examen rouverte",
            message=f"La session d'examen {session.nom} a été rouverte.",
            recipients=_exam_notification_recipients(request),
            metadata={"annee_scolaire_id": session.annee_scolaire_id, "type": session.type},
        )
        return Response({"detail": "Session rouverte.", "id": session.id})

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow de la session."""
        session = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(session), many=True)
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

    def perform_create(self, serializer):
        epreuve = serializer.save()
        record_workflow_event(
            self.request,
            epreuve,
            "creation",
            "Épreuve créée",
            message=f"L'épreuve {epreuve} a été créée.",
            recipients=_exam_notification_recipients(self.request),
            metadata={"session_id": epreuve.session_id, "matiere_id": epreuve.matiere_id},
        )

    def perform_update(self, serializer):
        epreuve = serializer.save()
        record_workflow_event(
            self.request,
            epreuve,
            "mise_a_jour",
            "Épreuve mise à jour",
            message=f"L'épreuve {epreuve} a été mise à jour.",
            recipients=_exam_notification_recipients(self.request),
            metadata={"session_id": epreuve.session_id, "matiere_id": epreuve.matiere_id},
        )

    def perform_destroy(self, instance):
        record_workflow_event(
            self.request,
            instance,
            "suppression",
            "Épreuve supprimée",
            message=f"L'épreuve {instance} a été supprimée.",
            recipients=_exam_notification_recipients(self.request),
            metadata={"session_id": instance.session_id, "matiere_id": instance.matiere_id},
        )
        instance.delete()

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

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow de l'épreuve."""
        epreuve = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(epreuve), many=True)
        return Response(serializer.data)


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
    filterset_fields = ["epreuve", "eleve", "admis", "statut", "type_resultat"]
    ordering = ["-note"]

    def get_permissions(self):
        if self.action in {
            "importer",
            "modele_import",
            "soumettre",
            "verifier",
            "valider",
            "publier",
            "reouvrir",
            "cloturer",
            "exporter",
        }:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = ResultatExamen.objects.select_related(
            "epreuve__session__annee_scolaire",
            "epreuve__matiere",
            "eleve__user",
        )
        user = self.request.user
        configuration = _exam_configuration(self.request)
        if request_has_business_access(
            self.request,
            "examens.view_resultatexamen",
            ("direction", "responsable_pedagogique", "vie_scolaire"),
            tenant_group_codes=_configured_result_group_codes(configuration),
        ):
            return queryset
        if user_has_any_role(user, ("eleve",)):
            return queryset.filter(eleve__user=user, statut="published")
        if user_has_any_role(user, ("parent",)):
            return queryset.filter(
                eleve__tuteurs_lies__tuteur__user=user,
                eleve__tuteurs_lies__autorise_acces_portail=True,
                statut="published",
            ).distinct()
        return queryset.none()

    def perform_create(self, serializer):
        epreuve = serializer.validated_data["epreuve"]
        workflow = _exam_result_workflow(self.request, epreuve)
        type_resultat = serializer.validated_data.get("type_resultat", "normal")
        _ensure_entry_allowed(epreuve, type_resultat, workflow)
        serializer.save(
            saisi_par=self.request.user,
            saisi_le=timezone.now(),
            statut="draft",
        )

    def perform_update(self, serializer):
        result = self.get_object()
        workflow = _exam_result_workflow(self.request, result.epreuve)
        _ensure_result_mutable(result, workflow)
        type_resultat = serializer.validated_data.get("type_resultat", result.type_resultat)
        _ensure_entry_allowed(result.epreuve, type_resultat, workflow)
        serializer.save()

    def perform_destroy(self, instance):
        workflow = _exam_result_workflow(self.request, instance.epreuve)
        _ensure_result_mutable(instance, workflow)
        instance.delete()

    @action(detail=False, methods=["post"])
    def exporter(self, request):
        report = configured_report(
            request,
            request.data.get("report"),
            allowed_datasets={"exam_results"},
        )
        return export_queryset(
            request,
            self.filter_queryset(self.get_queryset()),
            report,
            RESULT_EXPORT_FIELDS,
            RESULT_EXPORT_FILTERS,
            request.data.get("filters", {}),
        )

    @action(detail=False, methods=["get"])
    def modele_import(self, request):
        workflow = _exam_result_workflow(request)
        _ensure_workflow_access(request, workflow, "verification_group_codes")
        if "exam_grades" not in workflow.get("import_template_codes", ["exam_grades"]):
            raise ValidationError({"workflow": "Le modèle d'import des notes d'examen n'est pas activé."})
        return template_response(
            RESULT_IMPORT_COLUMNS,
            "modele-resultats-examen.xlsx",
            sample_row=["123", "MAT-001", "14.5", "Bonne copie", "normal"],
        )

    @action(detail=False, methods=["post"])
    def importer(self, request):
        workflow = _exam_result_workflow(request)
        _ensure_workflow_access(request, workflow, "verification_group_codes")
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            raise ValidationError({"file": "Un fichier Excel est requis."})
        rows = load_excel_rows(uploaded_file, RESULT_IMPORT_COLUMNS)
        if not rows:
            raise ValidationError({"file": "Le fichier ne contient aucune ligne exploitable."})
        epreuve_ids = set()
        for row in rows:
            try:
                epreuve_ids.add(int(row["epreuve_id"]))
            except (TypeError, ValueError):
                raise ValidationError(
                    {"epreuve_id": f"Ligne {row['__row_number__']}: identifiant d'épreuve invalide."}
                )
        matricules = {str(row["eleve_matricule"]).strip() for row in rows}
        convocations = ConvocationExamen.objects.select_related(
            "epreuve__session__annee_scolaire", "eleve"
        ).filter(epreuve_id__in=epreuve_ids, eleve__matricule__in=matricules)
        convocation_map = {
            (convocation.epreuve_id, convocation.eleve.matricule): convocation for convocation in convocations
        }
        seen = {}
        created = updated = 0
        pass_mark = _pass_mark(request)
        with transaction.atomic():
            for row in rows:
                row_number = row.pop("__row_number__")
                try:
                    epreuve_id = int(row["epreuve_id"])
                except (TypeError, ValueError):
                    raise ValidationError({"epreuve_id": f"Ligne {row_number}: identifiant d'épreuve invalide."})
                matricule = str(row["eleve_matricule"]).strip()
                key = (epreuve_id, matricule)
                if key in seen:
                    if seen[key] != row:
                        raise ValidationError({"file": f"Ligne {row_number}: doublon incohérent détecté pour {matricule}."})
                    continue
                seen[key] = row.copy()
                convocation = convocation_map.get(key)
                if convocation is None:
                    raise ValidationError(
                        {"file": f"Ligne {row_number}: apprenant hors périmètre pour cette épreuve."}
                    )
                workflow = _exam_result_workflow(request, convocation.epreuve)
                _ensure_workflow_access(request, workflow, "verification_group_codes")
                result_type = str(row.get("type_resultat") or "normal").strip().lower()
                if result_type not in {"normal", "retake"}:
                    raise ValidationError({"type_resultat": f"Ligne {row_number}: type de résultat invalide."})
                _ensure_entry_allowed(convocation.epreuve, result_type, workflow)
                try:
                    note = Decimal(str(row["note"]))
                except (ArithmeticError, TypeError, ValueError):
                    raise ValidationError({"note": f"Ligne {row_number}: note invalide."})
                if note < 0 or note > convocation.epreuve.bareme:
                    raise ValidationError({"note": f"Ligne {row_number}: la note doit respecter le barème."})
                result, was_created = ResultatExamen.objects.select_for_update().get_or_create(
                    epreuve=convocation.epreuve,
                    eleve=convocation.eleve,
                    defaults={
                        "numero_anonyme": getattr(getattr(convocation, "copie", None), "numero_anonyme", ""),
                    },
                )
                if not was_created:
                    _ensure_result_mutable(result, workflow)
                result.note = note
                result.appreciation = str(row.get("appreciation") or "").strip()
                result.type_resultat = result_type
                result.numero_anonyme = result.numero_anonyme or getattr(
                    getattr(convocation, "copie", None), "numero_anonyme", ""
                )
                result.saisi_par = request.user
                result.saisi_le = timezone.now()
                _apply_result_outcome(result, pass_mark)
                result.statut = "submitted"
                result.save()
                created += int(was_created)
                updated += int(not was_created)
        return Response({"resultats_crees": created, "resultats_mis_a_jour": updated})

    @action(detail=True, methods=["post"])
    def soumettre(self, request, pk=None):
        result = self.get_object()
        workflow = _exam_result_workflow(request, result.epreuve)
        _ensure_workflow_access(request, workflow, "verification_group_codes")
        _ensure_entry_allowed(result.epreuve, result.type_resultat, workflow)
        _ensure_result_mutable(result, workflow)
        _set_result_status(result, "submitted", request.user, _pass_mark(request))
        return Response(self.get_serializer(result).data)

    @action(detail=True, methods=["post"])
    def verifier(self, request, pk=None):
        result = self.get_object()
        workflow = _exam_result_workflow(request, result.epreuve)
        _ensure_workflow_access(request, workflow, "verification_group_codes")
        if result.statut not in ("submitted", "reopened"):
            return Response({"error": "Ce résultat doit être soumis avant vérification."}, status=400)
        _set_result_status(result, "verified", request.user, _pass_mark(request))
        return Response(self.get_serializer(result).data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        result = self.get_object()
        workflow = _exam_result_workflow(request, result.epreuve)
        _ensure_workflow_access(request, workflow, "validation_group_codes")
        if result.statut != "verified":
            return Response({"error": "Ce résultat doit être vérifié avant validation."}, status=400)
        _set_result_status(result, "validated", request.user, _pass_mark(request))
        return Response(self.get_serializer(result).data)

    @action(detail=True, methods=["post"])
    def publier(self, request, pk=None):
        result = self.get_object()
        workflow = _exam_result_workflow(request, result.epreuve)
        _ensure_workflow_access(request, workflow, "publication_group_codes")
        if result.statut != "validated":
            return Response({"error": "Ce résultat doit être validé avant publication."}, status=400)
        _set_result_status(result, "published", request.user, _pass_mark(request))
        return Response(self.get_serializer(result).data)

    @action(detail=True, methods=["post"])
    def reouvrir(self, request, pk=None):
        result = self.get_object()
        workflow = _exam_result_workflow(request, result.epreuve)
        _ensure_workflow_access(request, workflow, "validation_group_codes")
        if result.statut not in ("validated", "published", "closed"):
            return Response({"error": "Seuls les résultats verrouillés peuvent être réouverts."}, status=400)
        _set_result_status(result, "reopened", request.user, _pass_mark(request))
        return Response(self.get_serializer(result).data)

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        result = self.get_object()
        workflow = _exam_result_workflow(request, result.epreuve)
        _ensure_workflow_access(request, workflow, "publication_group_codes")
        if result.statut not in ("published", "validated", "reopened"):
            return Response({"error": "Ce résultat ne peut pas être clôturé dans son état actuel."}, status=400)
        _set_result_status(result, "closed", request.user, _pass_mark(request))
        return Response(self.get_serializer(result).data)


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
