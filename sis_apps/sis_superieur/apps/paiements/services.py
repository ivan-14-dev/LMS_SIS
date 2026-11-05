"""Provider confirmation for card payments."""

import os
import re
from decimal import Decimal

import requests
from django.conf import settings


class PaymentConfirmationRejected(Exception):
    """The provider did not confirm this invoice's payment."""


class PaymentProviderUnavailable(Exception):
    """The provider could not be contacted or is not configured."""


def confirm_card_payment(paiement, facture, tenant):
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

    expected_cents = paiement.montant * Decimal("100")
    metadata = intent.get("metadata") if isinstance(intent, dict) else None
    charge = intent.get("latest_charge") if isinstance(intent, dict) else None
    method = charge.get("payment_method_details") if isinstance(charge, dict) else None
    if not isinstance(metadata, dict) or not isinstance(charge, dict) or not isinstance(method, dict) or not (
        intent.get("id") == reference
        and intent.get("status") == "succeeded"
        and intent.get("livemode") is True
        and intent.get("currency") == "eur"
        and type(intent.get("amount")) is int
        and type(intent.get("amount_received")) is int
        and intent["amount"] == intent["amount_received"] == expected_cents
        and charge.get("paid") is True
        and charge.get("captured") is True
        and charge.get("disputed") is False
        and charge.get("refunded") is False
        and charge.get("amount_refunded") == 0
        and method.get("type") == "card"
        and metadata.get("sis_variant") == settings.SIS_VARIANT
        and metadata.get("sis_tenant_id") == str(tenant.pk)
        and metadata.get("sis_tenant_schema") == tenant.schema_name
        and metadata.get("sis_invoice") == facture.numero
    ):
        raise PaymentConfirmationRejected
