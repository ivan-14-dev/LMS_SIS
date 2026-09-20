"""Administration de l'intégration Open edX."""

from django.contrib import admin

from .models import EdxAssessmentMapping, EdxGradeLog


@admin.register(EdxAssessmentMapping)
class EdxAssessmentMappingAdmin(admin.ModelAdmin):
    list_display = ("course", "subsection_id", "evaluation", "actif")
    list_filter = ("actif",)
    search_fields = ("course__course_id", "subsection_id", "evaluation__titre")
    raw_id_fields = ("course", "evaluation")


@admin.register(EdxGradeLog)
class EdxGradeLogAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment",
        "subsection_id",
        "score",
        "max_score",
        "imported_to_sis",
        "timestamp_lms",
    )
    list_filter = ("imported_to_sis",)
    search_fields = ("event_id", "subsection_id")
    readonly_fields = ("event_id", "created_at")
