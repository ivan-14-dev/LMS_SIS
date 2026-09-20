# Configuration de base pour SIS Supérieur
import os
import sys
from pathlib import Path

from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent
SIS_APPS_DIR = BASE_DIR.parent
if str(SIS_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(SIS_APPS_DIR))
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

from sis_common.config import (
    get_allowed_hosts,
    get_bool_environment,
    get_required_secret,
)

# =============================================================================
# SECURITY - Configuration obligatoire
# =============================================================================

SECRET_KEY = get_required_secret(
    "DJANGO_SECRET_KEY", test_value="test-secret-key-for-testing-only"
)
DEBUG = get_bool_environment("DJANGO_DEBUG")
ALLOWED_HOSTS = get_allowed_hosts()

# Application
DJANGO_APPS = [
    "django_tenants",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "auditlog",
    "simple_history",
    "import_export",
    "guardian",
    "crispy_forms",
    "crispy_tailwind",
    "django_tables2",
    "django_celery_beat",
    "axes",
    "mfa",
    "modeltranslation",
]

# Apps métier du SIS Supérieur
LOCAL_APPS = [
    "apps.core",
    "apps.etablissement",
    "apps.utilisateurs",
    "apps.structure",
    "apps.formations",
    "apps.maquettes",
    "apps.ue_ecue",
    "apps.etudiants",
    "apps.inscriptions",
    "apps.ects",
    "apps.mobilite",
    "apps.emplois_du_temps",
    "apps.notes",
    "apps.examens",
    "apps.rattrapages",
    "apps.jurys",
    "apps.releves",
    "apps.diplomes",
    "apps.memoires",
    "apps.stages",
    "apps.bourses",
    "apps.paiements",
    "apps.recherche",
    "apps.bibliotheque",
    "apps.entreprises",
    "apps.enseignants",
    "apps.portail_enseignant",
    "apps.portail_etudiant",
    "apps.portail_doyen",
    "apps.portail_scolarite",
    "apps.integration",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Middleware
MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "apps.core.middleware.AuditLogMiddleware",
    "apps.core.middleware.TenantContextMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.tenant_context",
            ],
        },
    },
]

# Database - multi-tenant (schema per tenant)
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.environ.get("DB_NAME", "sis_superieur"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# Tenancy
TENANT_MODEL = "etablissement.Universite"
TENANT_DOMAIN_MODEL = "etablissement.Domain"
SHARED_APPS = (
    "django_tenants",
    "apps.core",
    "apps.etablissement",
)
TENANT_APPS = tuple(
    app for app in LOCAL_APPS if app not in ("apps.core", "apps.etablissement")
) + tuple(THIRD_PARTY_APPS)

# Cache
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "sis_u",
    }
}

# Celery
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/2")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/3")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Europe/Paris"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Auth
AUTH_USER_MODEL = "utilisateurs.Utilisateur"
LOGIN_URL = "/comptes/connexion/"
LOGIN_REDIRECT_URL = "/tableau-de-bord/"
LOGOUT_REDIRECT_URL = "/comptes/connexion/"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
]

# Password
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalisation
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("fr", "Français"),
    ("en", "English"),
    ("ar", "العربية"),
    ("es", "Español"),
]

# Static
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
PRIVATE_EXAM_STORAGE_ROOT = Path(
    os.environ.get("PRIVATE_EXAM_STORAGE_ROOT", BASE_DIR / "private_exam_copies")
)
EXAM_COPY_MAX_SIZE = int(os.environ.get("EXAM_COPY_MAX_SIZE", 25 * 1024 * 1024))
PRIVATE_FINANCIAL_STORAGE_ROOT = Path(
    os.environ.get(
        "PRIVATE_FINANCIAL_STORAGE_ROOT", BASE_DIR / "private_financial_documents"
    )
)
PAYMENT_PROOF_MAX_SIZE = int(
    os.environ.get("PAYMENT_PROOF_MAX_SIZE", 10 * 1024 * 1024)
)

# Security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "sis_common.authentication.EdxJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10/minute",
        "user": "100/minute",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SIS Supérieur API",
    "DESCRIPTION": "API du Système d'Information pour Universités et Grandes Écoles",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# CORS
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (*default_headers, "use-jwt-cookie")
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# Audit
AUDITLOG_INCLUDE_TRACKING_MODELS = [
    "etudiants.Etudiant",
    "notes.Note",
    "releves.ReleveNotes",
    "paiements.FactureFrais",
    "paiements.PaiementFrais",
]

# Axes (anti-brute force)
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # heures
AXES_LOCKOUT_PARAMETERS = ["username"]

# Use English for internal messages
USE_L10N = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "apps.core.logging.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "sis.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "json",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": os.environ.get("LOG_LEVEL", "INFO"),
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "INFO",
        },
    },
}

# ====================== Open edX Integration ======================
EDX_LMS_URL = os.environ.get("EDX_LMS_URL", "http://localhost:8000")
EDX_CMS_URL = os.environ.get("EDX_CMS_URL", "http://localhost:8001")
EDX_OAUTH_CLIENT_ID = get_required_secret(
    "EDX_OAUTH_CLIENT_ID", test_value="sis-superieur-test-client"
)
EDX_OAUTH_CLIENT_SECRET = get_required_secret(
    "EDX_OAUTH_CLIENT_SECRET", test_value="test-oauth-secret"
)
EDX_JWT_ISSUER = os.environ.get("EDX_JWT_ISSUER", f"{EDX_LMS_URL.rstrip('/')}/oauth2")
EDX_JWT_AUDIENCE = get_required_secret(
    "EDX_JWT_AUDIENCE", test_value="sis-test-audience"
)
EDX_JWT_PUBLIC_SIGNING_JWK_SET = get_required_secret(
    "EDX_JWT_PUBLIC_SIGNING_JWK_SET", test_value='{"keys":[]}'
)
EDX_JWT_ALGORITHM = "RS512"
EDX_JWT_LEEWAY = 5
EDX_JWT_COOKIE_HEADER_PAYLOAD = os.environ.get(
    "EDX_JWT_COOKIE_HEADER_PAYLOAD", "edx-jwt-cookie-header-payload"
)
EDX_JWT_COOKIE_SIGNATURE = os.environ.get(
    "EDX_JWT_COOKIE_SIGNATURE", "edx-jwt-cookie-signature"
)
WEBHOOK_SECRET = get_required_secret("WEBHOOK_SECRET", test_value="test-webhook-secret")
SIS_WEBHOOK_LMS_URL = f"{EDX_LMS_URL}/api/webhooks/v1/webhooks/"
