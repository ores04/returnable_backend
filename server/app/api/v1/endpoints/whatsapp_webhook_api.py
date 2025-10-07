"""API endpoints for WhatsApp webhook integration."""
import logfire
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends

from server.core.config.whatsapp_config import WhatsAppConfig
from server.core.security.whatsapp_auth import verify_whatsapp_webhook
from server.core.service.whatsapp_service.webhook_handler import WhatsAppWebhookHandler

router = APIRouter()

# Initialize webhook handler
webhook_handler = WhatsAppWebhookHandler()


@router.get("/whatsapp/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Verify WhatsApp webhook subscription.

    This endpoint is called by WhatsApp to verify the webhook URL.

    Args:
        hub_mode: Should be "subscribe"
        hub_challenge: Challenge string to return
        hub_verify_token: Verification token to validate

    Returns:
        The challenge as an integer if verification succeeds

    Raises:
        HTTPException: If verification fails
    """
    if hub_mode == "subscribe" and hub_verify_token == WhatsAppConfig.VERIFY_TOKEN:
        # Validate challenge is numeric and within reasonable bounds
        try:
            challenge_int = int(hub_challenge)
            if challenge_int < 0 or challenge_int > 2**31 - 1:
                logfire.warning("Challenge value out of bounds")
                raise HTTPException(status_code=400, detail="Invalid challenge value")
            logfire.info("WhatsApp webhook verification successful")
            return challenge_int
        except (ValueError, TypeError):
            logfire.warning("Invalid challenge format")
            raise HTTPException(status_code=400, detail="Invalid challenge format")

    logfire.warning(f"WhatsApp webhook verification failed - mode: {hub_mode}")
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/whatsapp/webhook")
async def handle_webhook(
    background_tasks: BackgroundTasks,
    verified_data: tuple = Depends(verify_whatsapp_webhook)
):
    """
    Handle incoming WhatsApp webhook events.

    This endpoint receives messages and other events from WhatsApp.
    The signature is verified via the dependency injection.
    Processing is done in the background to respond quickly.

    Args:
        background_tasks: FastAPI background tasks handler
        verified_data: Tuple of (raw_body, parsed_json) from verification dependency

    Returns:
        Acknowledgment response for WhatsApp
    """
    _, data = verified_data  # Unpack verified data

    # Log minimal info (avoid logging sensitive data in production)
    logfire.info("Received verified WhatsApp webhook")

    # Process webhook in background to respond quickly
    background_tasks.add_task(webhook_handler.process_webhook, data)

    return {"status": "EVENT_RECEIVED"}
