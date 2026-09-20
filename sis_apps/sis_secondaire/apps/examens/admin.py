"""Administration des examens."""

from django.contrib import admin

from .models import (
    AffectationCorrection,
    AuditCopieExamen,
    CopieExamen,
    CorrectionCopie,
    EpreuveExamen,
    SessionExamen,
)

admin.site.register(SessionExamen)
admin.site.register(EpreuveExamen)


@admin.register(CopieExamen)
class CopieExamenAdmin(admin.ModelAdmin):
    list_display = ("numero_anonyme", "statut", "note_finale", "deposee_le")
    list_filter = ("statut",)
    search_fields = ("numero_anonyme", "empreinte_sha256")
    exclude = ("fichier",)
    readonly_fields = (
        "numero_anonyme",
        "empreinte_sha256",
        "taille_octets",
        "deposee_par",
        "deposee_le",
    )


admin.site.register(AffectationCorrection)
admin.site.register(CorrectionCopie)


@admin.register(AuditCopieExamen)
class AuditCopieExamenAdmin(admin.ModelAdmin):
    list_display = ("copie", "acteur", "action", "cree_le")
    readonly_fields = ("copie", "acteur", "action", "details", "cree_le")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
