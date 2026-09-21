"""API views for portail étudiant (SIS Supérieur) - Agrégation."""

from apps.notes.models import Note
from apps.paiements.models import FactureFrais
from apps.releves.models import ReleveNotes
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

UNPAID_STATUSES = ("emise", "partielle", "en_retard")


def _decimal_to_float(value):
    return float(value) if value is not None else None


class IsEtudiant(IsAuthenticated):
    """Permission: uniquement pour les étudiants."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "etudiant_profile")


class PortailEtudiantViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail étudiant."""

    permission_classes = [IsEtudiant]

    def _get_etudiant(self, request):
        return request.user.etudiant_profile

    def _current_inscription(self, etudiant):
        current_year = etudiant.annee_universitaire_actuelle_id
        inscriptions = etudiant.inscriptions_admin.select_related(
            "formation", "parcours", "annee_universitaire"
        )
        if current_year:
            current = inscriptions.filter(annee_universitaire_id=current_year).first()
            if current:
                return current
        return inscriptions.order_by("-annee_universitaire__date_debut").first()

    def _latest_releve(self, etudiant):
        return (
            ReleveNotes.objects.filter(etudiant=etudiant)
            .select_related("semestre")
            .order_by("-date_emission")
            .first()
        )

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord de l'étudiant."""
        etudiant = self._get_etudiant(request)
        inscription = self._current_inscription(etudiant)
        latest_releve = self._latest_releve(etudiant)
        notes_recentes = (
            Note.objects.filter(etudiant=etudiant)
            .select_related("evaluation__ecue__ue", "evaluation__semestre")
            .order_by("-evaluation__date", "-date_saisie")[:5]
        )
        factures_impayees = (
            FactureFrais.objects.filter(etudiant=etudiant, statut__in=UNPAID_STATUSES)
            .order_by("date_echeance", "-date_emission")[:5]
        )

        return Response(
            {
                "etudiant": {
                    "id": etudiant.id,
                    "matricule": etudiant.matricule,
                    "nom": etudiant.user.get_full_name(),
                },
                "inscription": (
                    {
                        "formation": inscription.formation.nom,
                        "parcours": inscription.parcours.nom if inscription.parcours else None,
                        "annee": inscription.annee_universitaire.libelle,
                        "statut": inscription.statut,
                    }
                    if inscription
                    else None
                ),
                "statistiques": {
                    "credits_valides": _decimal_to_float(
                        latest_releve.credits_valides if latest_releve else 0
                    ),
                    "moyenne": _decimal_to_float(
                        latest_releve.moyenne_generale if latest_releve else None
                    ),
                },
                "notes_recentes": [
                    {
                        "id": note.id,
                        "ecue": note.evaluation.ecue.nom,
                        "ue": note.evaluation.ecue.ue.nom if note.evaluation.ecue.ue else None,
                        "note": _decimal_to_float(note.valeur),
                        "statut": note.statut,
                        "date": note.evaluation.date.isoformat(),
                    }
                    for note in notes_recentes
                ],
                "factures_impayees": [
                    {
                        "id": facture.id,
                        "numero": facture.numero,
                        "montant": _decimal_to_float(facture.montant),
                        "reste_a_payer": _decimal_to_float(
                            facture.montant - facture.montant_paye
                        ),
                        "echeance": (
                            facture.date_echeance.isoformat()
                            if facture.date_echeance
                            else None
                        ),
                        "statut": facture.statut,
                    }
                    for facture in factures_impayees
                ],
            }
        )

    @action(detail=False, methods=["get"])
    def profil(self, request):
        """Profil complet de l'étudiant."""
        etudiant = self._get_etudiant(request)
        inscription = self._current_inscription(etudiant)
        latest_releve = self._latest_releve(etudiant)

        return Response(
            {
                "id": etudiant.id,
                "matricule": etudiant.matricule,
                "nom_complet": etudiant.user.get_full_name(),
                "email": etudiant.user.email,
                "formation": (
                    {"id": inscription.formation.id, "nom": inscription.formation.nom}
                    if inscription
                    else None
                ),
                "parcours": (
                    {"id": inscription.parcours.id, "nom": inscription.parcours.nom}
                    if inscription and inscription.parcours
                    else None
                ),
                "annee_universitaire": (
                    inscription.annee_universitaire.libelle if inscription else None
                ),
                "statut": etudiant.statut,
                "regime": etudiant.regime,
                "credits_valides": _decimal_to_float(
                    latest_releve.credits_valides if latest_releve else 0
                ),
                "moyenne_generale": _decimal_to_float(
                    latest_releve.moyenne_generale if latest_releve else None
                ),
            }
        )

    @action(detail=False, methods=["get"])
    def notes(self, request):
        """Notes par semestre."""
        etudiant = self._get_etudiant(request)
        semestre_id = request.query_params.get("semestre")
        notes_query = Note.objects.filter(etudiant=etudiant).select_related(
            "evaluation__ecue__ue", "evaluation__semestre"
        )
        if semestre_id:
            notes_query = notes_query.filter(evaluation__semestre_id=semestre_id)

        semestres = {}
        for note in notes_query.order_by(
            "evaluation__semestre__numero", "evaluation__ecue__ue__nom", "evaluation__ecue__nom"
        ):
            semestre = note.evaluation.semestre
            sem_data = semestres.setdefault(
                semestre.id,
                {
                    "semestre": {"id": semestre.id, "nom": str(semestre)},
                    "notes": [],
                },
            )
            sem_data["notes"].append(
                {
                    "evaluation": note.evaluation.titre,
                    "ecue": note.evaluation.ecue.nom,
                    "ue": note.evaluation.ecue.ue.nom if note.evaluation.ecue.ue else None,
                    "note": _decimal_to_float(note.valeur),
                    "credits": _decimal_to_float(note.evaluation.ecue.credits_ects),
                    "modalite": note.evaluation.modalite,
                    "statut": note.statut,
                }
            )

        return Response(list(semestres.values()))

    @action(detail=False, methods=["get"])
    def releves(self, request):
        """Relevés de notes de l'étudiant."""
        etudiant = self._get_etudiant(request)
        releves = etudiant.releves.select_related("semestre").order_by("-date_emission")
        return Response(
            [
                {
                    "id": releve.id,
                    "semestre": str(releve.semestre),
                    "moyenne": _decimal_to_float(releve.moyenne_generale),
                    "credits_valides": _decimal_to_float(releve.credits_valides),
                    "mention": releve.mention,
                    "date_emission": releve.date_emission.isoformat(),
                    "signe": releve.signe,
                }
                for releve in releves
            ]
        )

    @action(detail=False, methods=["get"])
    def factures(self, request):
        """Factures de l'étudiant."""
        etudiant = self._get_etudiant(request)
        factures = etudiant.factures.order_by("-date_emission")
        return Response(
            [
                {
                    "id": facture.id,
                    "numero": facture.numero,
                    "montant": _decimal_to_float(facture.montant),
                    "paye": _decimal_to_float(facture.montant_paye),
                    "reste_a_payer": _decimal_to_float(
                        facture.montant - facture.montant_paye
                    ),
                    "statut": facture.statut,
                    "echeance": (
                        facture.date_echeance.isoformat()
                        if facture.date_echeance
                        else None
                    ),
                }
                for facture in factures
            ]
        )
