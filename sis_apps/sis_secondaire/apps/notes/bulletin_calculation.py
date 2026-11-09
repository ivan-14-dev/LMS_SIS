"""Explicit numeric report-card protocol; academic decisions remain human."""

from decimal import ROUND_HALF_UP, Decimal

from apps.classes.models import Classe, Matiere, ProgrammeMatiere
from apps.eleves.models import AffectationMatiereIndividuelle, Eleve, Inscription
from apps.etablissement.models import Periode
from django.db import OperationalError, connection, transaction
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied

from sis_common.authorization import has_business_permission
from sis_common.grade_entry import validate_offering_grade

from .models import Evaluation, Note

METHOD = "moyenne_ponderee_20_v1"
CENT = Decimal("0.01")


class BulletinConflict(APIException):
    status_code = 409
    default_detail = "Le bulletin ou ses sources ont changé. Rechargez et recalculez le brouillon."


class PrepareBulletinInput(serializers.Serializer):
    eleve = serializers.PrimaryKeyRelatedField(queryset=Eleve.objects.none())
    classe = serializers.PrimaryKeyRelatedField(queryset=Classe.objects.none())
    periode = serializers.PrimaryKeyRelatedField(queryset=Periode.objects.none())
    methode = serializers.ChoiceField(choices=[METHOD])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = self.context["request"].tenant
        self.fields["eleve"].queryset = Eleve.objects.filter(etablissement=tenant, user__etablissement=tenant)
        self.fields["classe"].queryset = Classe.objects.filter(
            etablissement=tenant, annee_scolaire__etablissement=tenant, niveau__etablissement=tenant
        )
        self.fields["periode"].queryset = Periode.objects.filter(annee_scolaire__etablissement=tenant)


class BulletinVersionInput(serializers.Serializer):
    version = serializers.DateTimeField()


class ValidateBulletinInput(BulletinVersionInput):
    confirmer = serializers.BooleanField()
    appreciation_conseil = serializers.CharField(allow_blank=True, max_length=4000)
    decision = serializers.CharField(allow_blank=True, max_length=50)

    def validate_confirmer(self, value):
        if not value:
            raise serializers.ValidationError("La vérification humaine doit être confirmée.")
        return value


def require_bulletin_permission(request, classe, periode, *, preparing=False):
    context = {"classes": classe.pk, "annees": classe.annee_scolaire_id, "periodes": periode.pk}
    permissions = ["notes.view_bulletin", "notes.change_bulletin"]
    if preparing:
        permissions.append("notes.add_bulletin")
    if not all(has_business_permission(request.user, permission, context) for permission in permissions):
        raise PermissionDenied("Des permissions explicites de gestion des bulletins sont requises.")


def check_version(bulletin, data):
    if not bulletin.calcul_detail:
        raise serializers.ValidationError({"bulletin": "Ce bulletin relève du circuit historique, sans calcul figé."})
    if bulletin.publie:
        raise serializers.ValidationError({"bulletin": "Un bulletin publié ne peut plus être recalculé ou validé."})
    if data["version"] != bulletin.updated_at:
        raise BulletinConflict()


def _positive(value, label):
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        raise serializers.ValidationError({"calcul": f"{label} doit être strictement positif et fini."})
    return number


