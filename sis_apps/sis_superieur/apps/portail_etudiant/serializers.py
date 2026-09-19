"""Serializers for portail étudiant (SIS Supérieur)."""

from rest_framework import serializers


class TableauBordEtudiantSerializer(serializers.Serializer):
    """Serializer pour le tableau de bord étudiant."""

    etudiant = serializers.DictField()
    inscription = serializers.DictField()
    statistiques = serializers.DictField()
    prochains_cours = serializers.ListField()
    notes_recentes = serializers.ListField()
    factures_impayees = serializers.ListField()
    notifications = serializers.ListField()


class ProfilEtudiantSerializer(serializers.Serializer):
    """Serializer pour le profil complet."""

    matricule = serializers.CharField()
    nom_complet = serializers.CharField()
    email = serializers.EmailField()
    formation = serializers.DictField()
    parcours = serializers.DictField(allow_null=True)
    annee_etude = serializers.IntegerField()
    statut = serializers.CharField()
    credits_valides = serializers.DecimalField(max_digits=5, decimal_places=2)
    credits_requis = serializers.DecimalField(max_digits=5, decimal_places=2)
    moyenne_generale = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True
    )


class NotesEtudiantSerializer(serializers.Serializer):
    """Serializer pour les notes de l'étudiant."""

    semestre = serializers.DictField()
    ues = serializers.ListField()
    moyenne = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    credits_valides = serializers.DecimalField(max_digits=5, decimal_places=2)
    mention = serializers.CharField(allow_blank=True)


class EmploiDuTempsEtudiantSerializer(serializers.Serializer):
    """Serializer pour l'emploi du temps."""

    semaine = serializers.IntegerField()
    jours = serializers.ListField()
