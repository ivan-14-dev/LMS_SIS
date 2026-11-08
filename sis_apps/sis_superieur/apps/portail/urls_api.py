"""URLs API for consolidated portail."""

from rest_framework.routers import DefaultRouter

from sis_common.surveys import SurveyPortalViewSet

from .api import PortailApprenantViewSet, PortailStaffViewSet

app_name = "portail_api"

router = DefaultRouter()
router.register("enquetes", SurveyPortalViewSet, basename="portail-enquetes")
router.register("apprenant", PortailApprenantViewSet, basename="portail-apprenant")
router.register("staff", PortailStaffViewSet, basename="portail-staff")

urlpatterns = router.urls
