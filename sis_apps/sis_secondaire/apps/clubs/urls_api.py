"""URLs API for clubs."""

from rest_framework.routers import DefaultRouter

from .api import ClubsViewSet, MembresClubViewSet, SeancesClubViewSet

app_name = "clubs_api"

router = DefaultRouter()
router.register("clubs", ClubsViewSet, basename="club")
router.register("membres-clubs", MembresClubViewSet, basename="membre-club")
router.register("activites-clubs", SeancesClubViewSet, basename="seance-club")

urlpatterns = router.urls
