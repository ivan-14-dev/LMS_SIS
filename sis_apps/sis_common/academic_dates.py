from rest_framework import serializers

from sis_common.serializers import TenantBoundSerializerMixin


class AcademicDatesMixin(TenantBoundSerializerMixin):
    academic_year_field = None

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get("date_debut", getattr(self.instance, "date_debut", None))
        end = attrs.get("date_fin", getattr(self.instance, "date_fin", None))
        if start and end and start > end:
            raise serializers.ValidationError({"date_fin": "La fin doit suivre le début."})
        if self.instance and (getattr(self.instance, "cloturee", False) or getattr(self.instance, "cloture", False)):
            raise serializers.ValidationError("Une année ou période clôturée ne peut plus être modifiée.")
        if self.academic_year_field:
            year = attrs.get(
                self.academic_year_field,
                getattr(self.instance, self.academic_year_field, None),
            )
            if year and (year.cloturee or (start and start < year.date_debut) or (end and end > year.date_fin)):
                raise serializers.ValidationError(
                    {
                        self.academic_year_field: (
                            "La période doit appartenir à une année ouverte et rester dans ses dates."
                        )
                    }
                )
        return attrs
