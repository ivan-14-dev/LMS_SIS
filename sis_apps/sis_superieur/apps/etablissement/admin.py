"""Admin for etablissement."""

from django.contrib import admin

from .models import AnneeUniversitaire, Domain, Semestre, Universite


@admin.register(Universite)
class UniversiteAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "ville", "pays", "actif")
    list_filter = ("type", "actif", "pays")
    search_fields = ("nom", "sigle", "uai", "ville")
    fieldsets = (
        (
            "Identité",
            {
                "fields": (
                    "nom",
                    "sigle",
                    "type",
                    "type_personnalise",
                    "uai",
                    "ministere_tutelle",
                )
            },
        ),
        (
            "Coordonnées",
            {
                "fields": (
                    "adresse",
                    "code_postal",
                    "ville",
                    "pays",
                    "telephone",
                    "email",
                    "site_web",
                )
            },
        ),
        (
            "Apparence et localisation",
            {
                "fields": (
                    "logo",
                    "couleur_primaire",
                    "couleur_secondaire",
                    "fuseau_horaire",
                )
            },
        ),
        (
            "Fonctionnalités",
            {
                "fields": (
                    "fonctionnalites",
                    "configuration_visio",
                    "systeme_notation",
                    "credits_annee",
                )
            },
        ),
        ("Exploitation", {"fields": ("schema_name", "actif")}),
    )


admin.site.register(Domain)
admin.site.register(AnneeUniversitaire)
admin.site.register(Semestre)
