"""API views for portail enseignant (SIS Secondaire) - Agrégation."""

from apps.classes.models import Classe
from apps.emplois_du_temps.models import Creneau
from apps.enseignants.models import AffectationEnseignant
from apps.presences.models import Appel
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


def _decimal_to_float(value):
    return float(value) if value is not None else None


class IsEnseignant(IsAuthenticated):
    """Permission: uniquement pour les enseignants."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "personnel_profile")


class PortailEnseignantViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail enseignant secondaire."""

    permission_classes = [IsEnseignant]

    def _get_enseignant(self, request):
        return request.user.personnel_profile

    def _affectations_queryset(self, enseignant):
        return (
            AffectationEnseignant.objects.filter(enseignant=enseignant)
            .select_related("matiere", "annee_scolaire")
            .prefetch_related("classes__niveau")
        )

    def _accessible_classes(self, request):
        enseignant = self._get_enseignant(request)
        classe_ids = {
            classe.id
            for affectation in self._affectations_queryset(enseignant)
            for classe in affectation.classes.all()
        }
        classe_ids.update(
            Classe.objects.filter(prof_principal=request.user).values_list("id", flat=True)
        )
        return Classe.objects.filter(id__in=classe_ids).select_related("niveau")

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord de l'enseignant."""
        enseignant = self._get_enseignant(request)
        affectations = list(self._affectations_queryset(enseignant))
        classes = []
        total_eleves = 0
        for affectation in affectations:
            for classe in affectation.classes.all():
                nb_eleves = classe.eleves_actuels.count()
                total_eleves += nb_eleves
                classes.append(
                    {
                        "classe_id": classe.id,
                        "classe_nom": classe.nom,
                        "niveau": classe.niveau.nom if classe.niveau else None,
                        "matiere": affectation.matiere.nom,
                        "annee_scolaire": affectation.annee_scolaire.libelle,
                        "nb_eleves": nb_eleves,
                        "heures_semaine": _decimal_to_float(affectation.heures_semaine),
                    }
                )

        classes_pp = (
            Classe.objects.filter(prof_principal=request.user)
            .select_related("niveau")
            .order_by("niveau__ordre", "nom")
        )

        return Response(
            {
                "enseignant": {
                    "nom": enseignant.user.get_full_name(),
                    "matricule": enseignant.matricule,
                    "statut": enseignant.statut,
                },
                "classes": classes,
                "classes_pp": [
                    {"id": classe.id, "nom": classe.nom, "niveau": classe.niveau.nom if classe.niveau else None}
                    for classe in classes_pp
                ],
                "statistiques": {
                    "nb_affectations": len(affectations),
                    "nb_classes": len({item["classe_id"] for item in classes}),
                    "nb_eleves_total": total_eleves,
                },
            }
        )

    @action(detail=False, methods=["get"])
    def mes_classes(self, request):
        """Liste détaillée des classes."""
        classes = []
        for affectation in self._affectations_queryset(self._get_enseignant(request)):
            for classe in affectation.classes.all():
                classes.append(
                    {
                        "id": classe.id,
                        "nom": classe.nom,
                        "niveau": classe.niveau.nom if classe.niveau else None,
                        "matiere": affectation.matiere.nom,
                        "nb_eleves": classe.eleves_actuels.count(),
                        "heures_semaine": _decimal_to_float(affectation.heures_semaine),
                        "annee_scolaire": affectation.annee_scolaire.libelle,
                    }
                )
        return Response(classes)

    @action(detail=False, methods=["get"])
    def eleves_classe(self, request):
        """Élèves d'une classe accessible par l'enseignant."""
        classe_id = request.query_params.get("classe_id")
        if not classe_id:
            return Response({"error": "classe_id requis."}, status=400)

        classe = self._accessible_classes(request).filter(id=classe_id).first()
        if not classe:
            return Response({"error": "Classe non trouvée ou non autorisée."}, status=404)

        eleves = classe.eleves_actuels.select_related("user").order_by("user__last_name")
        return Response(
            [
                {
                    "id": eleve.id,
                    "matricule": eleve.matricule,
                    "nom": eleve.user.get_full_name(),
                    "statut": eleve.statut,
                }
                for eleve in eleves
            ]
        )

    @action(detail=False, methods=["get"])
    def emploi_du_temps(self, request):
        """Emploi du temps de l'enseignant."""
        enseignant = self._get_enseignant(request)
        creneaux = (
            Creneau.objects.filter(enseignant=enseignant, actif=True)
            .select_related("classe__niveau", "matiere", "salle")
            .order_by("jour", "heure_debut")
        )

        return Response(
            [
                {
                    "id": creneau.id,
                    "jour": creneau.jour,
                    "heure_debut": str(creneau.heure_debut),
                    "heure_fin": str(creneau.heure_fin),
                    "classe": creneau.classe.nom,
                    "niveau": creneau.classe.niveau.nom if creneau.classe.niveau else None,
                    "matiere": creneau.matiere.nom,
                    "salle": creneau.salle.nom if creneau.salle else None,
                    "type": creneau.type,
                }
                for creneau in creneaux
            ]
        )

    @action(detail=False, methods=["get"])
    def absences_a_saisir(self, request):
        """Appels à faire."""
        enseignant = self._get_enseignant(request)
        today = timezone.now().date()
        jour_semaine = today.weekday() + 1
        creneaux = Creneau.objects.filter(
            enseignant=enseignant,
            jour=jour_semaine,
            actif=True,
        ).select_related("classe", "matiere")

        a_saisir = []
        for creneau in creneaux:
            if not Appel.objects.filter(creneau=creneau, date=today).exists():
                a_saisir.append(
                    {
                        "creneau_id": creneau.id,
                        "classe": creneau.classe.nom,
                        "matiere": creneau.matiere.nom,
                        "heure": str(creneau.heure_debut),
                    }
                )

        return Response(a_saisir)
