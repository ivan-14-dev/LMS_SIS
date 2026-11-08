"""Serialized, human-confirmed financial commands and persisted reconciliation.

No bank request is made. The project row lock is shared with academic lifecycle
and metadata commands. Files are created only after all business checks and the
unique-key insert have succeeded.
"""

import hashlib
import json
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from sis_common.exam_files import hash_uploaded_file
from sis_common.workflow_tracking import record_workflow_event

from .access import FINANCE, ResearchConflict, allowed, check_version, current_research_user
from .finance_models import ResearchAccountingLine, ResearchFinanceOperation, research_financial_upload_to
from .finance_serializers import FinancialCommandSerializer

logger = logging.getLogger(__name__)
ZERO = Decimal("0.00")


def _project_model():
    return apps.get_model("recherche", "ProjetRecherche")


def money(value):
    return format(value, ".2f")


def _invariant(condition, detail):
    if not condition:
        raise ResearchConflict(f"Sous-grand-livre incohérent : {detail}")


def _business_hash(project_id, data, proof_digest):
    payload = {
        "projet": str(project_id),
        "type": data["type"],
        "montant": money(data["montant"]),
        "reference": data["reference"],
        "date_operation": data["date_operation"].isoformat(),
        "libelle": data["libelle"],
        "engagement": str(data["engagement"]) if data["engagement"] else None,
        "contrepassation_de": str(data["contrepassation_de"]) if data["contrepassation_de"] else None,
        "justificatif_sha256": proof_digest,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def valid_proof_path(operation):
    schema = getattr(connection, "schema_name", "")
    name = operation.justificatif.name or ""
    return bool(
        schema != "public"
        and re.fullmatch(r"[a-zA-Z0-9_]+", schema)
        and re.fullmatch(rf"recherche-finance/{re.escape(schema)}/[0-9a-f]{{32}}/preuve\.(pdf|png|jpe?g)", name)
    )


def expected_lines(operation, previous):
    kind, amount = operation.type, operation.montant
    if kind == "financement":
        return {"banque": (amount, ZERO), "financement": (ZERO, amount)}
    if kind == "depense":
        return {"charge": (amount, ZERO), "banque": (ZERO, amount)}
    if kind in ("engagement", "annulation_engagement"):
        return {}
    if kind == "contrepassation":
        original = previous.get(operation.contrepassation_de_id)
        _invariant(original is not None and original.type in ("financement", "depense"), "origine de contrepassation.")
        _invariant(original.montant == amount, "montant de contrepassation.")
        return {account: (credit, debit) for account, (debit, credit) in expected_lines(original, previous).items()}
    raise ResearchConflict("Sous-grand-livre incohérent : type d'opération inconnu.")


@dataclass
class Ledger:
    receipts: Decimal = ZERO
    spent: Decimal = ZERO
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    commitments: dict = field(default_factory=dict)
    cancelled: set = field(default_factory=set)
    reversed: set = field(default_factory=set)
    operations: dict = field(default_factory=dict)

    @property
    def reserved(self):
        return sum(self.commitments.values(), ZERO)

    @property
    def cash(self):
        return self.receipts - self.spent

    def apply(self, operation):
        amount, kind = operation.montant, operation.type
        engagement = operation.engagement_id
        original_id = operation.contrepassation_de_id
        _invariant(amount > ZERO, "montant non positif.")
        _invariant(
            (kind in ("financement", "engagement") and engagement is None and original_id is None)
            or (kind in ("depense", "annulation_engagement") and engagement is not None and original_id is None)
            or (kind == "contrepassation" and engagement is None and original_id is not None),
            "liens incompatibles.",
        )
        if kind == "financement":
            self.receipts += amount
        elif kind == "engagement":
            self.commitments[operation.pk] = amount
        elif kind in ("depense", "annulation_engagement"):
            _invariant(engagement in self.commitments and engagement not in self.cancelled, "engagement indisponible.")
            _invariant(
                operation.date_operation >= self.operations[engagement].date_operation,
                "mouvement antérieur à son engagement.",
            )
            remaining = self.commitments[engagement]
            _invariant(amount <= remaining, "dépassement d'engagement.")
            if kind == "depense":
                self.spent += amount
                self.commitments[engagement] -= amount
            else:
                _invariant(amount == remaining, "annulation différente du solde engagé.")
                self.commitments[engagement] = ZERO
                self.cancelled.add(engagement)
        elif kind == "contrepassation":
            original = self.operations.get(original_id)
            _invariant(original is not None and original.type in ("financement", "depense"), "origine de contrepassation.")
            _invariant(original_id not in self.reversed and amount == original.montant, "contrepassation répétée ou partielle.")
            _invariant(operation.date_operation >= original.date_operation, "contrepassation antérieure à son origine.")
            if original.type == "financement":
                self.receipts -= amount
            else:
                self.spent -= amount
                if original.engagement_id not in self.cancelled:
                    self.commitments[original.engagement_id] += amount
            self.reversed.add(original_id)
        _invariant(self.cash >= ZERO and self.receipts >= ZERO and self.spent >= ZERO, "solde de trésorerie négatif.")
        self.operations[operation.pk] = operation


def reconciled_ledger(project):
    """Read actual rows and compare every account/side/amount, not just totals.

    Callers hold the project row lock, including report readers.
    """
    ledger = Ledger()
    operations = (
        ResearchFinanceOperation.objects.filter(projet=project)
        .select_related("actor")
        .prefetch_related("lignes")
        .order_by("sequence")
    )
    tenant_id = getattr(getattr(connection, "tenant", None), "pk", None)
    for operation in operations:
        _invariant(operation.sequence == len(ledger.operations) + 1, "séquence d'écritures non contiguë.")
        _invariant(operation.actor.etablissement_id == tenant_id and tenant_id is not None, "établissement de l'acteur.")
        _invariant(valid_proof_path(operation), "emplacement privé du justificatif.")
        _invariant(
            operation.justificatif_taille > 0
            and bool(operation.justificatif_nom)
            and bool(re.fullmatch(r"[0-9a-f]{64}", operation.justificatif_sha256)),
            "métadonnées du justificatif.",
        )
        _invariant(operation.date_operation <= timezone.localdate(), "date future.")
        business = {
            "type": operation.type, "montant": operation.montant, "reference": operation.reference,
            "date_operation": operation.date_operation, "libelle": operation.libelle,
            "engagement": operation.engagement_id, "contrepassation_de": operation.contrepassation_de_id,
        }
        _invariant(
            operation.request_hash == _business_hash(project.pk, business, operation.justificatif_sha256),
            "empreinte de l'opération.",
        )
        expected = expected_lines(operation, ledger.operations)
        lines = list(operation.lignes.all())
        actual = {line.compte: (line.debit, line.credit) for line in lines}
        _invariant(len(lines) == len(expected) and actual == expected, f"écritures de l'opération {operation.pk}.")
        for line in lines:
            ledger.debit += line.debit
            ledger.credit += line.credit
        ledger.apply(operation)
    _invariant(ledger.debit == ledger.credit, "journal déséquilibré.")
    _invariant(
        project.budget >= ledger.receipts and project.budget >= ledger.spent + ledger.reserved,
        "dépassement du budget.",
    )
    return ledger


@contextmanager
def locked_financial_project(request, project):
    with transaction.atomic():
        try:
            locked = _project_model().objects.select_for_update().get(pk=project.pk)
        except _project_model().DoesNotExist as exc:
            raise NotFound("Projet introuvable.") from exc
        if not allowed(request, FINANCE, projet=locked):
            raise PermissionDenied("Autorisation financière requise pour ce projet.")
        yield locked


def report_from_ledger(project, ledger):
    return {
        "projet_id": project.pk,
        "devise": "EUR",
        "budget": money(project.budget),
        "encaissements": money(ledger.receipts),
        "depenses": money(ledger.spent),
        "engagements_ouverts": money(ledger.reserved),
        "disponible_budgetaire": money(project.budget - ledger.spent - ledger.reserved),
        "solde_tresorerie": money(ledger.cash),
        "total_debit": money(ledger.debit),
        "total_credit": money(ledger.credit),
        "rapproche": True,
        "version": project.version,
    }


def financial_report(project):
    with transaction.atomic():
        project = _project_model().objects.select_for_update().get(pk=project.pk)
        return report_from_ledger(project, reconciled_ledger(project))


def project_has_open_commitments(project):
    with transaction.atomic():
        project = _project_model().objects.select_for_update().get(pk=project.pk)
        return reconciled_ledger(project).reserved > ZERO


def validate_budget_floor(project, proposed_budget):
    # This helper also validates the current journal before metadata can change.
    with transaction.atomic():
        project = _project_model().objects.select_for_update().get(pk=project.pk)
        ledger = reconciled_ledger(project)
        if not isinstance(proposed_budget, Decimal) or not proposed_budget.is_finite() or proposed_budget < ZERO:
            raise ValidationError({"budget": "Montant décimal positif ou nul requis."})
        if proposed_budget < max(ledger.receipts, ledger.spent + ledger.reserved):
            raise ResearchConflict("Le budget ne peut être inférieur aux fonds reçus ou aux dépenses et engagements.")


def _replay(project, data, request_hash):
    existing = ResearchFinanceOperation.objects.filter(idempotency_key=data["idempotency_key"]).first()
    if existing is None:
        return None
    if existing.projet_id != project.pk or existing.request_hash != request_hash:
        raise ResearchConflict("Clé d'idempotence déjà utilisée pour une autre commande.")
    return existing


def _validate_operation(project, data, ledger):
    kind, amount = data["type"], data["montant"]
    allowed_states = {
        "financement": {"accepte", "en_cours"},
        "engagement": {"en_cours"},
        "depense": {"en_cours"},
        "annulation_engagement": {"accepte", "en_cours", "termine"},
        "contrepassation": {"accepte", "en_cours", "termine"},
    }
    if project.statut not in allowed_states[kind]:
        raise ResearchConflict("L'état du projet ne permet pas cette opération.")
    if kind == "financement" and ledger.receipts + amount > project.budget:
        raise ResearchConflict("Les encaissements dépasseraient le budget.")
    if kind == "engagement" and amount > project.budget - ledger.spent - ledger.reserved:
        raise ResearchConflict("Budget disponible insuffisant.")
    if data["engagement"]:
        engagement_id = data["engagement"]
        if engagement_id not in ledger.commitments:
            raise ValidationError({"engagement": "Engagement introuvable dans ce projet."})
        if data["date_operation"] < ledger.operations[engagement_id].date_operation:
            raise ValidationError({"date_operation": "Le mouvement ne peut pas précéder son engagement."})
        if engagement_id in ledger.cancelled:
            raise ResearchConflict("Cet engagement a été annulé.")
        remaining = ledger.commitments[engagement_id]
        if amount > remaining or (kind == "annulation_engagement" and amount != remaining):
            raise ResearchConflict("Le montant ne correspond pas au solde disponible de l'engagement.")
        if kind == "depense" and amount > ledger.cash:
            raise ResearchConflict("Trésorerie disponible insuffisante.")
    if data["contrepassation_de"]:
        original = ledger.operations.get(data["contrepassation_de"])
        if original is None:
            raise ValidationError({"contrepassation_de": "Opération introuvable dans ce projet."})
        if original.type not in ("financement", "depense"):
            raise ResearchConflict("Seuls un encaissement ou une dépense peuvent être contrepassés.")
        if data["date_operation"] < original.date_operation:
            raise ValidationError({"date_operation": "La contrepassation ne peut pas précéder l'opération originale."})
        if original.pk in ledger.reversed or amount != original.montant:
            raise ResearchConflict("Contrepassation déjà effectuée ou montant différent de l'original.")
        if original.type == "financement" and amount > ledger.cash:
            raise ResearchConflict("La contrepassation rendrait la trésorerie négative.")


def post_financial_operation(request, project, raw_data):
    owned_paths = []
    owned_directory = None
    storage = ResearchFinanceOperation._meta.get_field("justificatif").storage
    try:
        with locked_financial_project(request, project) as project:
            serializer = FinancialCommandSerializer(data=raw_data, context={"project": project})
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            if project.archive:
                raise ResearchConflict("Un projet archivé ne peut pas être modifié.")
            ledger = reconciled_ledger(project)
            proof = data["justificatif"]
            digest = hash_uploaded_file(proof)
            request_hash = _business_hash(project.pk, data, digest)
            replay = _replay(project, data, request_hash)
            if replay is not None:
                return replay, project.version, True
            check_version(project, data["version"])
            _validate_operation(project, data, ledger)
            if ResearchFinanceOperation.objects.filter(reference=data["reference"]).exists():
                raise ResearchConflict("Référence financière déjà utilisée.")
            path = research_financial_upload_to(None, proof.name)
            while storage.exists(path):
                path = research_financial_upload_to(None, proof.name)
            actor = current_research_user(request)
            if actor is None or not allowed(request, FINANCE, projet=project):
                raise PermissionDenied("Autorisation financière révoquée.")
            operation = ResearchFinanceOperation(
                projet=project,
                sequence=len(ledger.operations) + 1,
                type=data["type"],
                montant=data["montant"],
                reference=data["reference"],
                date_operation=data["date_operation"],
                libelle=data["libelle"],
                engagement_id=data["engagement"],
                contrepassation_de_id=data["contrepassation_de"],
                idempotency_key=data["idempotency_key"],
                request_hash=request_hash,
                justificatif=path,
                justificatif_nom=proof.name,
                justificatif_taille=proof.size,
                justificatif_sha256=digest,
                actor=actor,
            )
            try:
                # The savepoint keeps the outer transaction usable after a
                # schema-wide reference/key race on a different project.
                with transaction.atomic():
                    operation.save(force_insert=True)
            except IntegrityError as exc:
                replay = _replay(project, data, request_hash)
                if replay is not None:
                    return replay, project.version, True
                raise ResearchConflict("Référence, clé ou correction financière déjà utilisée.") from exc
            entries = expected_lines(operation, ledger.operations)
            ResearchAccountingLine.objects.bulk_create([
                ResearchAccountingLine(operation=operation, compte=account, debit=debit, credit=credit)
                for account, (debit, credit) in entries.items()
            ])
            directory = Path(storage.path(path)).parent
            directory.parent.mkdir(parents=True, exist_ok=True)
            try:
                # Exclusive ownership of a UUID namespace makes cleanup safe
                # even if a storage backend renames a partially written file.
                directory.mkdir(mode=0o700, exist_ok=False)
            except FileExistsError as exc:
                raise ResearchConflict("Le répertoire privé alloué existe déjà.") from exc
            owned_directory = directory
            owned_paths.append(path)
            proof.seek(0)
            saved_path = storage.save(path, proof)
            if saved_path != path:
                if Path(saved_path).parent == Path(path).parent:
                    owned_paths.append(saved_path)
                raise ResearchConflict("Le stockage n'a pas conservé le chemin privé alloué.")
            with storage.open(path, "rb") as persisted:
                if persisted.size != proof.size or hash_uploaded_file(persisted) != digest:
                    raise ResearchConflict("Le justificatif enregistré ne correspond pas au fichier validé.")
            project.version += 1
            project.save(update_fields=["version"])
            record_workflow_event(
                request, operation, "recherche_operation_financiere",
                "Opération du sous-grand-livre de recherche",
                metadata={
                    "projet_id": project.pk, "operation_id": str(operation.pk), "sequence": operation.sequence,
                    "type": operation.type,
                    "montant": money(operation.montant), "devise": "EUR", "version": project.version,
                },
            )
            return operation, project.version, False
    except Exception:
        for path in owned_paths:
            try:
                storage.delete(path)
            except Exception:
                logger.exception("Échec du nettoyage d'un nouveau justificatif financier.")
        if owned_directory is not None:
            try:
                owned_directory.rmdir()
            except OSError:
                logger.exception("Échec du nettoyage du nouveau répertoire financier.")
        raise
