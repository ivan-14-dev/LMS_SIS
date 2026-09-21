"""Serializers for etudiants (SIS Supérieur)."""

from apps.utilisateurs.serializers import UtilisateurListSerializer
from rest_framework import serializers

from .models import AffectationECUEIndividuelle, Etudiant, InscriptionAdministrative


class EtudiantListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'étudiants."""

    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Etudiant
        fields = [
            "id",
            "matricule",
            "full_name",
            "email",
            "sexe",
            "statut",
            "statut_display",
            "regime",
            "boursier",
        ]


class EtudiantDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour le détail d'un étudiant."""

    user = UtilisateurListSerializer(read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    regime_display = serializers.CharField(source="get_regime_display", read_only=True)
    sexe_display = serializers.CharField(source="get_sexe_display", read_only=True)
    annee_universitaire_libelle = serializers.CharField(
        source="annee_universitaire_actuelle.libelle", read_only=True
    )

    class Meta:
        model = Etudiant
        fields = [
            "id",
            "user",
            "universite",
            "matricule",
            "ine",
            "date_naissance",
            "lieu_naissance",
            "sexe",
            "sexe_display",
            "nationalite",
            "adresse",
            "code_postal",
            "ville",
            "pays",
            "telephone",
            "email_personnel",
            "statut",
            "statut_display",
            "regime",
            "regime_display",
            "boursier",
            "date_premiere_inscription",
            "annee_universitaire_actuelle",
            "annee_universitaire_libelle",
            "photo",
            "contact_urgence_nom",
            "contact_urgence_tel",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "matricule", "created_at", "updated_at"]
        # Cacher les données sensibles
        extra_kwargs = {
            "numero_securite_sociale": {"write_only": True},
            "rib_iban": {"write_only": True},
        }


class EtudiantCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un étudiant."""

    # Données utilisateur imbriquées
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Etudiant
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "universite",
            "matricule",
            "ine",
            "date_naissance",
            "lieu_naissance",
            "sexe",
            "nationalite",
            "adresse",
            "code_postal",
            "ville",
            "pays",
            "telephone",
            "email_personnel",
            "regime",
            "boursier",
        ]

    def create(self, validated_data):
        from apps.utilisateurs.models import Utilisateur

        # Extraire les données utilisateur
        user_data = {
            "username": validated_data.pop("username"),
            "email": validated_data.pop("email"),
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "role": "etudiant",
        }
        password = validated_data.pop("password")

        # Créer l'utilisateur
        user = Utilisateur(**user_data)
        user.set_password(password)
        user.save()

        # Créer l'étudiant
        etudiant = Etudiant.objects.create(user=user, **validated_data)
        return etudiant


class InscriptionAdministrativeSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions administratives."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    formation_nom = serializers.CharField(source="formation.nom", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    annee_universitaire_libelle = serializers.CharField(
        source="annee_universitaire.libelle", read_only=True
    )

    class Meta:
        model = InscriptionAdministrative
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "annee_universitaire",
            "annee_universitaire_libelle",
            "formation",
            "formation_nom",
            "parcours",
            "date_inscription",
            "statut",
            "statut_display",
            "regime",
            "bourse_id",
            "pieces_fournies",
            "payeur",
            "motif_refus",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EtudiantSearchSerializer(serializers.Serializer):
    """Serializer pour la recherche d'étudiants."""

    q = serializers.CharField(
        required=False, help_text="Recherche par nom, prénom ou matricule"
    )
    statut = serializers.ChoiceField(choices=Etudiant.STATUT_CHOICES, required=False)
    regime = serializers.ChoiceField(choices=Etudiant.REGIME_CHOICES, required=False)
    boursier = serializers.BooleanField(required=False)
    annee_universitaire = serializers.IntegerField(required=False)


class AffectationECUEIndividuelleSerializer(serializers.ModelSerializer):
    """Serializer pour les ECUE individualisés d'un étudiant."""

    semestre_cible_libelle = serializers.SerializerMethodField()
    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    ue_code = serializers.CharField(source="ecue.ue.code", read_only=True)
    ue_nom = serializers.CharField(source="ecue.ue.nom", read_only=True)
    source_semestre = serializers.SerializerMethodField()

    class Meta:
        model = AffectationECUEIndividuelle
        fields = [
            "id",
            "inscription_admin",
            "semestre_cible",
            "semestre_cible_libelle",
            "ecue",
            "ecue_code",
            "ecue_nom",
            "ue_code",
            "ue_nom",
            "source_semestre",
            "obligatoire",
            "groupe_td",
            "groupe_tp",
            "commentaire",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_semestre_cible_libelle(self, obj):
        return str(obj.semestre_cible)

    def get_source_semestre(self, obj):
        return str(obj.ecue.ue.semestre)

    def validate(self, attrs):
        etudiant = self.context.get("etudiant") or getattr(
            getattr(self.instance, "inscription_admin", None), "etudiant", None
        )
        inscription_admin = attrs.get("inscription_admin") or getattr(
            self.instance, "inscription_admin", None
        )
        semestre_cible = attrs.get("semestre_cible") or getattr(
            self.instance, "semestre_cible", None
        )
        if etudiant and inscription_admin and inscription_admin.etudiant_id != etudiant.id:
            raise serializers.ValidationError(
                {"inscription_admin": "Cette inscription administrative n'appartient pas à cet étudiant."}
            )
        if inscription_admin and semestre_cible and (
            inscription_admin.annee_universitaire_id != semestre_cible.annee_universitaire_id
        ):
            raise serializers.ValidationError(
                {
                    "semestre_cible": (
                        "Le semestre cible doit appartenir à la même année universitaire que l'inscription administrative."
                    )
                }
            )
        return attrs
