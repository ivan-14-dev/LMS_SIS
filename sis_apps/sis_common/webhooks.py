"""Shared webhook validation utilities."""
import hashlib
import hmac


def verify_hmac_signature(secret: str, body: bytes, signature: str) -> bool:
    """Validate a SHA-256 webhook signature without accepting a fallback secret."""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))
