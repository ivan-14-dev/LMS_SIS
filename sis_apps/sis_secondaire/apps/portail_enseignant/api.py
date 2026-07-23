"""API views for portail enseignant (SIS Secondaire) - Agrégation."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Q
from django.utils import timezone


class IsEnseignant(IsAuthenticated):
    """Permission: uniquement pour les enseignants."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, 'enseignant_secondaire')


class PortailEnseignantViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail enseignant secondaire."""
    permission_classes = [IsEnseignant]

    def _get_enseignant(self, request):
        return request.user.enseignant_secondaire

    @action(detail=False, methods=['get'])
    def tableau_bord(self, request):
        """Tableau de bord de l'enseignant."""
        enseignant = self._get_enseignant(request)
        
        # Classes de l'enseignant
        classes = []
        for affectation in enseignant.classes.all():
            classes.append({
                'classe_id': affectation.classe.id,
                'classe_nom': affectation.classe.nom,
                'matiere': affectation.matiere.nom,
                'nb_eleves': affectation.classe.eleves.count(),
            })
        
        # Classes où il est PP
        classes_pp = enseignant.classes_pp.all()
        
        return Response({
            'enseignant': {
                'nom': enseignant.user.get_full_name(),
                'matricule': enseignant.matricule,
            },
            'classes': classes,
            'classes_pp': [{'id': c.id, 'nom': c.nom} for c in classes_pp],
            'statistiques': {
                'nb_classes': len(classes),
                'nb_eleves_total': sum(c['nb_eleves'] for c in classes),
            },
        })

    @action(detail=False, methods=['get'])
    def mes_classes(self, request):
        """Liste détaillée des classes."""
        enseignant = self._get_enseignant(request)
        
        classes = []
        for affectation in enseignant.classes.select_related('classe', 'matiere'):
            classe = affectation.classe
            classes.append({
                'id': classe.id,
                'nom': classe.nom,
                'niveau': classe.niveau,
                'matiere': affectation.matiere.nom,
                'nb_eleves': classe.eleves.count(),
                'heures_semaine': affectation.heures_semaine,
            })
        
        return Response(classes)

    @action(detail=False, methods=['get'])
    def eleves_classe(self, request):
        """Élèves d'une classe."""
        classe_id = request.query_params.get('classe_id')
        if not classe_id:
            return Response({'error': 'classe_id requis.'}, status=400)
        
        from apps.classes.models import Classe
        try:
            classe = Classe.objects.get(id=classe_id)
        except Classe.DoesNotExist:
            return Response({'error': 'Classe non trouvée.'}, status=404)
        
        eleves = classe.eleves.select_related('user').order_by('user__last_name')
        return Response([{
            'id': e.id,
            'matricule': e.matricule,
            'nom': e.user.get_full_name(),
        } for e in eleves])

    @action(detail=False, methods=['get'])
    def emploi_du_temps(self, request):
        """Emploi du temps de l'enseignant."""
        enseignant = self._get_enseignant(request)
        
        from apps.emplois_du_temps.models import Creneau
        creneaux = Creneau.objects.filter(
            enseignant=enseignant
        ).select_related('classe', 'matiere', 'salle').order_by('jour', 'heure_debut')
        
        return Response([{
            'id': c.id,
            'jour': c.jour,
            'heure_debut': str(c.heure_debut),
            'heure_fin': str(c.heure_fin),
            'classe': c.classe.nom,
            'matiere': c.matiere.nom,
            'salle': c.salle.nom if c.salle else None,
        } for c in creneaux])

    @action(detail=False, methods=['get'])
    def absences_a_saisir(self, request):
        """Appels à faire."""
        enseignant = self._get_enseignant(request)
        today = timezone.now().date()
        
        # Cours du jour sans appel fait
        from apps.emplois_du_temps.models import Creneau
        from apps.presences.models import Appel
        
        jour_semaine = today.weekday()  # 0=lundi
        creneaux = Creneau.objects.filter(
            enseignant=enseignant,
            jour=jour_semaine
        ).select_related('classe', 'matiere')
        
        a_saisir = []
        for c in creneaux:
            appel_existe = Appel.objects.filter(
                classe=c.classe,
                date=today,
                creneau=c
            ).exists()
            if not appel_existe:
                a_saisir.append({
                    'creneau_id': c.id,
                    'classe': c.classe.nom,
                    'matiere': c.matiere.nom,
                    'heure': str(c.heure_debut),
                })
        
        return Response(a_saisir)
