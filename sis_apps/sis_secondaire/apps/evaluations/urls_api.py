"""URLs API for evaluations."""
from django.urls import path
from . import api

app_name = "evaluations_api"

urlpatterns = [
    # path("", api.EvaluationsViewSet.as_view({"get": "list", "post": "create"}), name="list"),
]
