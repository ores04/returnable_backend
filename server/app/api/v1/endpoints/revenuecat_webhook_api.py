"""API endpoints for RevenueCat webhook integration."""
import logfire
from fastapi import APIRouter, BackgroundTasks, Depends
from typing import Dict, Any

from server.core.security.revenuecat_auth import verify_revenuecat_webhook
from server.core.service.revenuecat_service.webhook_handler import RevenueCatWebhookHandler

router = APIRouter()

# Initialize webhook handler
webhook_handler = RevenueCatWebhookHandler()


@router.post("/revenuecat/webhook")
async def handle_revenuecat_webhook(
    background_tasks: BackgroundTasks,
    verified_data: Dict[str, Any] = Depends(verify_revenuecat_webhook)
):
    """
    Handle incoming RevenueCat webhook events.

    This endpoint receives subscription events from RevenueCat including:
    - INITIAL_PURCHASE: First time purchase
    - RENEWAL: Subscription renewal
    - CANCELLATION: Subscription cancelled
    - UNCANCELLATION: Cancelled subscription reactivated
    - NON_RENEWING_PURCHASE: One-time purchase
    - SUBSCRIPTION_PAUSED: Subscription paused
    - EXPIRATION: Subscription expired
    - BILLING_ISSUE: Payment failed
    - PRODUCT_CHANGE: Upgrade/downgrade
    - TRANSFER: Subscription transferred

    The authorization is verified via the dependency injection.
    Processing is done in the background to respond quickly.

    Args:
        background_tasks: FastAPI background tasks handler
        verified_data: Verified and parsed webhook payload

    Returns:
        Acknowledgment response for RevenueCat

    Raises:
        HTTPException: If authorization fails (handled by dependency)
    """
    # Log minimal info (avoid logging sensitive data in production)
    event_type = verified_data.get("event", {}).get("type", "UNKNOWN")
    app_user_id = verified_data.get("event", {}).get("app_user_id", "UNKNOWN")

    logfire.info(
        f"Received verified RevenueCat webhook",
        extra={
            "event_type": event_type,
            "app_user_id": app_user_id
        }
    )

    # Process webhook in background to respond quickly
    # RevenueCat expects a 200 response within a few seconds
    background_tasks.add_task(webhook_handler.process_webhook, verified_data)

    return {"received": True}
