"""API views for portail doyen (SIS Supérieur) - Agrégation."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Q
from django.utils import timezone

from apps.structure.models import Faculte, Departement
from apps.formations.models import Formation
from apps.etudiants.models import Etudiant, InscriptionAdministrative
from apps.enseignants.models import EnseignantChercheur
from apps.recherche.models import Laboratoire, These


class IsDoyen(IsAuthenticated):
    """Permission: uniquement pour les doyens/direction."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return user.is_staff or getattr(user, 'role', '') in (
            'doyen', 'vice_doyen', 'president', 'vice_president'
        )


class PortailDoyenViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail doyen."""
    permission_classes = [IsDoyen]

    @action(detail=False, methods=['get'])
    def tableau_bord(self, request):
        """Tableau de bord du doyen."""
        faculte_id = request.query_params.get('faculte_id')
        
        # Si pas de faculté spécifiée, prendre toutes les stats
        if faculte_id:
            try:
                faculte = Faculte.objects.get(id=faculte_id)
            except Faculte.DoesNotExist:
                return Response({'error': 'Faculté non trouvée.'}, status=404)
            formations = Formation.objects.filter(departement__faculte=faculte)
            departements = faculte.departements.all()
        else:
            formations = Formation.objects.all()
            departements = Departement.objects.all()
        
        # Statistiques
        stats = {
            'nb_formations': formations.count(),
            'nb_departements': departements.count(),
            'nb_etudiants': InscriptionAdministrative.objects.filter(
                formation__in=formations, active=True
            ).count(),
            'nb_enseignants': EnseignantChercheur.objects.filter(
                departement__in=departements
            ).count(),
            'nb_laboratoires': Laboratoire.objects.filter(
                faculte_id=faculte_id
            ).count() if faculte_id else Laboratoire.objects.count(),
            'nb_theses_en_cours': These.objects.filter(statut='en_cours').count(),
        }
        
        # Départements
        deps = [{
            'id': d.id,
            'nom': d.nom,
            'chef': d.chef.user.get_full_name() if d.chef else None,
            'nb_enseignants': d.enseignants.count(),
        } for d in departements[:10]]
        
        return Response({
            'faculte': {'id': faculte.id, 'nom': faculte.nom} if faculte_id else None,
            'statistiques': stats,
            'departements': deps,
        })

    @action(detail=False, methods=['get'])
    def statistiques_formations(self, request):
        """Statistiques détaillées par formation."""
        faculte_id = request.query_params.get('faculte_id')
        
        formations = Formation.objects.annotate(
            nb_inscrits=Count('inscriptions', filter=Q(inscriptions__active=True)),
        )
        if faculte_id:
            formations = formations.filter(departement__faculte_id=faculte_id)
        
        return Response([{
            'id': f.id,
            'nom': f.nom,
            'departement': f.departement.nom if f.departement else None,
            'nb_inscrits': f.nb_inscrits,
            'niveau': f.niveau,
        } for f in formations])

    @action(detail=False, methods=['get'])
    def recherche(self, request):
        """Statistiques recherche."""
        faculte_id = request.query_params.get('faculte_id')
        
        labos = Laboratoire.objects.all()
        theses = These.objects.all()
        if faculte_id:
            labos = labos.filter(faculte_id=faculte_id)
        
        return Response({
            'nb_laboratoires': labos.count(),
            'nb_theses_en_cours': theses.filter(statut='en_cours').count(),
            'nb_theses_soutenues': theses.filter(statut='soutenue').count(),
            'laboratoires': [{
                'id': l.id,
                'nom': l.nom,
                'acronyme': l.acronyme,
                'directeur': l.directeur.user.get_full_name() if l.directeur else None,
            } for l in labos[:10]],
        })

    @action(detail=False, methods=['get'])
    def budget(self, request):
        """Informations budgétaires."""
        from apps.paiements.models import Facture
        from django.db.models import Sum
        
        # Simplifié
        factures = Facture.objects.filter(annee_universitaire__en_cours=True)
        
        return Response({
            'total_facture': float(factures.aggregate(t=Sum('montant_total'))['t'] or 0),
            'total_paye': float(factures.filter(statut='payee').aggregate(t=Sum('montant_total'))['t'] or 0),
            'total_impaye': float(factures.filter(statut='impayee').aggregate(t=Sum('montant_total'))['t'] or 0),
        })
