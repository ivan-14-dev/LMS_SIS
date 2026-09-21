"""API views for portail élève (SIS Secondaire) - Agrégation."""

from apps.emplois_du_temps.models import Creneau
from apps.notes.models import Bulletin, Note
from apps.presences.models import Presence
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

ABSENCE_STATUSES = ("absent", "absent_justifie")


def _decimal_to_float(value):
    return float(value) if value is not None else None


class IsEleve(IsAuthenticated):
    """Permission: uniquement pour les élèves."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "eleve_profile")


class PortailEleveViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail élève."""

    permission_classes = [IsEleve]

    def _get_eleve(self, request):
        return request.user.eleve_profile

    def _latest_bulletin(self, eleve):
        return (
            Bulletin.objects.filter(eleve=eleve, publie=True)
            .select_related("classe__niveau", "periode")
            .order_by("-periode__date_fin")
            .first()
        )

    def _classe_payload(self, eleve):
        classe = eleve.classe_actuelle
        if not classe:
            return None
        return {
            "id": classe.id,
            "nom": classe.nom,
            "niveau": classe.niveau.nom if classe.niveau else None,
        }

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord de l'élève."""
        eleve = self._get_eleve(request)
        latest_bulletin = self._latest_bulletin(eleve)
        notes_recentes = (
            Note.objects.filter(eleve=eleve)
            .select_related("evaluation__matiere", "evaluation__periode")
            .order_by("-evaluation__date", "-date_saisie")[:5]
        )
        absences = Presence.objects.filter(eleve=eleve, statut__in=ABSENCE_STATUSES).count()
        retards = Presence.objects.filter(eleve=eleve, statut="retard").count()

        return Response(
            {
                "eleve": {
                    "id": eleve.id,
                    "matricule": eleve.matricule,
                    "nom": eleve.user.get_full_name(),
                },
                "classe": self._classe_payload(eleve),
                "statistiques": {
                    "moyenne": _decimal_to_float(
                        latest_bulletin.moyenne_generale if latest_bulletin else None
                    ),
                    "rang": latest_bulletin.rang if latest_bulletin else None,
                    "absences": absences,
                    "retards": retards,
                },
                "notes_recentes": [
                    {
                        "id": note.id,
                        "evaluation": note.evaluation.titre,
                        "matiere": note.evaluation.matiere.nom,
                        "note": _decimal_to_float(note.valeur),
                        "statut": note.statut,
                        "type": note.evaluation.type,
                        "periode": note.evaluation.periode.libelle,
                        "date": note.evaluation.date.isoformat(),
                    }
                    for note in notes_recentes
                ],
            }
        )

    @action(detail=False, methods=["get"])
    def profil(self, request):
        """Profil complet de l'élève."""
        eleve = self._get_eleve(request)
        latest_bulletin = self._latest_bulletin(eleve)
        classe = self._classe_payload(eleve)

        return Response(
            {
                "id": eleve.id,
                "matricule": eleve.matricule,
                "nom": eleve.user.get_full_name(),
                "email": eleve.user.email,
                "classe": classe["nom"] if classe else None,
                "niveau": classe["niveau"] if classe else None,
                "moyenne": _decimal_to_float(
                    latest_bulletin.moyenne_generale if latest_bulletin else None
                ),
                "rang": latest_bulletin.rang if latest_bulletin else None,
                "statut": eleve.statut,
            }
        )

    @action(detail=False, methods=["get"])
    def notes(self, request):
        """Notes de l'élève."""
        eleve = self._get_eleve(request)
        periode_id = request.query_params.get("periode")
        notes = Note.objects.filter(eleve=eleve).select_related(
            "evaluation__matiere", "evaluation__periode"
        )
        if periode_id:
            notes = notes.filter(evaluation__periode_id=periode_id)

        return Response(
            [
                {
                    "id": note.id,
                    "matiere": note.evaluation.matiere.nom,
                    "evaluation": note.evaluation.titre,
                    "note": _decimal_to_float(note.valeur),
                    "bareme": _decimal_to_float(note.evaluation.bareme),
                    "coefficient": _decimal_to_float(note.evaluation.coefficient),
                    "type": note.evaluation.type,
                    "statut": note.statut,
                    "periode": note.evaluation.periode.libelle,
                    "date": note.evaluation.date.isoformat(),
                }
                for note in notes.order_by("-evaluation__date", "-date_saisie")
            ]
        )

    @action(detail=False, methods=["get"])
    def bulletins(self, request):
        """Bulletins publiés de l'élève."""
        eleve = self._get_eleve(request)
        bulletins = (
            Bulletin.objects.filter(eleve=eleve, publie=True)
            .select_related("periode", "classe__niveau")
            .order_by("-periode__date_fin")
        )

        return Response(
            [
                {
                    "id": bulletin.id,
                    "periode": bulletin.periode.libelle,
                    "classe": bulletin.classe.nom,
                    "niveau": bulletin.classe.niveau.nom if bulletin.classe.niveau else None,
                    "moyenne": _decimal_to_float(bulletin.moyenne_generale),
                    "rang": bulletin.rang,
                    "appreciation": bulletin.appreciation_conseil,
                    "decision": bulletin.decision,
                    "pdf_disponible": bool(bulletin.pdf_path),
                    "publie_le": (
                        bulletin.date_publication.isoformat()
                        if bulletin.date_publication
                        else None
                    ),
                }
                for bulletin in bulletins
            ]
        )

    @action(detail=False, methods=["get"])
    def emploi_du_temps(self, request):
        """Emploi du temps de l'élève."""
        eleve = self._get_eleve(request)
        if not eleve.classe_actuelle:
            return Response({"error": "Pas de classe assignée."}, status=400)

        creneaux = (
            Creneau.objects.filter(classe=eleve.classe_actuelle, actif=True)
            .select_related("matiere", "enseignant__user", "salle")
            .order_by("jour", "heure_debut")
        )

        return Response(
            [
                {
                    "id": creneau.id,
                    "jour": creneau.jour,
                    "heure_debut": str(creneau.heure_debut),
                    "heure_fin": str(creneau.heure_fin),
                    "matiere": creneau.matiere.nom,
                    "enseignant": creneau.enseignant.user.get_full_name(),
                    "salle": creneau.salle.nom if creneau.salle else None,
                    "type": creneau.type,
                }
                for creneau in creneaux
            ]
        )

    @action(detail=False, methods=["get"])
    def absences(self, request):
        """Absences et retards de l'élève."""
        eleve = self._get_eleve(request)
        presences = (
            Presence.objects.filter(eleve=eleve, statut__in=ABSENCE_STATUSES + ("retard",))
            .select_related("appel__creneau", "justificatif")
            .order_by("-appel__date", "-appel__creneau__heure_debut")[:30]
        )

        return Response(
            [
                {
                    "date": presence.appel.date.isoformat(),
                    "statut": presence.statut,
                    "retard_minutes": presence.retard_minutes,
                    "commentaire": presence.commentaire,
                    "justificatif": (
                        {
                            "statut": presence.justificatif.statut,
                            "motif": presence.justificatif.motif,
                        }
                        if hasattr(presence, "justificatif")
                        else None
                    ),
                }
                for presence in presences
            ]
        )
