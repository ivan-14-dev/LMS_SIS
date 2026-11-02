from rest_framework import serializers


class CurrentTenantDefault:
    requires_context = True

    def __call__(self, serializer_field):
        tenant = getattr(serializer_field.context.get("request"), "tenant", None)
        if tenant is None:
            raise serializers.SkipField()
        return tenant


class TenantBoundSerializerMixin:
    """Bind shared institution foreign keys to the tenant selected by the host."""

    tenant_field = "etablissement"

    def get_fields(self):
        fields = super().get_fields()
        if self.tenant_field in fields:
            fields[self.tenant_field].default = CurrentTenantDefault()
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        if tenant is not None:
            if self.tenant_field in self.fields:
                supplied = attrs.get(self.tenant_field)
                if supplied is not None and supplied.pk != tenant.pk:
                    raise serializers.ValidationError({self.tenant_field: "Établissement incorrect."})
                attrs[self.tenant_field] = tenant
            for name, value in attrs.items():
                references = [value]
                for year_field in ("annee_scolaire", "annee_universitaire"):
                    year = getattr(value, year_field, None)
                    if year is not None:
                        references.append(year)
                for reference in references:
                    for owner_field in ("etablissement_id", "universite_id"):
                        owner = getattr(reference, owner_field, None)
                        if owner is not None and owner != tenant.pk:
                            raise serializers.ValidationError({name: "Cet objet appartient à un autre établissement."})
        return attrs


class DateRangeSerializerMixin(TenantBoundSerializerMixin):
    date_range_fields = ("date_debut", "date_fin")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start_field, end_field = self.date_range_fields
        start = attrs.get(start_field, getattr(self.instance, start_field, None))
        end = attrs.get(end_field, getattr(self.instance, end_field, None))
        if start is not None and end is not None and end < start:
            raise serializers.ValidationError({end_field: "La fin ne peut pas précéder le début."})
        return attrs
