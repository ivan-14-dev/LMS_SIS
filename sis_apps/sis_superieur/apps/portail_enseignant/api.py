"""API views for portail enseignant (SIS Supérieur) - Agrégation."""

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class IsEnseignant(IsAuthenticated):
    """Permission: uniquement pour les enseignants."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "enseignant")


class PortailEnseignantViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail enseignant."""

    permission_classes = [IsEnseignant]

    def _get_enseignant(self, request):
        return request.user.enseignant

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord de l'enseignant."""
        enseignant = self._get_enseignant(request)

        # Cours du semestre en cours
        cours = []
        for service in enseignant.services.filter(semestre__en_cours=True):
            cours.append(
                {
                    "ecue_id": service.ecue.id,
                    "ecue_nom": service.ecue.nom,
                    "type": service.type_enseignement,
                    "heures": float(service.heures),
                }
            )

        return Response(
            {
                "enseignant": {
                    "nom": enseignant.user.get_full_name(),
                    "grade": enseignant.grade,
                    "departement": (
                        enseignant.departement.nom if enseignant.departement else None
                    ),
                },
                "cours_semestre": cours,
                "statistiques": {
                    "nb_cours": len(cours),
                    "heures_total": sum(c["heures"] for c in cours),
                },
            }
        )

    @action(detail=False, methods=["get"])
    def mes_cours(self, request):
        """Liste des cours de l'enseignant."""
        enseignant = self._get_enseignant(request)
        semestre_id = request.query_params.get("semestre")

        services = enseignant.services.select_related("ecue__ue", "semestre")
        if semestre_id:
            services = services.filter(semestre_id=semestre_id)

        return Response(
            [
                {
                    "id": s.id,
                    "ecue": {
                        "id": s.ecue.id,
                        "nom": s.ecue.nom,
                        "code": s.ecue.code,
                    },
                    "ue": s.ecue.ue.nom if s.ecue.ue else None,
                    "semestre": str(s.semestre),
                    "type": s.type_enseignement,
                    "heures": float(s.heures),
                    "groupe": s.groupe,
                }
                for s in services
            ]
        )

    @action(detail=False, methods=["get"])
    def etudiants_cours(self, request):
        """Liste des étudiants pour un cours."""
        ecue_id = request.query_params.get("ecue_id")
        if not ecue_id:
            return Response({"error": "ecue_id requis."}, status=400)

        from apps.etudiants.models import InscriptionAdministrative
        from apps.ue_ecue.models import ECUE

        try:
            ecue = ECUE.objects.select_related("ue__formation").get(id=ecue_id)
        except ECUE.DoesNotExist:
            return Response({"error": "ECUE non trouvé."}, status=404)

        # Étudiants inscrits à cette formation
        inscriptions = InscriptionAdministrative.objects.filter(
            formation=ecue.ue.formation, active=True
        ).select_related("etudiant__user")

        return Response(
            [
                {
                    "id": i.etudiant.id,
                    "matricule": i.etudiant.matricule,
                    "nom": i.etudiant.user.get_full_name(),
                }
                for i in inscriptions
            ]
        )

    @action(detail=False, methods=["get"])
    def notes_a_saisir(self, request):
        """Notes en attente de saisie."""
        enseignant = self._get_enseignant(request)

        # ECUEs de l'enseignant sans notes complètes
        services = enseignant.services.filter(semestre__en_cours=True).select_related(
            "ecue"
        )

        a_saisir = []
        for service in services:
            # Compter les notes manquantes (simplifié)
            a_saisir.append(
                {
                    "ecue_id": service.ecue.id,
                    "ecue_nom": service.ecue.nom,
                    "type": service.type_enseignement,
                }
            )

        return Response(a_saisir)

    @action(detail=False, methods=["get"])
    def emploi_du_temps(self, request):
        """Emploi du temps de l'enseignant."""
        self._get_enseignant(request)
        semaine = request.query_params.get("semaine", timezone.now().isocalendar()[1])

        # Simplifié - retourner les créneaux
        return Response(
            {
                "semaine": int(semaine),
                "creneaux": [],  # À implémenter avec le module emplois_du_temps
            }
        )
