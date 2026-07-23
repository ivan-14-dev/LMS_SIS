"""URL configuration for SIS Supérieur."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.core.healthcheck import health_check, readiness_check, metrics

urlpatterns = [
    # Healthcheck endpoints (public, no auth)
    path("health/", health_check, name="health-check"),
    path("ready/", readiness_check, name="readiness-check"),
    path("metrics/", metrics, name="metrics"),
    # Admin
    path("admin/", admin.site.urls),
    path("api/v1/", include("config.api_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    # Portails
    path("", include("apps.portail_etudiant.urls")),
    path("comptes/", include("apps.utilisateurs.urls_auth")),
    path("admin-portail/", include("apps.etablissement.urls_admin")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
