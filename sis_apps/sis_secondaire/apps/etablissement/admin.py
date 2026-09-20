"""Admin for etablissement."""

from django.contrib import admin

from .models import AnneeScolaire, Domain, Etablissement, Periode


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "ville", "pays", "actif")
    list_filter = ("type", "actif", "pays")
    search_fields = ("nom", "uai", "ville")
    fieldsets = (
        (
            "Identité",
            {
                "fields": (
                    "nom",
                    "type",
                    "type_personnalise",
                    "uai",
                    "devise",
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
            {"fields": ("fonctionnalites", "configuration_visio", "systeme_periodes")},
        ),
        ("Exploitation", {"fields": ("schema_name", "actif")}),
    )


admin.site.register(Domain)
admin.site.register(AnneeScolaire)
admin.site.register(Periode)
