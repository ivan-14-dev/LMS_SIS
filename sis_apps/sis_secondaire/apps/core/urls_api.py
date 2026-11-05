"""API URLs for core."""

from apps.core.api import WorkflowEventViewSet, WorkflowNotificationViewSet
from rest_framework.routers import DefaultRouter

from sis_common.complaints import ComplaintViewSet
from sis_common.delegations import DelegationViewSet
from sis_common.erp_correspondence import CorrespondanceViewSet
from sis_common.signatures import SignatureMandateViewSet, SignatureViewSet
from sis_common.signed_documents import SignedDocumentViewSet

app_name = "core_api"

router = DefaultRouter()
router.register("workflow-events", WorkflowEventViewSet, basename="workflow-event")
router.register("notifications", WorkflowNotificationViewSet, basename="notifications")
router.register("reclamations", ComplaintViewSet, basename="reclamations")
router.register("delegations", DelegationViewSet, basename="delegations")
router.register("signatures", SignatureViewSet, basename="signatures")
router.register("mandats-signature", SignatureMandateViewSet, basename="mandats-signature")
router.register("documents-signes", SignedDocumentViewSet, basename="documents-signes")
router.register("correspondances", CorrespondanceViewSet, basename="correspondances")

urlpatterns = router.urls