def _rounded(value):
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def _locked_calculation(eleve, classe, periode):
    # Parent locks also prevent new evaluations/notes being inserted during the snapshot.
    eleve = Eleve.objects.select_for_update(nowait=True).get(pk=eleve.pk)
    classe = Classe.objects.select_for_update(nowait=True).get(pk=classe.pk)
    # Match note writers' shared calendar guard, avoiding a note/calendar lock inversion.
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM etablissement_periode WHERE id = %s FOR SHARE NOWAIT", [periode.pk])
    periode = Periode.objects.select_related("annee_scolaire").get(pk=periode.pk)
    if classe.annee_scolaire_id != periode.annee_scolaire_id:
        raise serializers.ValidationError({"periode": "La période doit appartenir à l'année de la classe."})
    if not Inscription.objects.filter(
        eleve=eleve, classe=classe, annee_scolaire_id=classe.annee_scolaire_id, statut="validee"
    ).exists():
        raise serializers.ValidationError({"eleve": "Une inscription validée dans cette classe est requise."})
    if AffectationMatiereIndividuelle.objects.filter(
        eleve=eleve, annee_scolaire_id=classe.annee_scolaire_id
    ).exists():
        raise serializers.ValidationError({"calcul": "Les parcours individualisés exigent un calcul dédié."})
    evaluations = list(
        Evaluation.objects.select_for_update(nowait=True).filter(classe=classe, periode=periode).order_by("pk")
    )
    if any(item.eleve_cible_id == eleve.pk for item in evaluations):
        raise serializers.ValidationError({"calcul": "Les évaluations individualisées exigent un calcul dédié."})
    evaluations = [item for item in evaluations if item.eleve_cible_id is None]
    notes = {
        note.evaluation_id: note
        for note in Note.objects.select_for_update(nowait=True).filter(eleve=eleve, evaluation__in=evaluations).order_by("pk")
    }
    programmes = {
        item.matiere_id: item
        for item in ProgrammeMatiere.objects.select_for_update(nowait=True).filter(classe=classe).order_by("pk")
    }
    subjects = {
        item.pk: item for item in Matiere.objects.select_for_update(nowait=True).filter(
            pk__in={item.matiere_id for item in evaluations} | set(programmes)
        ).order_by("pk")
    }
    grouped = {}
    excluded = []
    covered_subjects = set()
    for evaluation in evaluations:
        if evaluation.ponderation == 0:
            excluded.append({"evaluation": evaluation.pk, "motif": "ponderation_nulle"})
            continue
        assessment = evaluation.offre_configuration.get("assessment", {})
        if assessment.get("mode", "numeric") != "numeric" or Decimal(str(assessment.get("minimum", 0))) != 0:
            raise serializers.ValidationError({"calcul": "Ce protocole exige des barèmes numériques commençant à zéro."})
        subject = subjects[evaluation.matiere_id]
        if subject.etablissement_id != classe.etablissement_id:
            raise serializers.ValidationError({"calcul": "Une matière n'appartient pas à cet établissement."})
        note = notes.get(evaluation.pk)
        if note is None:
            raise serializers.ValidationError({"notes": f"Note manquante pour l'évaluation {evaluation.pk}."})
        covered_subjects.add(subject.pk)
        if note.statut == "dispensee":
            excluded.append({"evaluation": evaluation.pk, "note": note.pk, "motif": "dispense"})
            continue
        if note.statut != "presente" or note.valeur is None:
            raise serializers.ValidationError({
                "notes": f"Évaluation {evaluation.pk} : absence, travail non rendu ou statut non chiffrable à traiter."
            })
        validate_offering_grade(evaluation, note.valeur, note.resultat, note.statut)
        bareme = _positive(evaluation.bareme, "Le barème")
        if not note.valeur.is_finite() or not 0 <= note.valeur <= bareme:
            raise serializers.ValidationError({"notes": f"Note hors barème pour l'évaluation {evaluation.pk}."})
        weight = _positive(evaluation.coefficient, "Le coefficient") * _positive(
            evaluation.ponderation, "La pondération"
        ) / Decimal(100)
        item = grouped.setdefault(subject.pk, {"sum": Decimal(0), "weight": Decimal(0), "notes": []})
        item["sum"] += note.valeur / bareme * 20 * weight
        item["weight"] += weight
        item["notes"].append({
            "id": note.pk, "evaluation": evaluation.pk, "titre": evaluation.titre,
            "valeur": str(note.valeur), "bareme": str(bareme), "coefficient": str(evaluation.coefficient),
            "ponderation": str(evaluation.ponderation), "appreciation": note.appreciation,
            "statut": note.statut, "offre_configuration": evaluation.offre_configuration,
        })
    missing = [
        item.matiere_id for item in programmes.values()
        if item.obligatoire and item.matiere_id not in covered_subjects
    ]
    if missing:
        raise serializers.ValidationError({"matieres": "Des matières obligatoires n'ont aucun résultat calculable."})
    if not grouped:
        raise serializers.ValidationError({"notes": "Aucun résultat numérique calculable pour ce bulletin."})
    details = []
    weighted_sum = total_weight = Decimal(0)
    for subject_id in sorted(grouped):
        item = grouped[subject_id]
        subject = subjects[subject_id]
        programme = programmes.get(subject_id)
        coefficient = _positive(
            programme.coefficient if programme else subject.coefficient_defaut, "Le coefficient de matière"
        )
        average = item["sum"] / item["weight"]
        weighted_sum += average * coefficient
        total_weight += coefficient
        details.append({
            "id": subject_id, "nom": subject.nom, "coefficient": str(coefficient),
            "origine_coefficient": "programme" if programme else "matiere",
            "moyenne": _rounded(average), "notes": item["notes"],
        })
    return {
        "methode": METHOD,
        "formule": "Notes ramenées sur 20, pondérées par coefficient × pondération / 100 ; "
                   "moyennes de matières pondérées par leurs coefficients, sans arrondi intermédiaire.",
        "arrondi": "Deux décimales, demi supérieur ; aucun rang ou passage automatique.",
        "eleve": {"id": eleve.pk, "nom": eleve.user.get_full_name(), "matricule": eleve.matricule},
        "classe": {"id": classe.pk, "nom": classe.nom},
        "periode": {
            "id": periode.pk,
            "libelle": periode.libelle or str(periode),
        },
        "matieres": details,
        "exclusions": excluded,
        "moyenne_generale": _rounded(weighted_sum / total_weight),
    }


def calculate_bulletin(eleve, classe, periode):
    try:
        with transaction.atomic():
            return _locked_calculation(eleve, classe, periode)
    except OperationalError as error:
        if getattr(getattr(error.__cause__, "diag", None), "sqlstate", None) == "55P03":
            raise BulletinConflict("Une source est en cours de modification. Rechargez avant de réessayer.") from error
        raise


def ensure_current_sources(bulletin):
    if calculate_bulletin(bulletin.eleve, bulletin.classe, bulletin.periode) != bulletin.calcul_detail:
        raise BulletinConflict()


def ensure_calculated_publication(request, bulletin):
    if not bulletin.calcul_detail:
        return
    require_bulletin_permission(request, bulletin.classe, bulletin.periode)
    payload = BulletinVersionInput(data=request.data)
    payload.is_valid(raise_exception=True)
    check_version(bulletin, payload.validated_data)
    if not bulletin.date_validation or not bulletin.valide_par_id:
        raise serializers.ValidationError({"validation": "Le brouillon doit être vérifié et validé avant publication."})
    ensure_current_sources(bulletin)
