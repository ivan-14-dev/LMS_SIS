"""API views for portail parent (SIS Secondaire) - Agrégation."""

from apps.eleves.models import EleveTuteur
from apps.emplois_du_temps.models import Creneau
from apps.notes.models import Bulletin, Note
from apps.paiements.models import Facture
from apps.presences.models import Presence
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

UNPAID_STATUSES = ("emise", "partielle", "en_retard")


def _decimal_to_float(value):
    return float(value) if value is not None else None


class IsParent(IsAuthenticated):
    """Permission: uniquement pour les parents."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "tuteur_profile")


class PortailParentViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail parent."""

    permission_classes = [IsParent]

    def _authorized_links(self, request):
        return EleveTuteur.objects.filter(
            tuteur=request.user.tuteur_profile,
            autorise_acces_portail=True,
        ).select_related("eleve__user", "eleve__classe_actuelle__niveau")

    def _get_enfants(self, request):
        return [link.eleve for link in self._authorized_links(request)]

    def _get_enfant(self, request):
        enfant_id = request.query_params.get("enfant_id")
        if not enfant_id:
            return None, Response({"error": "enfant_id requis."}, status=400)
        link = self._authorized_links(request).filter(eleve_id=enfant_id).first()
        if not link:
            return None, Response({"error": "Élève non trouvé ou non autorisé."}, status=404)
        return link.eleve, None

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord du parent."""
        enfants = self._get_enfants(request)
        enfant_ids = [enfant.id for enfant in enfants]
        latest_bulletins = {}
        for bulletin in (
            Bulletin.objects.filter(eleve_id__in=enfant_ids, publie=True)
            .select_related("periode")
            .order_by("eleve_id", "-periode__date_fin")
        ):
            latest_bulletins.setdefault(bulletin.eleve_id, bulletin)

        enfants_data = []
        for enfant in enfants:
            absences = Presence.objects.filter(
                eleve=enfant, statut__in=("absent", "absent_justifie")
            ).count()
            retards = Presence.objects.filter(eleve=enfant, statut="retard").count()
            bulletin = latest_bulletins.get(enfant.id)
            enfants_data.append(
                {
                    "id": enfant.id,
                    "matricule": enfant.matricule,
                    "nom": enfant.user.get_full_name(),
                    "classe": enfant.classe_actuelle.nom if enfant.classe_actuelle else None,
                    "niveau": (
                        enfant.classe_actuelle.niveau.nom
                        if enfant.classe_actuelle and enfant.classe_actuelle.niveau
                        else None
                    ),
                    "moyenne": _decimal_to_float(
                        bulletin.moyenne_generale if bulletin else None
                    ),
                    "rang": bulletin.rang if bulletin else None,
                    "absences": absences,
                    "retards": retards,
                }
            )

        factures = (
            Facture.objects.filter(eleve_id__in=enfant_ids, statut__in=UNPAID_STATUSES)
            .select_related("eleve__user")
            .order_by("date_echeance", "-date_emission")[:5]
        )

        return Response(
            {
                "enfants": enfants_data,
                "factures_impayees": [
                    {
                        "id": facture.id,
                        "numero": facture.numero,
                        "eleve": facture.eleve.user.get_full_name(),
                        "montant": _decimal_to_float(facture.montant),
                        "reste_a_payer": _decimal_to_float(facture.montant_restant),
                        "echeance": (
                            facture.date_echeance.isoformat()
                            if facture.date_echeance
                            else None
                        ),
                        "statut": facture.statut,
                    }
                    for facture in factures
                ],
            }
        )

    @action(detail=False, methods=["get"])
    def enfant_detail(self, request):
        """Détails d'un enfant."""
        enfant, error = self._get_enfant(request)
        if error:
            return error

        latest_bulletin = (
            Bulletin.objects.filter(eleve=enfant, publie=True)
            .select_related("periode")
            .order_by("-periode__date_fin")
            .first()
        )
        return Response(
            {
                "id": enfant.id,
                "matricule": enfant.matricule,
                "nom": enfant.user.get_full_name(),
                "classe": enfant.classe_actuelle.nom if enfant.classe_actuelle else None,
                "niveau": (
                    enfant.classe_actuelle.niveau.nom
                    if enfant.classe_actuelle and enfant.classe_actuelle.niveau
                    else None
                ),
                "statut": enfant.statut,
                "moyenne": _decimal_to_float(
                    latest_bulletin.moyenne_generale if latest_bulletin else None
                ),
                "rang": latest_bulletin.rang if latest_bulletin else None,
            }
        )

    @action(detail=False, methods=["get"])
    def notes_enfant(self, request):
        """Notes d'un enfant."""
        enfant, error = self._get_enfant(request)
        if error:
            return error

        notes = Note.objects.filter(eleve=enfant).select_related(
            "evaluation__matiere", "evaluation__periode"
        )

        return Response(
            [
                {
                    "id": note.id,
                    "matiere": note.evaluation.matiere.nom,
                    "evaluation": note.evaluation.titre,
                    "note": _decimal_to_float(note.valeur),
                    "type": note.evaluation.type,
                    "statut": note.statut,
                    "date": note.evaluation.date.isoformat(),
                }
                for note in notes.order_by("-evaluation__date", "-date_saisie")[:50]
            ]
        )

    @action(detail=False, methods=["get"])
    def absences_enfant(self, request):
        """Absences d'un enfant."""
        enfant, error = self._get_enfant(request)
        if error:
            return error

        presences = (
            Presence.objects.filter(
                eleve=enfant, statut__in=("absent", "absent_justifie", "retard")
            )
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

    @action(detail=False, methods=["get"])
    def emploi_du_temps_enfant(self, request):
        """Emploi du temps d'un enfant."""
        enfant, error = self._get_enfant(request)
        if error:
            return error
        if not enfant.classe_actuelle:
            return Response({"error": "Élève sans classe."}, status=400)

        creneaux = (
            Creneau.objects.filter(classe=enfant.classe_actuelle, actif=True)
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
