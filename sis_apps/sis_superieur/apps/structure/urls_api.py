"""URLs API for structure."""

from rest_framework.routers import DefaultRouter

from .api import DepartementsViewSet, EcolesDoctoralesViewSet, FacultesViewSet

app_name = "structure_api"

router = DefaultRouter()
router.register("facultes", FacultesViewSet, basename="faculte")
router.register("departements", DepartementsViewSet, basename="departement")
router.register("ecoles-doctorales", EcolesDoctoralesViewSet, basename="ecole-doctorale")

urlpatterns = router.urls
