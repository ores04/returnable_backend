"""RevenueCat webhook event handler."""
import logfire
from datetime import datetime, timezone
from typing import Dict, Any

from server.core.models.revenuecat_models import RevenueCatWebhookEvent, WebhookProcessingResult
from server.core.service.supabase_connectors.supabase_client import (
    get_supabase_service_role_client,
    USER_META_INFORMATION_TABLE_NAME
)
from server.core.config.revenuecat_config import RevenueCatConfig


class RevenueCatWebhookHandler:
    """Handles processing of RevenueCat webhook events."""

    def __init__(self):
        """Initialize the webhook handler."""
        self.supabase = get_supabase_service_role_client()

    def process_webhook(self, payload: Dict[str, Any]) -> WebhookProcessingResult:
        """
        Process incoming RevenueCat webhook event.

        Args:
            payload: The webhook event payload

        Returns:
            WebhookProcessingResult with processing details
        """
        try:
            # Parse the webhook event
            event = RevenueCatWebhookEvent(**payload)
            event_type = event.event_type
            app_user_id = event.app_user_id

            logfire.info(
                f"Processing RevenueCat webhook event",
                extra={
                    "event_type": event_type,
                    "app_user_id": app_user_id,
                    "product_id": event.product_id
                }
            )

            # Check if event type is supported
            if event_type not in RevenueCatConfig.SUPPORTED_EVENT_TYPES:
                logfire.warning(f"Unsupported event type: {event_type}")
                return WebhookProcessingResult(
                    success=False,
                    event_type=event_type,
                    user_id=app_user_id,
                    message=f"Unsupported event type: {event_type}"
                )

            # Route to appropriate handler based on event type
            if event_type in ["INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION", "NON_RENEWING_PURCHASE"]:
                return self._handle_subscription_activated(event)
            elif event_type in ["CANCELLATION", "EXPIRATION"]:
                return self._handle_subscription_deactivated(event)
            elif event_type == "PRODUCT_CHANGE":
                return self._handle_product_change(event)
            elif event_type == "SUBSCRIPTION_PAUSED":
                return self._handle_subscription_paused(event)
            elif event_type == "BILLING_ISSUE":
                return self._handle_billing_issue(event)
            elif event_type == "TRANSFER":
                return self._handle_transfer(event)
            else:
                logfire.info(f"Event type {event_type} acknowledged but not processed")
                return WebhookProcessingResult(
                    success=True,
                    event_type=event_type,
                    user_id=app_user_id,
                    message=f"Event {event_type} acknowledged but not processed"
                )

        except Exception as e:
            logfire.error(f"Error processing RevenueCat webhook: {str(e)}", exc_info=True)
            return WebhookProcessingResult(
                success=False,
                event_type="UNKNOWN",
                user_id="UNKNOWN",
                message=f"Error processing webhook: {str(e)}"
            )

    def _handle_subscription_activated(self, event: RevenueCatWebhookEvent) -> WebhookProcessingResult:
        """
        Handle subscription activation events (purchase, renewal, uncancellation).

        Args:
            event: The webhook event

        Returns:
            WebhookProcessingResult
        """
        app_user_id = event.app_user_id
        product_id = event.product_id
        expiration_at_ms = event.expiration_at_ms
        transaction_id = event.transaction_id

        # Convert expiration time from milliseconds to ISO format
        if expiration_at_ms:
            expiration_time = datetime.fromtimestamp(
                expiration_at_ms / 1000, tz=timezone.utc
            ).isoformat()
        else:
            # For non-renewing purchases, set a far future date or handle differently
            logfire.warning(f"No expiration time for event {event.event_type}, setting to None")
            expiration_time = None

        update_data = {
            "tier_product_id": product_id or "unknown",
            "tier_expiration_time": expiration_time,
            "purchase_token": transaction_id
        }

        try:
            result = self.supabase.from_(USER_META_INFORMATION_TABLE_NAME)\
                .update(update_data)\
                .eq("uuid", app_user_id)\
                .execute()

            if not result.data:
                logfire.error(
                    f"User not found in USER_META_INFORMATION table",
                    extra={"app_user_id": app_user_id}
                )
                return WebhookProcessingResult(
                    success=False,
                    event_type=event.event_type,
                    user_id=app_user_id,
                    message=f"User {app_user_id} not found in database"
                )

            logfire.info(
                f"Successfully updated subscription for user {app_user_id}",
                extra={
                    "event_type": event.event_type,
                    "product_id": product_id,
                    "expiration_time": expiration_time
                }
            )

            return WebhookProcessingResult(
                success=True,
                event_type=event.event_type,
                user_id=app_user_id,
                message=f"Subscription activated for user {app_user_id}",
                updated_fields=update_data
            )

        except Exception as e:
            logfire.error(f"Database update failed: {str(e)}", exc_info=True)
            return WebhookProcessingResult(
                success=False,
                event_type=event.event_type,
                user_id=app_user_id,
                message=f"Database update failed: {str(e)}"
            )

    def _handle_subscription_deactivated(self, event: RevenueCatWebhookEvent) -> WebhookProcessingResult:
        """
        Handle subscription deactivation events (cancellation, expiration).

        Args:
            event: The webhook event

        Returns:
            WebhookProcessingResult
        """
        app_user_id = event.app_user_id

        # Revert user to free tier
        update_data = {
            "tier_product_id": "free",
            "tier_expiration_time": None,
            "purchase_token": None
        }

        try:
            result = self.supabase.from_(USER_META_INFORMATION_TABLE_NAME)\
                .update(update_data)\
                .eq("uuid", app_user_id)\
                .execute()

            if not result.data:
                logfire.error(
                    f"User not found in USER_META_INFORMATION table",
                    extra={"app_user_id": app_user_id}
                )
                return WebhookProcessingResult(
                    success=False,
                    event_type=event.event_type,
                    user_id=app_user_id,
                    message=f"User {app_user_id} not found in database"
                )

            logfire.info(
                f"Successfully reverted user {app_user_id} to free tier",
                extra={
                    "event_type": event.event_type,
                    "cancellation_reason": event.cancellation_reason
                }
            )

            return WebhookProcessingResult(
                success=True,
                event_type=event.event_type,
                user_id=app_user_id,
                message=f"Subscription deactivated for user {app_user_id}",
                updated_fields=update_data
            )

        except Exception as e:
            logfire.error(f"Database update failed: {str(e)}", exc_info=True)
            return WebhookProcessingResult(
                success=False,
                event_type=event.event_type,
                user_id=app_user_id,
                message=f"Database update failed: {str(e)}"
            )

    def _handle_product_change(self, event: RevenueCatWebhookEvent) -> WebhookProcessingResult:
        """
        Handle product change events (upgrade/downgrade).

        Args:
            event: The webhook event

        Returns:
            WebhookProcessingResult
        """
        # Product changes are similar to activations - update with new product
        return self._handle_subscription_activated(event)

    def _handle_subscription_paused(self, event: RevenueCatWebhookEvent) -> WebhookProcessingResult:
        """
        Handle subscription paused events.

        Args:
            event: The webhook event

        Returns:
            WebhookProcessingResult
        """
        # For paused subscriptions, you might want to keep them as premium
        # until expiration or immediately revert to free - adjust as needed
        app_user_id = event.app_user_id

        logfire.info(
            f"Subscription paused for user {app_user_id}",
            extra={"event_type": event.event_type}
        )

        # Option 1: Keep current subscription until it expires
        # (no update needed, let expiration handle it)
        return WebhookProcessingResult(
            success=True,
            event_type=event.event_type,
            user_id=app_user_id,
            message=f"Subscription paused for user {app_user_id}, will expire naturally"
        )

        # Option 2: Immediately revert to free
        # return self._handle_subscription_deactivated(event)

    def _handle_billing_issue(self, event: RevenueCatWebhookEvent) -> WebhookProcessingResult:
        """
        Handle billing issue events.

        Args:
            event: The webhook event

        Returns:
            WebhookProcessingResult
        """
        app_user_id = event.app_user_id

        logfire.warning(
            f"Billing issue for user {app_user_id}",
            extra={"event_type": event.event_type}
        )

        # Keep subscription active for grace period
        # You might want to add a flag to track billing issues
        return WebhookProcessingResult(
            success=True,
            event_type=event.event_type,
            user_id=app_user_id,
            message=f"Billing issue noted for user {app_user_id}"
        )

    def _handle_transfer(self, event: RevenueCatWebhookEvent) -> WebhookProcessingResult:
        """
        Handle transfer events (subscription transferred between users).

        Args:
            event: The webhook event

        Returns:
            WebhookProcessingResult
        """
        app_user_id = event.app_user_id

        logfire.info(
            f"Transfer event for user {app_user_id}",
            extra={"event_type": event.event_type}
        )

        # Handle transfer - might need to update both old and new user
        # For now, just update the current user's subscription
        return self._handle_subscription_activated(event)
