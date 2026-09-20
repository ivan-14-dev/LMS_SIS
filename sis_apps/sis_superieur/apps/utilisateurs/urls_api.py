"""URLs API for utilisateurs."""

from rest_framework.routers import DefaultRouter

from .api import GroupesPermissionsViewSet, PermissionsViewSet, UtilisateursViewSet

app_name = "utilisateurs_api"

router = DefaultRouter()
router.register("comptes", UtilisateursViewSet, basename="utilisateur")
router.register("groupes", GroupesPermissionsViewSet, basename="groupe-permission")
router.register("permissions", PermissionsViewSet, basename="permission")

urlpatterns = router.urls
