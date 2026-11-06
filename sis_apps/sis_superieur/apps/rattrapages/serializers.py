"""Serializers for rattrapages (SIS Supérieur)."""

from apps.etudiants.models import AffectationECUEIndividuelle, InscriptionPedagogique
from django.db.models import Q
from rest_framework import serializers

from .models import InscriptionRattrapage


class InscriptionRattrapageSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions au rattrapage."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    session_libelle = serializers.CharField(
        source="session_rattrapage.libelle", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = InscriptionRattrapage
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "ecue",
            "ecue_code",
            "ecue_nom",
            "session_rattrapage",
            "session_libelle",
            "statut",
            "statut_display",
            "date_inscription",
            "note",
            "date_echeance_inscription",
        ]
        read_only_fields = ["id", "date_inscription"]

    def validate_session_rattrapage(self, session):
        if session.type != "rattrapage":
            raise serializers.ValidationError("La session doit être un rattrapage.")
        return session

    def validate(self, attrs):
        attrs = super().validate(attrs)
        etudiant = attrs.get("etudiant", getattr(self.instance, "etudiant", None))
        ecue = attrs.get("ecue", getattr(self.instance, "ecue", None))
        session = attrs.get("session_rattrapage", getattr(self.instance, "session_rattrapage", None))
        semestre = session.semestre
        annee = semestre.annee_universitaire
        request = self.context.get("request")

        if (
            (request and annee.universite_id != request.tenant.pk)
            or etudiant.universite_id != annee.universite_id
            or ecue.ue.semestre_id != semestre.pk
            or ecue.ue.maquette.annee_universitaire_id != annee.pk
        ):
            raise serializers.ValidationError(
                {"ecue": "L'étudiant, l'ECUE et la session doivent relever du même semestre et de la même université."}
            )

        inscription = InscriptionPedagogique.objects.filter(
            inscription_admin__etudiant=etudiant,
            inscription_admin__annee_universitaire=annee,
            inscription_admin__formation_id=ecue.ue.maquette.formation_id,
            inscription_admin__statut="validee",
            semestre=semestre,
            statut="validee",
        ).filter(Q(ecues=ecue) | Q(ues=ecue.ue))
        affectation = AffectationECUEIndividuelle.objects.filter(
            inscription_admin__etudiant=etudiant,
            inscription_admin__annee_universitaire=annee,
            inscription_admin__formation_id=ecue.ue.maquette.formation_id,
            inscription_admin__statut="validee",
            semestre_cible=semestre,
            ecue=ecue,
        )
        if not inscription.exists() and not affectation.exists():
            raise serializers.ValidationError(
                {"etudiant": "Aucune inscription pédagogique validée ou affectation à cet ECUE pour cette session."}
            )
        return attrs
