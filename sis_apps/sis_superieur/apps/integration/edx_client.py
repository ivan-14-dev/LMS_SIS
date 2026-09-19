"""Client de communication bidirectionnelle LMS + CMS Open edX (SIS Supérieur)."""

import hashlib
import hmac
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class EdxClientError(Exception):
    """Exception de base pour les erreurs du client EdX."""

    pass


class EdxAuthenticationError(EdxClientError):
    """Erreur d'authentification OAuth."""

    pass


class EdxApiError(EdxClientError):
    """Erreur lors d'un appel API."""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


def retry_on_failure(max_retries: int = 3, backoff_factor: float = 0.5):
    """Décorateur pour retry avec backoff exponentiel."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, EdxApiError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2**attempt)
                        logger.warning(
                            f"Tentative {attempt + 1}/{max_retries} échouée pour {func.__name__}, "
                            f"retry dans {wait_time}s: {e}"
                        )
                        time.sleep(wait_time)
            raise last_exception

        return wrapper

    return decorator


class EdxClient:
    """Client HTTP pour Open edX LMS + CMS avec retry et validation."""

    def __init__(
        self,
        lms_url: str = None,
        cms_url: str = None,
        oauth_client_id: str = None,
        oauth_client_secret: str = None,
        timeout: int = 30,
        verify_ssl: bool = True,
    ):
        self.lms_url = lms_url or getattr(settings, "EDX_LMS_URL", None)
        self.cms_url = cms_url or getattr(settings, "EDX_CMS_URL", None)
        self.oauth_client_id = oauth_client_id or getattr(
            settings, "EDX_OAUTH_CLIENT_ID", None
        )
        self.oauth_client_secret = oauth_client_secret or getattr(
            settings, "EDX_OAUTH_CLIENT_SECRET", None
        )
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._access_token: str | None = None
        self._token_expires_at: float = 0

        # Validation des paramètres obligatoires
        self._validate_configuration()

        # Normalisation des URLs
        if self.lms_url:
            self.lms_url = self.lms_url.rstrip("/")
        if self.cms_url:
            self.cms_url = self.cms_url.rstrip("/")

    def _validate_configuration(self) -> None:
        """Valide que la configuration est complète."""
        missing = []
        if not self.lms_url:
            missing.append("EDX_LMS_URL")
        if not self.oauth_client_id:
            missing.append("EDX_OAUTH_CLIENT_ID")
        if not self.oauth_client_secret:
            missing.append("EDX_OAUTH_CLIENT_SECRET")

        if missing:
            raise ImproperlyConfigured(
                f"Configuration EdX incomplète. Variables manquantes: {', '.join(missing)}. "
                "Consultez sis_apps/docs/ROADMAP_OPERATIONNEL.md pour la configuration."
            )

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def _get_access_token(self) -> str:
        """Obtient un token OAuth avec retry."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        url = f"{self.lms_url}/oauth2/access_token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.oauth_client_id,
            "client_secret": self.oauth_client_secret,
            "token_type": "jwt",
        }

        try:
            r = requests.post(
                url, data=data, timeout=self.timeout, verify=self.verify_ssl
            )
            r.raise_for_status()
        except requests.HTTPError as e:
            logger.error(f"Échec d'authentification OAuth: {e}")
            raise EdxAuthenticationError(
                f"Impossible d'obtenir un token OAuth: {e}"
            ) from e
        except requests.RequestException as e:
            logger.error(f"Erreur réseau lors de l'authentification: {e}")
            raise EdxClientError(f"Erreur de connexion au LMS: {e}") from e

        payload = r.json()
        self._access_token = payload["access_token"]
        self._token_expires_at = time.time() + payload.get("expires_in", 3600)
        logger.debug("Token OAuth obtenu avec succès")
        return self._access_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"JWT {self._get_access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _handle_response(self, response: requests.Response, operation: str) -> dict:
        """Gère la réponse HTTP et lève les exceptions appropriées."""
        try:
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.HTTPError as e:
            error_body = {}
            try:
                error_body = response.json()
            except Exception:
                pass
            logger.error(
                f"Erreur API EdX ({operation})",
                extra={
                    "status_code": response.status_code,
                    "error": error_body,
                    "url": response.url,
                },
            )
            raise EdxApiError(
                f"{operation} a échoué: {e}",
                status_code=response.status_code,
                response=error_body,
            ) from e

    # ---------- USERS ----------

    def create_user(
        self,
        username,
        email,
        full_name,
        is_staff=False,
        is_superuser=False,
        role="student",
        extra=None,
    ) -> dict:
        url = f"{self.lms_url}/api/user/v1/accounts"
        data = {
            "username": username,
            "email": email,
            "name": full_name,
            "is_staff": is_staff,
            "is_superuser": is_superuser,
            "role": role,
        }
        if extra:
            data.update(extra)
        r = requests.post(url, json=data, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def update_user(self, username, data) -> dict:
        url = f"{self.lms_url}/api/user/v1/accounts/{username}"
        r = requests.patch(
            url, json=data, headers=self._headers(), timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    def deactivate_user(self, username) -> bool:
        url = f"{self.lms_url}/api/user/v1/accounts/{username}/deactivate"
        return (
            requests.post(
                url, headers=self._headers(), timeout=self.timeout
            ).status_code
            == 200
        )

    def get_user(self, username) -> dict | None:
        url = f"{self.lms_url}/api/user/v1/accounts/{username}"
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    # ---------- COURSES (CMS) ----------

    def create_course(self, org, number, run, display_name, course_data=None) -> dict:
        url = f"{self.cms_url}/api/courses/v1/courses/"
        data = {"org": org, "number": number, "run": run, "display_name": display_name}
        if course_data:
            data.update(course_data)
        r = requests.post(url, json=data, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_course(self, course_key) -> dict | None:
        url = f"{self.cms_url}/api/courses/v1/courses/{course_key}"
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def update_course(self, course_key, data) -> dict:
        url = f"{self.cms_url}/api/courses/v1/courses/{course_key}"
        r = requests.patch(
            url, json=data, headers=self._headers(), timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    def publish_course(self, course_key) -> dict:
        url = f"{self.cms_url}/api/courses/v1/courses/{course_key}/publish"
        r = requests.post(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def create_course_block(
        self,
        course_key,
        parent_locator,
        block_type,
        display_name,
        category="vertical",
        metadata=None,
    ) -> dict:
        url = f"{self.cms_url}/api/xblock/v1/xblocks/"
        data = {
            "course_id": course_key,
            "parent_locator": parent_locator,
            "category": category,
            "type": block_type,
            "display_name": display_name,
        }
        if metadata:
            data["metadata"] = metadata
        r = requests.post(url, json=data, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def update_block(self, block_id, data) -> dict:
        url = f"{self.cms_url}/api/xblock/v1/xblocks/{block_id}"
        r = requests.patch(
            url, json=data, headers=self._headers(), timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    def delete_block(self, block_id) -> bool:
        url = f"{self.cms_url}/api/xblock/v1/xblocks/{block_id}"
        return requests.delete(
            url, headers=self._headers(), timeout=self.timeout
        ).status_code in (200, 204)

    def upload_asset(self, course_key, file_path, content) -> dict:
        """Upload un asset (PDF, image, etc.) dans Studio."""
        url = f"{self.cms_url}/api/assets/v1/assets/{course_key}/"
        files = {"file": (file_path, content)}
        headers = {"Authorization": f"JWT {self._get_access_token()}"}
        r = requests.post(url, files=files, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- ENROLLMENTS ----------

    def enroll_user(self, course_key, username, mode="audit") -> dict:
        url = f"{self.lms_url}/api/enrollment/v1/enrollment"
        data = {
            "course_id": course_key,
            "username": username,
            "mode": mode,
            "is_active": True,
        }
        r = requests.post(
            url, json=[data], headers=self._headers(), timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()[0] if isinstance(r.json(), list) else r.json()

    def unenroll_user(self, course_key, username) -> bool:
        url = f"{self.lms_url}/api/enrollment/v1/enrollment"
        data = {"course_id": course_key, "username": username}
        return requests.delete(
            url, json=data, headers=self._headers(), timeout=self.timeout
        ).status_code in (200, 204)

    def get_enrollments(self, course_key) -> list[dict]:
        url = f"{self.lms_url}/api/enrollment/v1/enrollment"
        r = requests.get(
            url,
            params={"course_id": course_key},
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def bulk_enroll(self, course_key, usernames, mode="audit") -> list[dict]:
        url = f"{self.lms_url}/api/enrollment/v1/enrollment"
        data = [
            {"course_id": course_key, "username": u, "mode": mode, "is_active": True}
            for u in usernames
        ]
        r = requests.post(url, json=data, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- GRADES ----------

    def post_grade(
        self, course_key, username, subsection_id, score, max_score=100.0
    ) -> dict:
        url = f"{self.lms_url}/api/grades/v1/grade_override/{course_key}/{username}/"
        data = {"subsection_id": subsection_id, "score": score, "max_score": max_score}
        r = requests.post(url, json=data, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_grades(self, course_key, username) -> dict:
        url = f"{self.lms_url}/api/grades/v1/grades/{course_key}/{username}/"
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- COHORTS ----------

    def add_to_cohort(self, course_key, username, cohort_name) -> dict:
        url = f"{self.lms_url}/api/cohorts/v1/courses/{course_key}/cohorts/{cohort_name}/add/"
        r = requests.post(
            url,
            json={"users": [username]},
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def create_cohort(self, course_key, cohort_name, assignment_type="random") -> dict:
        url = f"{self.lms_url}/api/cohorts/v1/courses/{course_key}/cohorts/"
        data = {"name": cohort_name, "assignment_type": assignment_type}
        r = requests.post(url, json=data, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- CERTIFICATES ----------

    def issue_certificate(self, course_key, username, certificate_type="honor") -> dict:
        url = f"{self.lms_url}/api/certificates/v1/certificates"
        data = {
            "course_id": course_key,
            "username": username,
            "certificate_type": certificate_type,
        }
        r = requests.post(url, json=data, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- WEBHOOKS ----------

    def register_webhook(self, target_url, event_type, secret) -> dict:
        url = f"{self.lms_url}/api/webhooks/v1/webhooks/"
        data = {
            "url": target_url,
            "event_type": event_type,
            "secret": secret,
            "active": True,
        }
        r = requests.post(url, json=data, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def sign_payload(payload, secret) -> str:
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    @staticmethod
    def verify_signature(payload, signature, secret) -> bool:
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.replace("sha256=", ""))

    def health_check(self) -> dict[str, Any]:
        results = {}
        for name, base in [("lms", self.lms_url), ("cms", self.cms_url)]:
            try:
                r = requests.get(f"{base}/heartbeat", timeout=5)
                results[name] = {"status": r.status_code, "ok": r.status_code == 200}
            except Exception as e:
                results[name] = {"status": None, "ok": False, "error": str(e)}
        return results


_client: EdxClient | None = None


def get_edx_client() -> EdxClient:
    global _client
    if _client is None:
        _client = EdxClient()
    return _client
