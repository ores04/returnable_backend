"""Pydantic models for RevenueCat webhook events."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class RevenueCatSubscriberAttributes(BaseModel):
    """Subscriber attributes from RevenueCat."""
    # Add any custom attributes you've configured in RevenueCat
    # These are custom key-value pairs you can set
    pass


class RevenueCatProduct(BaseModel):
    """Product information from RevenueCat."""
    id: str = Field(..., description="Product identifier")
    name: Optional[str] = Field(None, description="Product name")
    type: Optional[str] = Field(None, description="Product type (e.g., subscription)")


class RevenueCatStore(BaseModel):
    """Store information."""
    store: str = Field(..., description="Store name (APP_STORE, PLAY_STORE, etc.)")


class RevenueCatSubscriber(BaseModel):
    """Subscriber information from RevenueCat."""
    app_user_id: str = Field(..., description="Your app's user ID (RevenueCat app_user_id)")
    original_app_user_id: str = Field(..., description="Original app user ID")
    aliases: Optional[list[str]] = Field(None, description="User aliases")
    entitlements: Optional[Dict[str, Any]] = Field(None, description="Active entitlements")
    first_seen: Optional[str] = Field(None, description="ISO timestamp of first seen")
    non_subscriptions: Optional[Dict[str, Any]] = Field(None, description="Non-subscription purchases")
    original_application_version: Optional[str] = Field(None, description="Original app version")
    original_purchase_date: Optional[str] = Field(None, description="ISO timestamp of original purchase")
    subscriptions: Optional[Dict[str, Any]] = Field(None, description="Subscription information")


class RevenueCatWebhookEvent(BaseModel):
    """RevenueCat webhook event payload."""
    api_version: str = Field(..., description="API version (e.g., '1.0')")
    event: Dict[str, Any] = Field(..., description="Event details")

    # Event fields
    @property
    def event_type(self) -> str:
        """Get the event type from the event dict."""
        return self.event.get("type", "")

    @property
    def app_user_id(self) -> str:
        """Get the app user ID from the event."""
        return self.event.get("app_user_id", "")

    @property
    def original_app_user_id(self) -> str:
        """Get the original app user ID."""
        return self.event.get("original_app_user_id", "")

    @property
    def product_id(self) -> Optional[str]:
        """Get the product ID from the event."""
        return self.event.get("product_id")

    @property
    def period_type(self) -> Optional[str]:
        """Get the period type (NORMAL, TRIAL, INTRO)."""
        return self.event.get("period_type")

    @property
    def purchased_at_ms(self) -> Optional[int]:
        """Get the purchase timestamp in milliseconds."""
        return self.event.get("purchased_at_ms")

    @property
    def expiration_at_ms(self) -> Optional[int]:
        """Get the expiration timestamp in milliseconds."""
        return self.event.get("expiration_at_ms")

    @property
    def store(self) -> Optional[str]:
        """Get the store (APP_STORE, PLAY_STORE, etc.)."""
        return self.event.get("store")

    @property
    def environment(self) -> Optional[str]:
        """Get the environment (PRODUCTION, SANDBOX)."""
        return self.event.get("environment")

    @property
    def is_trial_conversion(self) -> Optional[bool]:
        """Check if this is a trial conversion."""
        return self.event.get("is_trial_conversion")

    @property
    def currency(self) -> Optional[str]:
        """Get the currency code."""
        return self.event.get("currency")

    @property
    def price(self) -> Optional[float]:
        """Get the price."""
        return self.event.get("price")

    @property
    def price_in_purchased_currency(self) -> Optional[float]:
        """Get the price in purchased currency."""
        return self.event.get("price_in_purchased_currency")

    @property
    def subscriber_attributes(self) -> Optional[Dict[str, Any]]:
        """Get subscriber attributes."""
        return self.event.get("subscriber_attributes")

    @property
    def transaction_id(self) -> Optional[str]:
        """Get the original transaction ID."""
        return self.event.get("original_transaction_id") or self.event.get("transaction_id")

    @property
    def cancellation_reason(self) -> Optional[str]:
        """Get the cancellation reason if applicable."""
        return self.event.get("cancellation_reason")


class WebhookProcessingResult(BaseModel):
    """Result of webhook processing."""
    success: bool
    event_type: str
    user_id: str
    message: str
    updated_fields: Optional[Dict[str, Any]] = None
