"""
Common models for purchase verification across platforms.
"""
from pydantic import BaseModel
from typing import Optional


class PurchaseVerificationRequest(BaseModel):
    """Base request model for purchase verification."""
    product_id: str
    purchase_token: str  # Android uses this; iOS uses transaction_id


class AndroidPurchaseVerificationRequest(PurchaseVerificationRequest):
    """Request model for Android purchase verification."""
    package_name: str = "info.sebastianorth.effortless"


class IOSPurchaseVerificationRequest(PurchaseVerificationRequest):
    """Request model for iOS purchase verification."""
    bundle_id: str = "info.sebastianorth.effortless"
    # For iOS, purchase_token is actually the transactionId or originalTransactionId


class PurchaseVerificationResponse(BaseModel):
    """Response model for purchase verification."""
    success: bool
    message: str
    product_id: Optional[str] = None
    expiration_time: Optional[str] = None


class SubscriptionCheckResponse(BaseModel):
    """Response model for subscription expiry check."""
    success: bool
    message: str
    total_users_checked: int
    expired_subscriptions: int
    reverted_to_free: int
    errors: int
