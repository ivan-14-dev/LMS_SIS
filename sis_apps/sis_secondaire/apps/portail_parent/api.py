"""API views for portail parent (SIS Secondaire) - Agrégation."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class IsParent(IsAuthenticated):
    """Permission: uniquement pour les parents."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "parent") or request.user.eleves_enfants.exists()


class PortailParentViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail parent."""

    permission_classes = [IsParent]

    def _get_enfants(self, request):
        """Récupère les enfants du parent."""
        return request.user.eleves_enfants.all()

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord du parent."""
        enfants = self._get_enfants(request)

        enfants_data = []
        for enfant in enfants.select_related("classe", "user"):
            # Absences du trimestre
            from apps.presences.models import Presence

            absences = Presence.objects.filter(eleve=enfant, statut="absent").count()
            retards = Presence.objects.filter(eleve=enfant, statut="retard").count()

            enfants_data.append(
                {
                    "id": enfant.id,
                    "matricule": enfant.matricule,
                    "nom": enfant.user.get_full_name(),
                    "classe": enfant.classe.nom if enfant.classe else None,
                    "moyenne": (
                        float(enfant.moyenne_generale)
                        if enfant.moyenne_generale
                        else None
                    ),
                    "absences": absences,
                    "retards": retards,
                }
            )

        # Factures impayées
        from apps.paiements.models import Facture

        factures = Facture.objects.filter(eleve__in=enfants, statut="impayee")
        factures_data = [
            {
                "id": f.id,
                "eleve": f.eleve.user.get_full_name(),
                "montant": float(f.montant_total),
                "echeance": f.date_echeance.isoformat() if f.date_echeance else None,
            }
            for f in factures[:5]
        ]

        return Response(
            {
                "enfants": enfants_data,
                "factures_impayees": factures_data,
            }
        )

    @action(detail=False, methods=["get"])
    def enfant_detail(self, request):
        """Détails d'un enfant."""
        enfant_id = request.query_params.get("enfant_id")
        if not enfant_id:
            return Response({"error": "enfant_id requis."}, status=400)

        enfants = self._get_enfants(request)
        try:
            enfant = enfants.select_related("classe", "user").get(id=enfant_id)
        except enfants.model.DoesNotExist:
            return Response({"error": "Élève non trouvé ou non autorisé."}, status=404)

        return Response(
            {
                "id": enfant.id,
                "matricule": enfant.matricule,
                "nom": enfant.user.get_full_name(),
                "classe": enfant.classe.nom if enfant.classe else None,
                "niveau": enfant.classe.niveau if enfant.classe else None,
            }
        )

    @action(detail=False, methods=["get"])
    def notes_enfant(self, request):
        """Notes d'un enfant."""
        enfant_id = request.query_params.get("enfant_id")
        if not enfant_id:
            return Response({"error": "enfant_id requis."}, status=400)

        enfants = self._get_enfants(request)
        try:
            enfant = enfants.get(id=enfant_id)
        except enfants.model.DoesNotExist:
            return Response({"error": "Élève non trouvé."}, status=404)

        from apps.notes.models import Note

        notes = Note.objects.filter(eleve=enfant).select_related("matiere", "periode")

        return Response(
            [
                {
                    "id": n.id,
                    "matiere": n.matiere.nom,
                    "note": float(n.note) if n.note else None,
                    "coefficient": float(n.coefficient),
                    "type": n.type_evaluation,
                    "date": n.date.isoformat() if n.date else None,
                }
                for n in notes.order_by("-date")[:50]
            ]
        )

    @action(detail=False, methods=["get"])
    def absences_enfant(self, request):
        """Absences d'un enfant."""
        enfant_id = request.query_params.get("enfant_id")
        if not enfant_id:
            return Response({"error": "enfant_id requis."}, status=400)

        enfants = self._get_enfants(request)
        try:
            enfant = enfants.get(id=enfant_id)
        except enfants.model.DoesNotExist:
            return Response({"error": "Élève non trouvé."}, status=404)

        from apps.presences.models import Presence

        absences = (
            Presence.objects.filter(eleve=enfant, statut__in=["absent", "retard"])
            .select_related("appel")
            .order_by("-appel__date")[:30]
        )

        return Response(
            [
                {
                    "date": a.appel.date.isoformat(),
                    "statut": a.statut,
                    "justifie": a.justifie,
                    "motif": a.motif or "",
                }
                for a in absences
            ]
        )

    @action(detail=False, methods=["get"])
    def emploi_du_temps_enfant(self, request):
        """Emploi du temps d'un enfant."""
        enfant_id = request.query_params.get("enfant_id")
        if not enfant_id:
            return Response({"error": "enfant_id requis."}, status=400)

        enfants = self._get_enfants(request)
        try:
            enfant = enfants.select_related("classe").get(id=enfant_id)
        except enfants.model.DoesNotExist:
            return Response({"error": "Élève non trouvé."}, status=404)

        if not enfant.classe:
            return Response({"error": "Élève sans classe."}, status=400)

        from apps.emplois_du_temps.models import Creneau

        creneaux = (
            Creneau.objects.filter(classe=enfant.classe)
            .select_related("matiere", "enseignant__user", "salle")
            .order_by("jour", "heure_debut")
        )

        return Response(
            [
                {
                    "jour": c.jour,
                    "heure_debut": str(c.heure_debut),
                    "heure_fin": str(c.heure_fin),
                    "matiere": c.matiere.nom,
                    "enseignant": (
                        c.enseignant.user.get_full_name() if c.enseignant else None
                    ),
                    "salle": c.salle.nom if c.salle else None,
                }
                for c in creneaux
            ]
        )
