"""Review metadata kept separate from official SIS grades."""

from django.conf import settings
from django.db import models


class LMSGradeReviewModel(models.Model):
    proposed_evaluation = models.ForeignKey(
        "notes.Evaluation", on_delete=models.PROTECT, null=True, blank=True, related_name="lms_proposals"
    )
    proposed_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    proposed_scale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    proposed_academic_context = models.JSONField(default=dict, blank=True)
    review_status = models.CharField(
        max_length=16,
        default="retained",
        choices=[
            ("retained", "Conservée sans proposition"),
            ("pending", "À vérifier"),
            ("approved", "Validée"),
            ("rejected", "Refusée"),
        ],
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)

    class Meta:
        abstract = True
