"""URLs API for utilisateurs."""

from rest_framework.routers import DefaultRouter

from .api import GroupesPermissionsViewSet, PermissionsViewSet, UtilisateursViewSet
from .guardian_links import GuardianLinksViewSet, GuardiansViewSet

app_name = "utilisateurs_api"

router = DefaultRouter()
router.register("comptes", UtilisateursViewSet, basename="utilisateur")
router.register("groupes", GroupesPermissionsViewSet, basename="groupe-permission")
router.register("permissions", PermissionsViewSet, basename="permission")
router.register("parents", GuardiansViewSet, basename="parent-affiliation")
router.register("liens-parent", GuardianLinksViewSet, basename="parent-link")

urlpatterns = router.urls
