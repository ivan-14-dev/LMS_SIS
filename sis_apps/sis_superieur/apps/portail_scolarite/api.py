"""API views for portail scolarité (SIS Supérieur) - Agrégation."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Q, Sum
from django.utils import timezone

from apps.etudiants.models import Etudiant, InscriptionAdministrative
from apps.formations.models import Formation
from apps.paiements.models import Facture


class IsScolarite(IsAuthenticated):
    """Permission: personnel scolarité."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return user.is_staff or getattr(user, 'role', '') in (
            'scolarite', 'directeur_etudes', 'chef_departement', 'doyen'
        )


class PortailScolariteViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour la scolarité."""
    permission_classes = [IsScolarite]

    @action(detail=False, methods=['get'])
    def tableau_bord(self, request):
        """Tableau de bord de la scolarité."""
        today = timezone.now().date()
        
        # Statistiques générales
        stats = {
            'total_etudiants': Etudiant.objects.filter(actif=True).count(),
            'inscriptions_annee': InscriptionAdministrative.objects.filter(
                annee_universitaire__en_cours=True
            ).count(),
            'factures_impayees': Facture.objects.filter(statut='impayee').count(),
            'montant_impaye': float(
                Facture.objects.filter(statut='impayee').aggregate(
                    total=Sum('montant_total')
                )['total'] or 0
            ),
        }
        
        # Inscriptions récentes
        inscriptions = InscriptionAdministrative.objects.select_related(
            'etudiant__user', 'formation'
        ).order_by('-created_at')[:10]
        
        inscriptions_recentes = [{
            'id': i.id,
            'etudiant': i.etudiant.user.get_full_name(),
            'matricule': i.etudiant.matricule,
            'formation': i.formation.nom,
            'date': i.created_at.isoformat(),
            'statut': i.statut,
        } for i in inscriptions]
        
        return Response({
            'statistiques': stats,
            'inscriptions_recentes': inscriptions_recentes,
        })

    @action(detail=False, methods=['get'])
    def statistiques_formations(self, request):
        """Statistiques par formation."""
        formations = Formation.objects.annotate(
            nb_inscrits=Count('inscriptions', filter=Q(inscriptions__active=True)),
        ).values('id', 'nom', 'nb_inscrits')
        
        return Response(list(formations))

    @action(detail=False, methods=['get'])
    def etudiants_recherche(self, request):
        """Recherche d'étudiants."""
        q = request.query_params.get('q', '')
        if len(q) < 2:
            return Response({'error': 'Recherche trop courte (min 2 caractères).'}, status=400)
        
        etudiants = Etudiant.objects.filter(
            Q(matricule__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__email__icontains=q)
        ).select_related('user')[:20]
        
        return Response([{
            'id': e.id,
            'matricule': e.matricule,
            'nom': e.user.get_full_name(),
            'email': e.user.email,
            'actif': e.actif,
        } for e in etudiants])

    @action(detail=False, methods=['get'])
    def dossier_etudiant(self, request):
        """Dossier complet d'un étudiant."""
        etudiant_id = request.query_params.get('etudiant_id')
        if not etudiant_id:
            return Response({'error': 'etudiant_id requis.'}, status=400)
        
        try:
            etudiant = Etudiant.objects.select_related('user').get(id=etudiant_id)
        except Etudiant.DoesNotExist:
            return Response({'error': 'Étudiant non trouvé.'}, status=404)
        
        # Inscriptions
        inscriptions = [{
            'id': i.id,
            'formation': i.formation.nom,
            'annee': str(i.annee_universitaire),
            'statut': i.statut,
            'active': i.active,
        } for i in etudiant.inscriptions.select_related('formation', 'annee_universitaire')]
        
        # Factures
        factures = [{
            'id': f.id,
            'numero': f.numero,
            'montant': float(f.montant_total),
            'statut': f.statut,
        } for f in etudiant.factures.all()[:10]]
        
        return Response({
            'etudiant': {
                'id': etudiant.id,
                'matricule': etudiant.matricule,
                'nom': etudiant.user.get_full_name(),
                'email': etudiant.user.email,
                'actif': etudiant.actif,
            },
            'inscriptions': inscriptions,
            'factures': factures,
        })

    @action(detail=False, methods=['get'])
    def alertes(self, request):
        """Alertes et notifications."""
        alertes = []
        
        # Factures en retard
        factures_retard = Facture.objects.filter(
            statut='impayee',
            date_echeance__lt=timezone.now().date()
        ).count()
        if factures_retard > 0:
            alertes.append({
                'type': 'factures_retard',
                'message': f'{factures_retard} facture(s) en retard de paiement',
                'niveau': 'warning',
            })
        
        return Response(alertes)
