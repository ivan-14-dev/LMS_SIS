"""API views for portail étudiant (SIS Supérieur) - Agrégation."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Avg, Sum
from django.utils import timezone


class IsEtudiant(IsAuthenticated):
    """Permission: uniquement pour les étudiants."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, 'etudiant')


class PortailEtudiantViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail étudiant."""
    permission_classes = [IsEtudiant]

    def _get_etudiant(self, request):
        return request.user.etudiant

    @action(detail=False, methods=['get'])
    def tableau_bord(self, request):
        """Tableau de bord de l'étudiant."""
        etudiant = self._get_etudiant(request)
        inscription = etudiant.inscriptions.filter(active=True).first()
        
        # Notes récentes
        notes_recentes = []
        for note in etudiant.notes.order_by('-created_at')[:5]:
            notes_recentes.append({
                'ecue': note.ecue.nom if hasattr(note, 'ecue') else '',
                'note': float(note.note) if note.note else None,
                'date': note.created_at.isoformat(),
            })
        
        # Factures impayées
        factures_impayees = []
        for facture in etudiant.factures.filter(statut='impayee')[:5]:
            factures_impayees.append({
                'id': facture.id,
                'montant': float(facture.montant_total),
                'echeance': facture.date_echeance.isoformat() if facture.date_echeance else None,
            })
        
        return Response({
            'etudiant': {
                'matricule': etudiant.matricule,
                'nom': etudiant.user.get_full_name(),
            },
            'inscription': {
                'formation': inscription.formation.nom if inscription else None,
                'annee': inscription.annee_etude if inscription else None,
            } if inscription else None,
            'statistiques': {
                'credits_valides': float(etudiant.credits_valides or 0),
                'moyenne': float(etudiant.moyenne_generale or 0),
            },
            'notes_recentes': notes_recentes,
            'factures_impayees': factures_impayees,
        })

    @action(detail=False, methods=['get'])
    def profil(self, request):
        """Profil complet de l'étudiant."""
        etudiant = self._get_etudiant(request)
        inscription = etudiant.inscriptions.filter(active=True).first()
        
        return Response({
            'matricule': etudiant.matricule,
            'nom_complet': etudiant.user.get_full_name(),
            'email': etudiant.user.email,
            'formation': {
                'id': inscription.formation.id,
                'nom': inscription.formation.nom,
            } if inscription else None,
            'parcours': {
                'id': inscription.parcours.id,
                'nom': inscription.parcours.nom,
            } if inscription and inscription.parcours else None,
            'annee_etude': inscription.annee_etude if inscription else None,
            'statut': etudiant.statut,
            'credits_valides': float(etudiant.credits_valides or 0),
            'moyenne_generale': float(etudiant.moyenne_generale) if etudiant.moyenne_generale else None,
        })

    @action(detail=False, methods=['get'])
    def notes(self, request):
        """Notes par semestre."""
        etudiant = self._get_etudiant(request)
        semestre_id = request.query_params.get('semestre')
        
        notes_query = etudiant.notes.select_related('ecue__ue', 'semestre')
        if semestre_id:
            notes_query = notes_query.filter(semestre_id=semestre_id)
        
        # Grouper par semestre
        semestres = {}
        for note in notes_query:
            sem_id = note.semestre_id
            if sem_id not in semestres:
                semestres[sem_id] = {
                    'semestre': {'id': sem_id, 'nom': str(note.semestre)},
                    'notes': [],
                }
            semestres[sem_id]['notes'].append({
                'ecue': note.ecue.nom,
                'ue': note.ecue.ue.nom if note.ecue.ue else None,
                'note': float(note.note) if note.note else None,
                'credits': float(note.ecue.credits),
                'valide': note.valide,
            })
        
        return Response(list(semestres.values()))

    @action(detail=False, methods=['get'])
    def releves(self, request):
        """Relevés de notes de l'étudiant."""
        etudiant = self._get_etudiant(request)
        releves = etudiant.releves.select_related('semestre').order_by('-date_emission')
        return Response([{
            'id': r.id,
            'semestre': str(r.semestre),
            'moyenne': float(r.moyenne_generale) if r.moyenne_generale else None,
            'credits_valides': float(r.credits_valides),
            'mention': r.mention,
            'date_emission': r.date_emission.isoformat(),
            'signe': r.signe,
        } for r in releves])

    @action(detail=False, methods=['get'])
    def factures(self, request):
        """Factures de l'étudiant."""
        etudiant = self._get_etudiant(request)
        factures = etudiant.factures.order_by('-date_emission')
        return Response([{
            'id': f.id,
            'numero': f.numero,
            'montant': float(f.montant_total),
            'paye': float(f.montant_paye or 0),
            'statut': f.statut,
            'echeance': f.date_echeance.isoformat() if f.date_echeance else None,
        } for f in factures])
