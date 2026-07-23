"""URLs API for examens."""
from django.urls import path
from . import api

app_name = "examens_api"

urlpatterns = [
    # path("", api.ExamensViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
