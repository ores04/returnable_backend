"""WhatsApp API configuration settings."""
import os
import logfire
from typing import Optional


class WhatsAppConfig:
    """Configuration for WhatsApp API integration."""

    # Webhook verification
    VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    # API access
    ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")

    # Security
    APP_SECRET: bytes = os.getenv("WHATSAPP_APP_SECRET", "").encode("utf8")

    # Constants
    WEBHOOK_OBJECT_TYPE: str = "whatsapp_business_account"
    SIGNATURE_HEADER_PREFIX: str = "sha256="

    @classmethod
    def validate(cls, strict: bool = False) -> None:
        """
        Validate that required configuration is set.

        Args:
            strict: If True, raise exception on missing config. If False, only log warnings.
        """
        errors = []

        if not cls.VERIFY_TOKEN:
            msg = (
                "WhatsApp verify token is not set. "
                "Please set the environment variable WHATSAPP_VERIFY_TOKEN."
            )
            if strict:
                errors.append(msg)
            else:
                logfire.warning(f"Warning: {msg}")

        if not cls.ACCESS_TOKEN:
            msg = (
                "WhatsApp access token is not set. "
                "Please set the environment variable WHATSAPP_ACCESS_TOKEN."
            )
            if strict:
                errors.append(msg)
            else:
                logfire.warning(f"Warning: {msg}")

        if not cls.APP_SECRET:
            msg = (
                "WhatsApp app secret is not set. "
                "Please set the environment variable WHATSAPP_APP_SECRET."
            )
            if strict:
                errors.append(msg)
            else:
                logfire.warning(f"Warning: {msg}")

        if strict and errors:
            raise ValueError(f"Missing required WhatsApp configuration: {', '.join(errors)}")


# Validate configuration on module import (non-strict mode for development)
WhatsAppConfig.validate(strict=False)
