"""Serializers for ECTS (SIS Supérieur)."""

from rest_framework import serializers

from .models import BilanECTS


class BilanECTSSerializer(serializers.ModelSerializer):
    """Serializer pour les bilans ECTS."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    annee_libelle = serializers.CharField(
        source="annee_universitaire.libelle", read_only=True
    )
    formation_nom = serializers.CharField(
        source="inscription_admin.formation.nom", read_only=True
    )
    taux_validation = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    ues_validees_list = serializers.SerializerMethodField()
    ues_compensees_list = serializers.SerializerMethodField()
    ues_echec_list = serializers.SerializerMethodField()

    class Meta:
        model = BilanECTS
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "annee_universitaire",
            "annee_libelle",
            "inscription_admin",
            "formation_nom",
            "credits_inscrits",
            "credits_valides",
            "credits_compenses",
            "credits_echec",
            "moyenne_ponderee",
            "taux_validation",
            "ues_validees",
            "ues_validees_list",
            "ues_compensees",
            "ues_compensees_list",
            "ues_echec",
            "ues_echec_list",
            "date_calcul",
            "created_at",
        ]
        read_only_fields = ["id", "date_calcul", "created_at"]
        extra_kwargs = {
            field: {"min_value": 0}
            for field in (
                "credits_inscrits",
                "credits_valides",
                "credits_compenses",
                "credits_echec",
            )
        }

    def validate(self, attrs):
        if self.instance is None or {"credits_inscrits", "credits_valides"} & attrs.keys():
            inscrits = attrs.get(
                "credits_inscrits", getattr(self.instance, "credits_inscrits", 0)
            )
            valides = attrs.get(
                "credits_valides", getattr(self.instance, "credits_valides", 0)
            )
            if valides > inscrits:
                raise serializers.ValidationError(
                    {"credits_valides": "Les crédits validés ne peuvent pas dépasser les crédits inscrits."}
                )

        inscription = attrs.get("inscription_admin")
        if inscription is None and self.instance is not None:
            inscription = self.instance.inscription_admin
        if inscription is None:
            return attrs

        for field in ("etudiant", "annee_universitaire"):
            identity_id = (
                attrs[field].pk
                if field in attrs
                else getattr(self.instance, f"{field}_id", None)
            )
            if identity_id is not None and identity_id != getattr(inscription, f"{field}_id"):
                raise serializers.ValidationError(
                    {field: "Le bilan doit correspondre à l'inscription administrative."}
                )
        return attrs

    def get_ues_validees_list(self, obj):
        return [
            {"id": ue.id, "code": ue.code, "nom": ue.nom, "credits": ue.credits}
            for ue in obj.ues_validees.all()
        ]

    def get_ues_compensees_list(self, obj):
        return [
            {"id": ue.id, "code": ue.code, "nom": ue.nom, "credits": ue.credits}
            for ue in obj.ues_compensees.all()
        ]

    def get_ues_echec_list(self, obj):
        return [
            {"id": ue.id, "code": ue.code, "nom": ue.nom, "credits": ue.credits}
            for ue in obj.ues_echec.all()
        ]
