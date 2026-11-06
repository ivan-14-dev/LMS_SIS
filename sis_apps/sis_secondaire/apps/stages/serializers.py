"""Serializers for stages (SIS Secondaire)."""

from rest_framework import serializers

from .models import ConventionStage, Entreprise, EvaluationStage, SuiviStage


class EntrepriseSerializer(serializers.ModelSerializer):
    """Serializer pour les entreprises."""

    nb_conventions = serializers.SerializerMethodField()

    class Meta:
        model = Entreprise
        fields = [
            "id",
            "raison_sociale",
            "siret",
            "secteur",
            "taille",
            "adresse",
            "code_postal",
            "ville",
            "telephone",
            "email",
            "contact_nom",
            "contact_fonction",
            "nb_conventions",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nb_conventions(self, obj):
        request = self.context.get("request")
        if request is None:
            return obj.conventions.count()
        from .api import visible_conventions

        return visible_conventions(request).filter(entreprise=obj).count()


class ConventionStageListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de conventions."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    entreprise_nom = serializers.CharField(
        source="entreprise.raison_sociale", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = ConventionStage
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "entreprise",
            "entreprise_nom",
            "date_debut",
            "date_fin",
            "duree_heures",
            "statut",
            "statut_display",
        ]


class ConventionStageDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une convention."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    entreprise_nom = serializers.CharField(
        source="entreprise.raison_sociale", read_only=True
    )
    maitre_stage_nom = serializers.CharField(
        source="maitre_stage_etablissement.get_full_name", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    suivis = serializers.SerializerMethodField()

    class Meta:
        model = ConventionStage
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "entreprise",
            "entreprise_nom",
            "tuteur_entreprise",
            "telephone_tuteur",
            "email_tuteur",
            "maitre_stage_etablissement",
            "maitre_stage_nom",
            "date_debut",
            "date_fin",
            "duree_heures",
            "remuneration",
            "missions",
            "horaires",
            "pdf_path",
            "statut",
            "statut_display",
            "date_signature_complete",
            "suivis",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "date_signature_complete"]

    def validate_statut(self, statut):
        if self.instance is None:
            if statut != "brouillon":
                raise serializers.ValidationError(
                    "Une nouvelle convention doit être en brouillon."
                )
        elif statut not in (self.instance.statut, "annulee"):
            raise serializers.ValidationError(
                "La signature doit passer par l'action signer."
            )
        return statut

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant_id = self.context["request"].tenant.pk
        eleve = attrs.get("eleve", getattr(self.instance, "eleve", None))
        maitre = attrs.get(
            "maitre_stage_etablissement",
            getattr(self.instance, "maitre_stage_etablissement", None),
        )
        if (
            eleve is not None
            and maitre is not None
            and (
                eleve.etablissement_id != tenant_id
                or eleve.user.etablissement_id != tenant_id
                or maitre.etablissement_id != tenant_id
            )
        ):
            raise serializers.ValidationError(
                "L'élève et le maître de stage doivent appartenir à l'établissement."
            )
        return attrs

    def get_suivis(self, obj):
        return SuiviStageSerializer(obj.suivis.all()[:5], many=True).data


class SuiviStageSerializer(serializers.ModelSerializer):
    """Serializer pour les suivis de stage."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = SuiviStage
        fields = [
            "id",
            "convention",
            "type",
            "type_display",
            "date",
            "commentaires",
            "appreciation",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_convention(self, convention):
        from .api import visible_conventions

        if not visible_conventions(self.context["request"]).filter(pk=convention.pk).exists():
            raise serializers.ValidationError("Convention inaccessible.")
        return convention


class EvaluationStageSerializer(serializers.ModelSerializer):
    """Serializer pour les évaluations de stage."""

    eleve_nom = serializers.CharField(
        source="convention.eleve.user.get_full_name", read_only=True
    )
    entreprise_nom = serializers.CharField(
        source="convention.entreprise.raison_sociale", read_only=True
    )

    class Meta:
        model = EvaluationStage
        fields = [
            "id",
            "convention",
            "eleve_nom",
            "entreprise_nom",
            "note_entreprise",
            "note_etablissement",
            "note_soutenance",
            "note_finale",
            "rapport",
            "appreciation_globale",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_convention(self, convention):
        from .api import visible_conventions

        if not visible_conventions(self.context["request"]).filter(pk=convention.pk).exists():
            raise serializers.ValidationError("Convention inaccessible.")
        return convention
