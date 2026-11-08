"""API URLs for core."""

from apps.core.api import AcademicSearchView, WorkflowEventViewSet, WorkflowNotificationViewSet
from django.urls import path
from rest_framework.routers import DefaultRouter

from sis_common.complaints import ComplaintViewSet
from sis_common.delegations import DelegationViewSet
from sis_common.erp_correspondence import CorrespondanceViewSet
from sis_common.institutional_events import InstitutionalEventViewSet
from sis_common.projects import ProjectViewSet
from sis_common.signatures import SignatureMandateViewSet, SignatureViewSet
from sis_common.signed_documents import SignedDocumentViewSet
from sis_common.surveys import SurveyManagementViewSet

app_name = "core_api"

router = DefaultRouter()
router.register("evenements", InstitutionalEventViewSet, basename="evenements")
router.register("enquetes", SurveyManagementViewSet, basename="enquetes")
router.register("projets", ProjectViewSet, basename="projets")
router.register("workflow-events", WorkflowEventViewSet, basename="workflow-event")
router.register("notifications", WorkflowNotificationViewSet, basename="notifications")
router.register("reclamations", ComplaintViewSet, basename="reclamations")
router.register("delegations", DelegationViewSet, basename="delegations")
router.register("signatures", SignatureViewSet, basename="signatures")
router.register("mandats-signature", SignatureMandateViewSet, basename="mandats-signature")
router.register("documents-signes", SignedDocumentViewSet, basename="documents-signes")
router.register("correspondances", CorrespondanceViewSet, basename="correspondances")

urlpatterns = [
    path("recherche-academique/", AcademicSearchView.as_view(), name="recherche-academique"),
] + router.urls
