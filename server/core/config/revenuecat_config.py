"""RevenueCat webhook configuration settings."""
import os
import logfire
from typing import Optional


class RevenueCatConfig:
    """Configuration for RevenueCat webhook integration."""

    # Webhook authorization
    # RevenueCat sends a Bearer token in the Authorization header
    WEBHOOK_AUTH_TOKEN: str = os.getenv("REVENUECAT_WEBHOOK_AUTH_TOKEN", "")

    # Alternative: Use API key for additional verification
    API_KEY: str = os.getenv("REVENUECAT_API_KEY", "")

    # Webhook event types to process
    SUPPORTED_EVENT_TYPES = {
        "INITIAL_PURCHASE",
        "RENEWAL",
        "CANCELLATION",
        "UNCANCELLATION",
        "NON_RENEWING_PURCHASE",
        "SUBSCRIPTION_PAUSED",
        "EXPIRATION",
        "BILLING_ISSUE",
        "PRODUCT_CHANGE",
        "TRANSFER"
    }

    @classmethod
    def validate(cls, strict: bool = False) -> None:
        """
        Validate that required configuration is set.

        Args:
            strict: If True, raise exception on missing config. If False, only log warnings.
        """
        errors = []

        if not cls.WEBHOOK_AUTH_TOKEN:
            msg = (
                "RevenueCat webhook auth token is not set. "
                "Please set the environment variable REVENUECAT_WEBHOOK_AUTH_TOKEN."
            )
            if strict:
                errors.append(msg)
            else:
                logfire.warning(f"Warning: {msg}")

        if strict and errors:
            raise ValueError(f"Missing required RevenueCat configuration: {', '.join(errors)}")


# Validate configuration on module import (non-strict mode for development)
RevenueCatConfig.validate(strict=False)
