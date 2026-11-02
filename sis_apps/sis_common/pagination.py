from django.db.models import QuerySet
from rest_framework.pagination import PageNumberPagination


class SISPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        if isinstance(queryset, QuerySet) and not queryset.ordered:
            queryset = queryset.order_by("pk")
        return super().paginate_queryset(queryset, request, view)
