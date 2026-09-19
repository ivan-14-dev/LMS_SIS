"""URL configuration for SIS Secondaire."""

from apps.core.healthcheck import health as health_check
from apps.core.healthcheck import metrics
from apps.core.healthcheck import ready as readiness_check
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Healthcheck endpoints (public, no auth)
    path("health/", health_check, name="health-check"),
    path("ready/", readiness_check, name="readiness-check"),
    path("metrics/", metrics, name="metrics"),
    # Admin
    path("admin/", admin.site.urls),
    path("api/v1/", include("config.api_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"
    ),
    # Portails
    path("", include("apps.portail_eleve.urls")),
    path("comptes/", include("apps.utilisateurs.urls")),
    path("admin-portail/", include("apps.etablissement.urls_admin")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
