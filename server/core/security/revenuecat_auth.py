"""RevenueCat webhook authorization verification."""
import logfire
from fastapi import Header, HTTPException, Request
from typing import Optional, Tuple

from server.core.config.revenuecat_config import RevenueCatConfig


class RevenueCatAuthVerifier:
    """Handles RevenueCat webhook authorization verification."""

    @staticmethod
    def verify_authorization(authorization_header: Optional[str]) -> bool:
        """
        Verify the Bearer token in the Authorization header.

        RevenueCat sends webhooks with an Authorization header containing
        a Bearer token that you configure in the RevenueCat dashboard.

        Args:
            authorization_header: The Authorization header value

        Returns:
            True if authorization is valid, False otherwise
        """
        if authorization_header is None:
            logfire.warning("RevenueCat webhook rejected: Missing Authorization header.")
            return False

        # The header should be in the format "Bearer <token>"
        if not authorization_header.startswith("Bearer "):
            logfire.warning("RevenueCat webhook rejected: Invalid authorization format.")
            return False

        token = authorization_header.removeprefix("Bearer ")

        # Compare the token with configured webhook auth token
        if not token or token != RevenueCatConfig.WEBHOOK_AUTH_TOKEN:
            logfire.warning("RevenueCat webhook rejected: Invalid authorization token.")
            return False

        logfire.info("RevenueCat webhook authorization successful.")
        return True


async def verify_revenuecat_webhook(
    request: Request,
    authorization: Optional[str] = Header(None)
) -> dict:
    """
    FastAPI dependency for verifying RevenueCat webhook authorization.

    Args:
        request: The FastAPI request object
        authorization: The Authorization header

    Returns:
        Parsed JSON payload

    Raises:
        HTTPException: If authorization verification fails or JSON is invalid
    """
    # Verify authorization
    verifier = RevenueCatAuthVerifier()
    if not verifier.verify_authorization(authorization):
        raise HTTPException(status_code=403, detail="Invalid webhook authorization")

    # Parse JSON payload
    try:
        data = await request.json()
    except Exception as e:
        logfire.error(f"Invalid JSON in RevenueCat webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    return data
