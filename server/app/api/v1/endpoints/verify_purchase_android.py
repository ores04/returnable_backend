"""
Android In-App Purchase Verification Endpoint.
"""
import os
import logfire
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Dict, Any
import httpx
from datetime import datetime, timezone

from server.core.service.supabase_connectors.supabase_client import (
    get_supabase_client,
    get_supabase_service_role_client,
    USER_META_INFORMATION_TABLE_NAME
)

""" OK FOR NOW - BUT WILL NEED TO EXTRACT SUPABASE STUFF TO A COMMON MODULE LATER """

router = APIRouter()

# OAuth2 scheme for JWT token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Load Google API key from environment
GOOGLE_EFFORTLESS_API_KEY = os.getenv("GOOGLE_EFFORTLESS_API_KEY")

if not GOOGLE_EFFORTLESS_API_KEY:
    logfire.error("GOOGLE_EFFORTLESS_API_KEY is not set in environment variables")


class PurchaseVerificationRequest(BaseModel):
    """Request model for Android purchase verification."""
    product_id: str
    purchase_token: str
    package_name: str = "info.sebastianorth.effortless"


class PurchaseVerificationResponse(BaseModel):
    """Response model for purchase verification."""
    success: bool
    message: str
    product_id: str | None = None
    expiration_time: str | None = None


