"""Serializers for paiements (SIS Secondaire)."""
from rest_framework import serializers
from .models import TypeFrais, Facture, Paiement


class TypeFraisSerializer(serializers.ModelSerializer):
    """Serializer pour les types de frais."""
    periodicite_display = serializers.CharField(source='get_periodicite_display', read_only=True)
    nb_factures = serializers.SerializerMethodField()
    
    class Meta:
        model = TypeFrais
        fields = [
            'id', 'annee_scolaire', 'code', 'libelle', 'montant',
            'periodicite', 'periodicite_display', 'obligatoire',
            'classes', 'date_limite', 'actif',
            'nb_factures', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_nb_factures(self, obj):
        return obj.factures.count()


class FactureListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de factures."""
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    type_frais_libelle = serializers.CharField(source='type_frais.libelle', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    montant_restant = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Facture
        fields = [
            'id', 'eleve', 'eleve_matricule', 'eleve_nom',
            'type_frais', 'type_frais_libelle',
            'numero', 'date_emission', 'date_echeance',
            'montant', 'montant_paye', 'montant_restant',
            'statut', 'statut_display',
        ]


class FactureDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une facture."""
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    type_frais_libelle = serializers.CharField(source='type_frais.libelle', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    montant_restant = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    paiements = serializers.SerializerMethodField()
    
    class Meta:
        model = Facture
        fields = [
            'id', 'eleve', 'eleve_matricule', 'eleve_nom',
            'type_frais', 'type_frais_libelle',
            'numero', 'date_emission', 'date_echeance',
            'montant', 'montant_paye', 'montant_restant',
            'statut', 'statut_display', 'note', 'pdf_path',
            'paiements', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'numero', 'created_at', 'updated_at']
    
    def get_paiements(self, obj):
        return PaiementSerializer(obj.paiements.all(), many=True).data


class PaiementSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements."""
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    enregistre_par_nom = serializers.CharField(source='enregistre_par.get_full_name', read_only=True)
    
    class Meta:
        model = Paiement
        fields = [
            'id', 'facture', 'numero', 'date_paiement',
            'montant', 'mode', 'mode_display',
            'reference_externe', 'statut', 'statut_display',
            'recu_pdf', 'enregistre_par', 'enregistre_par_nom', 'created_at',
        ]
        read_only_fields = ['id', 'numero', 'created_at']


class PaiementCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un paiement."""
    
    class Meta:
        model = Paiement
        fields = [
            'facture', 'date_paiement', 'montant',
            'mode', 'reference_externe',
        ]
