"""WhatsApp webhook signature verification."""
import hashlib
import hmac
import logfire
from fastapi import Header, HTTPException, Request
from typing import Optional, Tuple

from server.core.config.whatsapp_config import WhatsAppConfig


class WhatsAppSignatureVerifier:
    """Handles WhatsApp webhook signature verification."""

    @staticmethod
    def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
        """
        Verify the HMAC signature of the webhook request.

        Args:
            raw_body: The raw request body bytes
            signature_header: The X-Hub-Signature-256 header value

        Returns:
            True if signature is valid, False otherwise
        """
        if signature_header is None:
            logfire.warning("Request rejected: Missing X-Hub-Signature-256 header.")
            return False

        # The header is in the format "sha256=xxxxxxxx...", extract the hash part
        if not signature_header.startswith(WhatsAppConfig.SIGNATURE_HEADER_PREFIX):
            logfire.warning("Request rejected: Invalid signature format.")
            return False

        hmac_received = signature_header.removeprefix(WhatsAppConfig.SIGNATURE_HEADER_PREFIX)

        # Validate hex format
        try:
            int(hmac_received, 16)
        except ValueError:
            logfire.warning("Request rejected: Invalid signature hex format.")
            return False

        # Compute the expected signature
        computed_hash = hmac.new(
            WhatsAppConfig.APP_SECRET,
            raw_body,
            hashlib.sha256
        ).hexdigest()

        # Compare the signatures using a constant-time comparison
        if not hmac.compare_digest(hmac_received, computed_hash):
            logfire.warning("Request rejected: Invalid signature.")
            return False

        logfire.info("Webhook signature verification successful.")
        return True


async def verify_whatsapp_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None)
) -> Tuple[bytes, dict]:
    """
    FastAPI dependency for verifying WhatsApp webhook signatures.

    Returns both the raw body and parsed JSON to avoid reading body twice.

    Args:
        request: The FastAPI request object
        x_hub_signature_256: The signature header

    Returns:
        Tuple of (raw_body, parsed_json)

    Raises:
        HTTPException: If signature verification fails
    """
    raw_body = await request.body()

    verifier = WhatsAppSignatureVerifier()
    if not verifier.verify_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    # Parse JSON after verification
    try:
        import json
        data = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logfire.error(f"Invalid JSON in webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    return raw_body, data
