"""Provider confirmation for card payments."""

import hashlib
import hmac
import json
import os
import re
import time
from decimal import Decimal

import requests
from django.conf import settings

CURRENCY_EXPONENTS = {"EUR": 2, "USD": 2, "GBP": 2, "CAD": 2, "CHF": 2, "XOF": 0, "XAF": 0, "JPY": 0}
MANUAL_MODES = ("especes", "cheque", "virement")


class PaymentConfirmationRejected(Exception):
    """The provider did not confirm this invoice's payment."""


class PaymentProviderUnavailable(Exception):
    """The provider could not be contacted or is not configured."""


def verify_callback(body, signature):
    """Authenticate the original bytes, before parsing any untrusted event."""
    secret = os.environ.get("SIS_STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise PaymentProviderUnavailable
    try:
        parts = [part.split("=", 1) for part in signature.split(",")]
        timestamps = [value for key, value in parts if key == "t"]
        signatures = [value for key, value in parts if key == "v1"]
        if len(timestamps) != 1 or abs(time.time() - int(timestamps[0])) > 300:
            raise ValueError
        expected = hmac.new(
            secret.encode(), timestamps[0].encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        if not any(hmac.compare_digest(expected, value) for value in signatures):
            raise ValueError
        event = json.loads(body)
        if not isinstance(event, dict) or not event.get("id"):
            raise ValueError
        return event
    except (ValueError, TypeError) as exc:
        raise PaymentConfirmationRejected from exc


def provider_status():
    return {
        "carte": "configure" if os.environ.get("SIS_STRIPE_SECRET_KEY") else "non_configure",
        "callback": "configure" if os.environ.get("SIS_STRIPE_WEBHOOK_SECRET") else "non_configure",
        "mobile_money": "non_configure",
        "sepa": "non_configure",
        "autre": "non_configure",
        "modes_manuels": list(MANUAL_MODES),
        "devises": list(CURRENCY_EXPONENTS),
    }


def confirm_card_payment(paiement, facture, tenant, *, refunded=False):
    reference = paiement.reference_externe
    if not re.fullmatch(r"pi_[A-Za-z0-9]+", reference):
        raise PaymentConfirmationRejected
    secret = os.environ.get("SIS_STRIPE_SECRET_KEY", "")
    if not secret:
        raise PaymentProviderUnavailable

    try:
        response = requests.get(
            f"https://api.stripe.com/v1/payment_intents/{reference}",
            auth=(secret, ""),
            params={"expand[]": "latest_charge"},
            timeout=(3, 8),
        )
        if response.status_code == 404:
            raise PaymentConfirmationRejected
        response.raise_for_status()
        intent = response.json()
    except PaymentConfirmationRejected:
        raise
    except (requests.RequestException, ValueError) as exc:
        raise PaymentProviderUnavailable from exc

    currency = getattr(facture, "devise", "")
    if currency not in CURRENCY_EXPONENTS:
        raise PaymentConfirmationRejected
    expected_cents = paiement.montant * Decimal(10) ** CURRENCY_EXPONENTS[currency]
    metadata = intent.get("metadata") if isinstance(intent, dict) else None
    charge = intent.get("latest_charge") if isinstance(intent, dict) else None
    method = charge.get("payment_method_details") if isinstance(charge, dict) else None
    if not isinstance(metadata, dict) or not isinstance(charge, dict) or not isinstance(method, dict) or not (
        intent.get("id") == reference
        and intent.get("status") == "succeeded"
        and intent.get("livemode") is True
        and intent.get("currency") == currency.lower()
        and type(intent.get("amount")) is int
        and type(intent.get("amount_received")) is int
        and intent["amount"] == intent["amount_received"] == expected_cents
        and charge.get("paid") is True
        and charge.get("captured") is True
        and charge.get("disputed") is False
        and charge.get("refunded") is refunded
        and charge.get("amount_refunded") == (expected_cents if refunded else 0)
        and method.get("type") == "card"
        and metadata.get("sis_variant") == settings.SIS_VARIANT
        and metadata.get("sis_tenant_id") == str(tenant.pk)
        and metadata.get("sis_tenant_schema") == tenant.schema_name
        and metadata.get("sis_invoice") == facture.numero
    ):
        raise PaymentConfirmationRejected
