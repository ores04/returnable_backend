"""WhatsApp API configuration settings."""
import os
import logfire
from typing import Optional


class WhatsAppConfig:
    """Configuration for WhatsApp API integration."""

    # Webhook verification
    VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "not_set")

    # API access
    ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "not_set")

    # Security
    APP_SECRET: bytes = os.getenv("WHATSAPP_APP_SECRET", "not_set").encode("utf8")

    # Constants
    WEBHOOK_OBJECT_TYPE: str = "whatsapp_business_account"
    SIGNATURE_HEADER_PREFIX: str = "sha256="

    @classmethod
    def validate(cls) -> None:
        """Validate that required configuration is set."""
        if cls.VERIFY_TOKEN == "not_set":
            logfire.warning(
                "Warning: WhatsApp verify token is not set. "
                "Please set the environment variable WHATSAPP_VERIFY_TOKEN."
            )

        if cls.ACCESS_TOKEN == "not_set":
            logfire.warning(
                "Warning: WhatsApp access token is not set. "
                "Please set the environment variable WHATSAPP_ACCESS_TOKEN."
            )

        if cls.APP_SECRET == b"not_set":
            logfire.warning(
                "Warning: WhatsApp app secret is not set. "
                "Please set the environment variable WHATSAPP_APP_SECRET."
            )


# Validate configuration on module import
WhatsAppConfig.validate()
