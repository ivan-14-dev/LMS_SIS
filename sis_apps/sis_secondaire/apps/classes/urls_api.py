"""URLs API for classes."""

from rest_framework.routers import DefaultRouter

from .api import ClassesViewSet, GroupesViewSet, MatieresViewSet, ProgrammesViewSet

app_name = "classes_api"

router = DefaultRouter()
router.register("classes", ClassesViewSet, basename="classe")
router.register("groupes", GroupesViewSet, basename="groupe")
router.register("matieres", MatieresViewSet, basename="matiere")
router.register("programmes", ProgrammesViewSet, basename="programme")

urlpatterns = router.urls
