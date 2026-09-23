"""URLs API for entreprises."""

from rest_framework.routers import DefaultRouter

from .api import ContactsEntrepriseViewSet, EntreprisesViewSet

app_name = "entreprises_api"

router = DefaultRouter()
router.register("entreprises", EntreprisesViewSet, basename="entreprise")
router.register("contacts-entreprises", ContactsEntrepriseViewSet, basename="contact-entreprise")

urlpatterns = router.urls
