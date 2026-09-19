"""API views for portail élève (SIS Secondaire) - Agrégation."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class IsEleve(IsAuthenticated):
    """Permission: uniquement pour les élèves."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "eleve")


class PortailEleveViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail élève."""

    permission_classes = [IsEleve]

    def _get_eleve(self, request):
        return request.user.eleve

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord de l'élève."""
        eleve = self._get_eleve(request)

        # Notes récentes
        from apps.notes.models import Note

        notes_recentes = (
            Note.objects.filter(eleve=eleve)
            .select_related("matiere")
            .order_by("-date")[:5]
        )

        notes_data = [
            {
                "matiere": n.matiere.nom,
                "note": float(n.note) if n.note else None,
                "type": n.type_evaluation,
                "date": n.date.isoformat() if n.date else None,
            }
            for n in notes_recentes
        ]

        # Absences
        from apps.presences.models import Presence

        absences = Presence.objects.filter(eleve=eleve, statut="absent").count()

        return Response(
            {
                "eleve": {
                    "matricule": eleve.matricule,
                    "nom": eleve.user.get_full_name(),
                },
                "classe": (
                    {
                        "nom": eleve.classe.nom if eleve.classe else None,
                        "niveau": eleve.classe.niveau if eleve.classe else None,
                    }
                    if eleve.classe
                    else None
                ),
                "statistiques": {
                    "moyenne": (
                        float(eleve.moyenne_generale)
                        if eleve.moyenne_generale
                        else None
                    ),
                    "rang": eleve.rang,
                    "absences": absences,
                },
                "notes_recentes": notes_data,
            }
        )

    @action(detail=False, methods=["get"])
    def profil(self, request):
        """Profil complet de l'élève."""
        eleve = self._get_eleve(request)

        return Response(
            {
                "matricule": eleve.matricule,
                "nom": eleve.user.get_full_name(),
                "email": eleve.user.email,
                "classe": eleve.classe.nom if eleve.classe else None,
                "niveau": eleve.classe.niveau if eleve.classe else None,
                "moyenne": (
                    float(eleve.moyenne_generale) if eleve.moyenne_generale else None
                ),
                "rang": eleve.rang,
            }
        )

    @action(detail=False, methods=["get"])
    def notes(self, request):
        """Notes de l'élève."""
        eleve = self._get_eleve(request)
        periode_id = request.query_params.get("periode")

        from apps.notes.models import Note

        notes = Note.objects.filter(eleve=eleve).select_related("matiere", "periode")
        if periode_id:
            notes = notes.filter(periode_id=periode_id)

        return Response(
            [
                {
                    "id": n.id,
                    "matiere": n.matiere.nom,
                    "note": float(n.note) if n.note else None,
                    "coefficient": float(n.coefficient),
                    "type": n.type_evaluation,
                    "periode": str(n.periode) if n.periode else None,
                    "date": n.date.isoformat() if n.date else None,
                }
                for n in notes.order_by("-date")
            ]
        )

    @action(detail=False, methods=["get"])
    def bulletins(self, request):
        """Bulletins de l'élève."""
        eleve = self._get_eleve(request)

        from apps.bulletins.models import Bulletin

        bulletins = (
            Bulletin.objects.filter(eleve=eleve)
            .select_related("periode")
            .order_by("-periode__date_fin")
        )

        return Response(
            [
                {
                    "id": b.id,
                    "periode": str(b.periode),
                    "moyenne": (
                        float(b.moyenne_generale) if b.moyenne_generale else None
                    ),
                    "rang": b.rang,
                    "appreciation": b.appreciation_generale,
                    "pdf_disponible": bool(b.pdf_path),
                }
                for b in bulletins
            ]
        )

    @action(detail=False, methods=["get"])
    def emploi_du_temps(self, request):
        """Emploi du temps de l'élève."""
        eleve = self._get_eleve(request)

        if not eleve.classe:
            return Response({"error": "Pas de classe assignée."}, status=400)

        from apps.emplois_du_temps.models import Creneau

        creneaux = (
            Creneau.objects.filter(classe=eleve.classe)
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

    @action(detail=False, methods=["get"])
    def absences(self, request):
        """Absences de l'élève."""
        eleve = self._get_eleve(request)

        from apps.presences.models import Presence

        absences = (
            Presence.objects.filter(eleve=eleve, statut__in=["absent", "retard"])
            .select_related("appel")
            .order_by("-appel__date")[:30]
        )

        return Response(
            [
                {
                    "date": a.appel.date.isoformat(),
                    "statut": a.statut,
                    "justifie": a.justifie,
                }
                for a in absences
            ]
        )
