"""Serializers for bourses (SIS Supérieur)."""
from rest_framework import serializers
from .models import TypeBourse, DemandeBourse, AttributionBourse, VersementBourse


# === TypeBourse Serializers ===
class TypeBourseListSerializer(serializers.ModelSerializer):
    """Liste légère des types de bourses."""
    class Meta:
        model = TypeBourse
        fields = ['id', 'nom', 'categorie', 'montant_mensuel', 'duree_mois', 'actif']


class TypeBourseDetailSerializer(serializers.ModelSerializer):
    """Détail complet d'un type de bourse."""
    categorie_display = serializers.CharField(source='get_categorie_display', read_only=True)
    montant_total = serializers.SerializerMethodField()

    class Meta:
        model = TypeBourse
        fields = '__all__'

    def get_montant_total(self, obj):
        return obj.montant_mensuel * obj.duree_mois


# === VersementBourse Serializers ===
class VersementBourseSerializer(serializers.ModelSerializer):
    """Versement de bourse."""
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = VersementBourse
        fields = '__all__'
        read_only_fields = ['attribution']


class VersementBourseCreateSerializer(serializers.ModelSerializer):
    """Création d'un versement."""
    class Meta:
        model = VersementBourse
        fields = ['mois', 'montant', 'statut', 'commentaire']


# === AttributionBourse Serializers ===
class AttributionBourseListSerializer(serializers.ModelSerializer):
    """Liste légère des attributions."""
    etudiant_nom = serializers.CharField(source='demande.etudiant.__str__', read_only=True)
    type_bourse_nom = serializers.CharField(source='demande.type_bourse.nom', read_only=True)

    class Meta:
        model = AttributionBourse
        fields = [
            'id', 'numero_attribution', 'etudiant_nom', 'type_bourse_nom',
            'date_debut', 'date_fin', 'montant_total', 'statut'
        ]


class AttributionBourseDetailSerializer(serializers.ModelSerializer):
    """Détail d'une attribution avec versements."""
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    versements = VersementBourseSerializer(many=True, read_only=True)
    etudiant = serializers.SerializerMethodField()
    type_bourse = TypeBourseListSerializer(source='demande.type_bourse', read_only=True)
    total_verse = serializers.SerializerMethodField()

    class Meta:
        model = AttributionBourse
        fields = '__all__'

    def get_etudiant(self, obj):
        return {
            'id': obj.demande.etudiant.id,
            'nom_complet': str(obj.demande.etudiant),
            'matricule': obj.demande.etudiant.matricule
        }

    def get_total_verse(self, obj):
        return sum(
            v.montant for v in obj.versements.filter(statut='effectue')
        )


# === DemandeBourse Serializers ===
class DemandeBourseListSerializer(serializers.ModelSerializer):
    """Liste légère des demandes."""
    etudiant_nom = serializers.CharField(source='etudiant.__str__', read_only=True)
    type_bourse_nom = serializers.CharField(source='type_bourse.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = DemandeBourse
        fields = [
            'id', 'etudiant_nom', 'type_bourse_nom', 'statut', 'statut_display',
            'date_soumission', 'created_at'
        ]


class DemandeBourseDetailSerializer(serializers.ModelSerializer):
    """Détail complet d'une demande."""
    etudiant = serializers.SerializerMethodField()
    type_bourse = TypeBourseDetailSerializer(read_only=True)
    annee_universitaire_str = serializers.CharField(
        source='annee_universitaire.__str__', read_only=True
    )
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    decision_par_nom = serializers.CharField(
        source='decision_par.__str__', read_only=True
    )
    attribution = AttributionBourseDetailSerializer(read_only=True)
    has_attribution = serializers.SerializerMethodField()

    class Meta:
        model = DemandeBourse
        fields = '__all__'

    def get_etudiant(self, obj):
        return {
            'id': obj.etudiant.id,
            'matricule': obj.etudiant.matricule,
            'nom_complet': str(obj.etudiant),
            'email': obj.etudiant.email,
            'formation': str(obj.etudiant.formation) if obj.etudiant.formation else None
        }

    def get_has_attribution(self, obj):
        return hasattr(obj, 'attribution')


class DemandeBourseCreateSerializer(serializers.ModelSerializer):
    """Création d'une demande de bourse."""
    class Meta:
        model = DemandeBourse
        fields = [
            'etudiant', 'type_bourse', 'annee_universitaire',
            'lettre_motivation', 'justificatifs', 'revenus_declares'
        ]

    def validate(self, attrs):
        etudiant = attrs.get('etudiant')
        type_bourse = attrs.get('type_bourse')
        annee = attrs.get('annee_universitaire')
        
        # Vérifier unicité
        if DemandeBourse.objects.filter(
            etudiant=etudiant, type_bourse=type_bourse, annee_universitaire=annee
        ).exists():
            raise serializers.ValidationError(
                "Une demande existe déjà pour cet étudiant, ce type de bourse et cette année."
            )
        return attrs


class DemandeBourseUpdateSerializer(serializers.ModelSerializer):
    """Mise à jour d'une demande."""
    class Meta:
        model = DemandeBourse
        fields = ['lettre_motivation', 'justificatifs', 'revenus_declares']


class DecisionBourseSerializer(serializers.Serializer):
    """Sérialiseur pour la décision sur une demande."""
    decision = serializers.ChoiceField(choices=['acceptee', 'refusee', 'liste_attente'])
    motif = serializers.CharField(required=False, allow_blank=True)
    commentaires = serializers.CharField(required=False, allow_blank=True)


# === Attribution Create ===
class AttributionBourseCreateSerializer(serializers.ModelSerializer):
    """Création d'une attribution suite à acceptation."""
    class Meta:
        model = AttributionBourse
        fields = [
            'date_debut', 'date_fin', 'montant_mensuel', 
            'rib_iban', 'titulaire_compte'
        ]


# === Stats ===
class StatsBourseSerializer(serializers.Serializer):
    """Statistiques des bourses."""
    total_demandes = serializers.IntegerField()
    demandes_en_attente = serializers.IntegerField()
    demandes_acceptees = serializers.IntegerField()
    demandes_refusees = serializers.IntegerField()
    attributions_actives = serializers.IntegerField()
    montant_total_attribue = serializers.DecimalField(max_digits=15, decimal_places=2)
    montant_total_verse = serializers.DecimalField(max_digits=15, decimal_places=2)