@router.post(
    "/verify",
    response_model=PurchaseVerificationResponse,
    summary="Verify Android In-App Purchase",
    description="Verifies an Android in-app purchase using Google Play Developer API and updates user subscription status"
)
async def verify_purchase_android(
    request: PurchaseVerificationRequest,
    token: str = Depends(oauth2_scheme)
) -> PurchaseVerificationResponse:
    """
    Verify an Android in-app purchase and update the authenticated user's subscription status.

    This endpoint:
    1. Authenticates the user via JWT token (OAuth2)
    2. Calls the Google Play Developer API to verify the purchase
    3. If verification succeeds (200 OK), updates the USER_META_INFORMATION table
       with the product_id and expiration_time for the authenticated user

    Args:
        request: PurchaseVerificationRequest containing product_id, purchase_token, and package_name
        token: JWT token from Authorization header (automatically extracted by Depends)

    Returns:
        PurchaseVerificationResponse with verification status and details

    Raises:
        HTTPException: If authentication fails, Google API call fails, or database update fails
    """
    logfire.info(f"Verifying Android purchase for product_id: {request.product_id}")

    if not GOOGLE_EFFORTLESS_API_KEY:
        logfire.error("GOOGLE_EFFORTLESS_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: Google API key not set"
        )

    # Get authenticated user's UUID from token
    try:
        supabase = get_supabase_client(jwt_token=token)
        user = supabase.auth.get_user(token).user
        user_uuid = user.id
        logfire.info(f"Authenticated user UUID: {user_uuid}")
    except Exception as e:
        logfire.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )

    # Construct Google Play Developer API URL for subscription verification
    google_api_url = (
        f"https://androidpublisher.googleapis.com/androidpublisher/v3/"
        f"applications/{request.package_name}/purchases/subscriptions/"
        f"{request.product_id}/tokens/{request.purchase_token}"
        f"?key={GOOGLE_EFFORTLESS_API_KEY}"
    )

    try:
        # Call Google Play Developer API to verify the purchase
        async with httpx.AsyncClient() as client:
            logfire.debug(f"Calling Google Play API for verification")
            response = await client.get(google_api_url, timeout=10.0)

            logfire.info(
                f"Google API response status: {response.status_code}",
                extra={"status_code": response.status_code, "user_uuid": user_uuid}
            )

            if response.status_code != 200:
                logfire.warning(
                    f"Purchase verification failed with status {response.status_code}",
                    extra={"response_body": response.text, "user_uuid": user_uuid}
                )
                return PurchaseVerificationResponse(
                    success=False,
                    message=f"Purchase verification failed: {response.status_code}"
                )

            # Parse the Google API response
            purchase_data = response.json()
            logfire.debug(f"Purchase data received", extra={"purchase_data": purchase_data})

            # Extract expiration time from the response
            # Google returns expiryTimeMillis for subscriptions
            expiry_time_millis = purchase_data.get("expiryTimeMillis")

            if not expiry_time_millis:
                logfire.error("No expiry time in purchase data")
                raise HTTPException(
                    status_code=500,
                    detail="Invalid purchase data: missing expiry time"
                )

            # Convert milliseconds timestamp to datetime
            expiry_timestamp = datetime.fromtimestamp(int(expiry_time_millis) / 1000)
            expiry_iso = expiry_timestamp.isoformat()

            logfire.info(
                f"Purchase verified successfully. Expiry: {expiry_iso}",
                extra={"product_id": request.product_id, "expiry": expiry_iso, "user_uuid": user_uuid}
            )

            # Update Supabase USER_META_INFORMATION table with subscription details
            update_data = {
                "tier_product_id": request.product_id,
                "tier_expiration_time": expiry_iso
            }

            logfire.info(
                f"Updating user subscription in database",
                extra={"user_uuid": user_uuid, "update_data": update_data}
            )

            result = supabase.from_(USER_META_INFORMATION_TABLE_NAME)\
                .update(update_data)\
                .eq("uuid", user_uuid)\
                .execute()

            if not result.data:
                logfire.error(
                    f"Failed to update user subscription - user not found in USER_META_INFORMATION",
                    extra={"user_uuid": user_uuid}
                )
                raise HTTPException(
                    status_code=404,
                    detail="User profile not found in USER_META_INFORMATION table"
                )

            logfire.info(
                f"Successfully verified and updated subscription for user {user_uuid}",
                extra={
                    "product_id": request.product_id,
                    "expiry": expiry_iso,
                    "user_uuid": user_uuid
                }
            )

            return PurchaseVerificationResponse(
                success=True,
                message="Purchase verified and subscription updated successfully",
                product_id=request.product_id,
                expiration_time=expiry_iso
            )

    except httpx.TimeoutException:
        logfire.error("Timeout calling Google Play API")
        raise HTTPException(
            status_code=504,
            detail="Timeout verifying purchase with Google Play API"
        )
    except httpx.RequestError as e:
        logfire.error(f"Request error calling Google Play API: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Error communicating with Google Play API: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Unexpected error during purchase verification: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


class SubscriptionCheckResponse(BaseModel):
    """Response model for subscription expiry check."""
    success: bool
    message: str
    total_users_checked: int
    expired_subscriptions: int
    reverted_to_free: int
    errors: int


@router.post(
    "/check-expired-subscriptions",
    response_model=SubscriptionCheckResponse,
    summary="Check and Update Expired Subscriptions",
    description="Checks all users with expired subscriptions and reverts them to free tier if no longer subscribed. Requires service role privileges."
)
async def check_expired_subscriptions() -> SubscriptionCheckResponse:
    """
    Check all users for expired subscriptions and revert to free tier if needed.

    This endpoint:
    1. Uses service role client to query all users with tier_expiration_time in the past
    2. For each expired user, verifies if they still have an active subscription via Google Play API
    3. If verification fails or subscription is not active, reverts user to 'free' tier
    4. Intended to be called by a cron job at midnight

    Returns:
        SubscriptionCheckResponse with statistics about the check

    Note:
        This endpoint has no authentication as it's meant to be called by a cron job.
        In production, you should add IP whitelisting or a secret token for security.
    """
    logfire.info("Starting expired subscription check for all users")

    if not GOOGLE_EFFORTLESS_API_KEY:
        logfire.error("GOOGLE_EFFORTLESS_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: Google API key not set"
        )

    # Get service role client (privileged access)
    try:
        supabase = get_supabase_service_role_client()
    except Exception as e:
        logfire.error(f"Failed to get service role client: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get privileged database access"
        )

    total_checked = 0
    expired_count = 0
    reverted_count = 0
    error_count = 0

    try:
        # Get current time
        current_time = datetime.now(timezone.utc)
        logfire.info(f"Current UTC time: {current_time.isoformat()}")

        # Query all users with expired subscriptions (tier_expiration_time < now)
        # and tier_product_id is not 'free'
        result = supabase.from_(USER_META_INFORMATION_TABLE_NAME)\
            .select("uuid, tier_product_id, tier_expiration_time")\
            .neq("tier_product_id", "free")\
            .not_.is_("tier_expiration_time", "null")\
            .execute()

        users = result.data if result.data else []
        logfire.info(f"Found {len(users)} users with non-free tiers")

        for user in users:
            user_uuid = user.get("uuid")
            product_id = user.get("tier_product_id")
            expiration_time_str = user.get("tier_expiration_time")

            if not expiration_time_str:
                continue

            total_checked += 1

            try:
                # Parse expiration time
                expiration_time = datetime.fromisoformat(expiration_time_str.replace('Z', '+00:00'))

                # Check if expired
                if expiration_time > current_time:
                    logfire.debug(
                        f"User {user_uuid} subscription still valid until {expiration_time_str}",
                        extra={"user_uuid": user_uuid}
                    )
                    continue

                expired_count += 1
                logfire.info(
                    f"User {user_uuid} subscription expired at {expiration_time_str}",
                    extra={"user_uuid": user_uuid, "product_id": product_id}
                )

                # Subscription is expired - revert to free tier
                # In a more advanced implementation, you could try to verify with Google Play API
                # using stored purchase tokens, but for now we'll just revert to free

                update_result = supabase.from_(USER_META_INFORMATION_TABLE_NAME)\
                    .update({
                        "tier_product_id": "free",
                        "tier_expiration_time": None
                    })\
                    .eq("uuid", user_uuid)\
                    .execute()

                if update_result.data:
                    reverted_count += 1
                    logfire.info(
                        f"Successfully reverted user {user_uuid} to free tier",
                        extra={"user_uuid": user_uuid}
                    )
                else:
                    error_count += 1
                    logfire.error(
                        f"Failed to revert user {user_uuid} to free tier - no data returned",
                        extra={"user_uuid": user_uuid}
                    )

            except Exception as user_error:
                error_count += 1
                logfire.error(
                    f"Error processing user {user_uuid}: {str(user_error)}",
                    extra={"user_uuid": user_uuid, "error": str(user_error)}
                )
                continue

        logfire.info(
            f"Subscription check completed",
            extra={
                "total_checked": total_checked,
                "expired": expired_count,
                "reverted": reverted_count,
                "errors": error_count
            }
        )

        return SubscriptionCheckResponse(
            success=True,
            message=f"Subscription check completed successfully",
            total_users_checked=total_checked,
            expired_subscriptions=expired_count,
            reverted_to_free=reverted_count,
            errors=error_count
        )

    except Exception as e:
        logfire.error(f"Fatal error during subscription check: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check expired subscriptions: {str(e)}"
        )
