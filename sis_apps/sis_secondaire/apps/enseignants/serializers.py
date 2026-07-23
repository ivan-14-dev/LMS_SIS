"""Serializers for enseignants (SIS Secondaire)."""
from rest_framework import serializers
from .models import Personnel, MatiereEnseignee, AffectationEnseignant


class PersonnelListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de personnel."""
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = Personnel
        fields = [
            'id', 'matricule', 'full_name', 'email',
            'statut', 'statut_display', 'corps',
            'date_embauche', 'heures_contractuelles',
        ]


class PersonnelDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour le détail d'un personnel."""
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = Personnel
        fields = [
            'id', 'user', 'matricule',
            'full_name', 'first_name', 'last_name', 'email', 'role',
            'statut', 'statut_display', 'date_embauche', 'corps',
            'diplomes', 'heures_contractuelles', 'indice',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'matricule', 'created_at', 'updated_at']
        extra_kwargs = {
            'rib': {'write_only': True},
            'iban': {'write_only': True},
        }


class MatiereEnseigneeSerializer(serializers.ModelSerializer):
    """Serializer pour les matières enseignées."""
    enseignant_nom = serializers.CharField(source='enseignant.user.get_full_name', read_only=True)
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    matiere_code = serializers.CharField(source='matiere.code', read_only=True)
    
    class Meta:
        model = MatiereEnseignee
        fields = [
            'id', 'enseignant', 'enseignant_nom',
            'matiere', 'matiere_nom', 'matiere_code',
            'niveau_competence', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class AffectationEnseignantSerializer(serializers.ModelSerializer):
    """Serializer pour les affectations enseignant."""
    enseignant_nom = serializers.CharField(source='enseignant.user.get_full_name', read_only=True)
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    classes_noms = serializers.SerializerMethodField()
    annee_libelle = serializers.CharField(source='annee_scolaire.libelle', read_only=True)
    
    class Meta:
        model = AffectationEnseignant
        fields = [
            'id', 'enseignant', 'enseignant_nom',
            'matiere', 'matiere_nom', 'classes', 'classes_noms',
            'heures_semaine', 'annee_scolaire', 'annee_libelle',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_classes_noms(self, obj):
        return [c.nom for c in obj.classes.all()]


class PersonnelCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de personnel."""
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=[('enseignant', 'Enseignant'), ('cpe', 'CPE'), ('administratif', 'Administratif')],
        default='enseignant'
    )
    
    class Meta:
        model = Personnel
        fields = [
            'username', 'email', 'first_name', 'last_name', 'password', 'role',
            'statut', 'date_embauche', 'corps', 'heures_contractuelles',
        ]
    
    def create(self, validated_data):
        from apps.utilisateurs.models import Utilisateur
        from django.utils import timezone
        import uuid
        
        role = validated_data.pop('role', 'enseignant')
        user_data = {
            'username': validated_data.pop('username'),
            'email': validated_data.pop('email'),
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'role': role,
        }
        password = validated_data.pop('password')
        
        user = Utilisateur(**user_data)
        user.set_password(password)
        user.save()
        
        matricule = f"PER{timezone.now().year}{uuid.uuid4().hex[:6].upper()}"
        
        personnel = Personnel.objects.create(
            user=user,
            matricule=matricule,
            **validated_data
        )
        return personnel
