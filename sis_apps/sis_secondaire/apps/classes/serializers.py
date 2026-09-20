"""Serializers for classes (SIS Secondaire)."""

from rest_framework import serializers

from .models import Classe, Groupe, Matiere, ProgrammeMatiere


class ClasseListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de classes."""

    niveau_nom = serializers.CharField(source="niveau.libelle", read_only=True)
    annee_libelle = serializers.CharField(
        source="annee_scolaire.libelle", read_only=True
    )
    prof_principal_nom = serializers.CharField(
        source="prof_principal.get_full_name", read_only=True
    )
    effectif = serializers.IntegerField(source="effectif_actuel", read_only=True)

    class Meta:
        model = Classe
        fields = [
            "id",
            "nom",
            "niveau",
            "niveau_nom",
            "annee_scolaire",
            "annee_libelle",
            "prof_principal",
            "prof_principal_nom",
            "effectif_max",
            "effectif",
            "color",
        ]


class ClasseDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour le détail d'une classe."""

    niveau_nom = serializers.CharField(source="niveau.libelle", read_only=True)
    annee_libelle = serializers.CharField(
        source="annee_scolaire.libelle", read_only=True
    )
    prof_principal_nom = serializers.CharField(
        source="prof_principal.get_full_name", read_only=True
    )
    salle_nom = serializers.CharField(source="salle_principale.nom", read_only=True)
    effectif = serializers.IntegerField(source="effectif_actuel", read_only=True)

    class Meta:
        model = Classe
        fields = [
            "id",
            "etablissement",
            "nom",
            "niveau",
            "niveau_nom",
            "annee_scolaire",
            "annee_libelle",
            "prof_principal",
            "prof_principal_nom",
            "salle_principale",
            "salle_nom",
            "effectif_max",
            "effectif",
            "color",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class GroupeSerializer(serializers.ModelSerializer):
    """Serializer pour les groupes."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    classes_noms = serializers.SerializerMethodField()

    class Meta:
        model = Groupe
        fields = [
            "id",
            "etablissement",
            "annee_scolaire",
            "nom",
            "type",
            "type_display",
            "capacite",
            "classes",
            "classes_noms",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_classes_noms(self, obj):
        return [c.nom for c in obj.classes.all()]


class MatiereListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de matières."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Matiere
        fields = [
            "id",
            "code",
            "nom",
            "type",
            "type_display",
            "couleur",
            "coefficient_defaut",
        ]


class MatiereDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une matière."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Matiere
        fields = [
            "id",
            "etablissement",
            "code",
            "nom",
            "type",
            "type_display",
            "couleur",
            "coefficient_defaut",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ProgrammeMatiereSerializer(serializers.ModelSerializer):
    """Serializer pour les programmes de matières."""

    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    matiere_nom = serializers.CharField(source="matiere.nom", read_only=True)
    matiere_code = serializers.CharField(source="matiere.code", read_only=True)
    enseignant_nom = serializers.CharField(
        source="enseignant_principal.get_full_name", read_only=True
    )

    class Meta:
        model = ProgrammeMatiere
        fields = [
            "id",
            "classe",
            "classe_nom",
            "matiere",
            "matiere_nom",
            "matiere_code",
            "coefficient",
            "credits",
            "heures_semaine",
            "obligatoire",
            "enseignant_principal",
            "enseignants",
            "enseignant_nom",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
