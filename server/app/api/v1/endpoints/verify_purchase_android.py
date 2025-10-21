"""
Android In-App Purchase Verification Endpoint.
"""
import os
import logfire
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any
import httpx
from datetime import datetime, timezone
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from server.core.service.purchase_verification.models import (
    AndroidPurchaseVerificationRequest,
    PurchaseVerificationResponse,
    SubscriptionCheckResponse
)
from server.core.service.purchase_verification.verification_service import VerificationService

router = APIRouter()

# OAuth2 scheme for JWT token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Path to the service account key file
SERVICE_ACCOUNT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "effortless_service_account_key.json"
)
print(SERVICE_ACCOUNT_FILE)

# Google Play Developer API scope
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

# Initialize Google service account credentials
try:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    logfire.info(f"Successfully loaded Google service account credentials from {SERVICE_ACCOUNT_FILE}")
except Exception as e:
    logfire.error(f"Failed to load service account credentials: {str(e)}")
    credentials = None


def get_google_access_token() -> str:
    """
    Get a valid access token from the service account credentials.
    Refreshes the token if necessary.

    Returns:
        str: Valid access token

    Raises:
        HTTPException: If credentials are not available or token refresh fails
    """
    if credentials is None:
        raise HTTPException(
            status_code=500,
            detail="Google service account credentials not configured"
        )

    # Refresh the token if it's expired or not yet fetched
    if not credentials.valid:
        try:
            credentials.refresh(Request())
            logfire.debug("Refreshed Google access token")
        except Exception as e:
            logfire.error(f"Failed to refresh access token: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to refresh Google access token: {str(e)}"
            )

    return credentials.token


@router.post(
    "/verify",
    response_model=PurchaseVerificationResponse,
    summary="Verify Android In-App Purchase",
    description="Verifies an Android in-app purchase using Google Play Developer API and updates user subscription status"
)
async def verify_purchase_android(
    request: AndroidPurchaseVerificationRequest,
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
        request: AndroidPurchaseVerificationRequest containing product_id, purchase_token, and package_name
        token: JWT token from Authorization header (automatically extracted by Depends)

    Returns:
        PurchaseVerificationResponse with verification status and details

    Raises:
        HTTPException: If authentication fails, Google API call fails, or database update fails
    """
    logfire.info(f"Verifying Android purchase for product_id: {request.product_id}")

    # Get Google access token
    access_token = get_google_access_token()

    # Get authenticated user's UUID from token
    supabase, user_uuid = VerificationService.get_authenticated_user_uuid(token)

    # Construct Google Play Developer API URL for subscription verification
    google_api_url = (
        f"https://androidpublisher.googleapis.com/androidpublisher/v3/"
        f"applications/{request.package_name}/purchases/subscriptions/"
        f"{request.product_id}/tokens/{request.purchase_token}"
    )

    # Prepare authorization headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        # Call Google Play Developer API to verify the purchase
        async with httpx.AsyncClient() as client:
            logfire.debug(f"Calling Google Play API for verification")
            response = await client.get(google_api_url, headers=headers, timeout=10.0)

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
            VerificationService.update_user_subscription(
                supabase_client=supabase,
                user_uuid=user_uuid,
                product_id=request.product_id,
                expiration_time=expiry_iso,
                purchase_token=request.purchase_token
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


@router.post("/check-expired-subscription", response_model=SubscriptionCheckResponse, summary="Check and Update Expired Subscription for Authenticated User", description="Checks if the authenticated user's subscription has expired and reverts to free tier if no longer subscribed.")
async def check_expired_subscription(
    token: str = Depends(oauth2_scheme)
) -> SubscriptionCheckResponse:
    """
    Check if the authenticated user's subscription has expired and revert to free tier if needed.

    This endpoint:
    1. Authenticates the user via JWT token (OAuth2)
    2. Queries the USER_META_INFORMATION table for the user's subscription details
    3. Verifies the subscription status via Google Play Developer API v2
    4. If subscription is not active (expired, canceled, etc.), reverts user to 'free' tier
    5. If subscription is still active, updates the expiration time in the database

    Args:
        token: JWT token from Authorization header (automatically extracted by Depends)
    Returns:
        SubscriptionCheckResponse with the result of the check

    """
    logfire.info("Starting expired subscription check for authenticated user (Android)")

    # Get Google access token
    access_token = get_google_access_token()

    # Get authenticated user's UUID from token
    supabase, user_uuid = VerificationService.get_authenticated_user_uuid(token)

    try:
        # Get user's subscription data
        user_data = VerificationService.get_user_subscription_data(supabase, user_uuid)

        product_id = user_data.get("tier_product_id")
        expiration_time_str = user_data.get("tier_expiration_time")
        purchase_token = user_data.get("purchase_token")

        if not expiration_time_str or product_id == "free":
            logfire.info(f"User {user_uuid} has no active subscription to check")
            return SubscriptionCheckResponse(
                success=True,
                message="No active subscription to check",
                total_users_checked=1,
                expired_subscriptions=0,
                reverted_to_free=0,
                errors=0
            )

        # Check if subscription appears expired locally
        if not VerificationService.is_subscription_expired_locally(expiration_time_str):
            logfire.info(
                f"User {user_uuid} subscription still valid until {expiration_time_str}",
                extra={"user_uuid": user_uuid}
            )
            return SubscriptionCheckResponse(
                success=True,
                message="Subscription still active",
                total_users_checked=1,
                expired_subscriptions=0,
                reverted_to_free=0,
                errors=0
            )

        # Subscription appears expired, verify with Google Play API
        logfire.info(
            f"User {user_uuid} subscription expired at {expiration_time_str}, verifying with Google Play API",
            extra={"user_uuid": user_uuid, "product_id": product_id}
        )

        if not purchase_token:
            logfire.warning(
                f"User {user_uuid} has no purchase token, reverting to free",
                extra={"user_uuid": user_uuid}
            )
            # No purchase token, revert to free
            VerificationService.revert_user_to_free(supabase, user_uuid)
            return SubscriptionCheckResponse(
                success=True,
                message="No purchase token, reverted to free tier",
                total_users_checked=1,
                expired_subscriptions=1,
                reverted_to_free=1,
                errors=0
            )

        # Call Google Play Developer API v2 to check subscription status
        package_name = "info.sebastianorth.effortless"
        google_api_url = (
            f"https://androidpublisher.googleapis.com/androidpublisher/v3/"
            f"applications/{package_name}/purchases/subscriptionsv2/tokens/{purchase_token}"
        )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient() as client:
            # call the actual API
            response = await client.get(google_api_url, headers=headers, timeout=10.0)

            if response.status_code == 200:
                # Parse subscription data
                subscription_data = response.json()
                subscription_state = subscription_data.get("subscriptionState")
                logfire.info(
                    f"Google API subscription state for user {user_uuid}: {subscription_state}",
                    extra={"user_uuid": user_uuid, "state": subscription_state}
                )
                print(subscription_data)
                print(subscription_state)
                # Check if subscription is active
                # Active states: SUBSCRIPTION_STATE_ACTIVE, SUBSCRIPTION_STATE_IN_GRACE_PERIOD,
                is_active = subscription_state in [
                    "SUBSCRIPTION_STATE_ACTIVE",
                    "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"
                ]
                if is_active:
                    line_items = subscription_data.get("lineItems", [])
                    if not line_items:
                        logfire.error(
                            f"No line items in subscription data for user {user_uuid}",
                            extra={"user_uuid": user_uuid}
                        )
                        raise HTTPException(
                            status_code=500,
                            detail="Invalid subscription data: missing line items"
                        )
                    # todo for one line it is ok to just take the first - but what if there are multiple lines? ie multipl e subscriptions?
                    expiry_time = line_items[0].get("expiryTime")
                    # write to db
                    if expiry_time:# Convert milliseconds timestamp to datetime
                        expiry_timestamp = datetime.fromisoformat(expiry_time)
                        expiry_iso = expiry_timestamp.isoformat()

                        logfire.info(
                            f"Subscription still active for user {user_uuid}, updating expiry to {expiry_iso}",
                            extra={"user_uuid": user_uuid, "new_expiry": expiry_iso})
                        VerificationService.update_subscription_expiration(
                            supabase, user_uuid, expiry_iso
                        )
                        return SubscriptionCheckResponse(
                            success=True,
                            message="Subscription still active, expiry updated",
                            total_users_checked=1,
                            expired_subscriptions=1,
                            reverted_to_free=0,
                            errors=0)

            # Subscription is not active (expired, canceled, paused, etc.), revert to free
            logfire.info(
                f"Subscription not active for user {user_uuid} (state: {subscription_state}), reverting to free",
                extra={"user_uuid": user_uuid, "state": subscription_state})

            VerificationService.revert_user_to_free(supabase, user_uuid)
        return SubscriptionCheckResponse(
            success=True,
            message="Subscription expired, reverted to free tier",
            total_users_checked=1,
            expired_subscriptions=1,
            reverted_to_free=1,
            errors=0
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
    1. Uses service role client to query all users with non-free tier_product_id
    2. For each user, verifies their subscription status via Google Play Developer API v2
    3. If subscription is not active (expired, canceled, etc.), reverts user to 'free' tier
    4. If subscription is still active, updates the expiration time in the database
    5. Intended to be called by a cron job at midnight

    Returns:
        SubscriptionCheckResponse with statistics about the check

    Note:
        This endpoint has no authentication as it's meant to be called by a cron job.
        In production, you should add IP whitelisting or a secret token for security.
    """
    logfire.info("Starting expired subscription check for all Android users")

    # Get Google access token
    access_token = get_google_access_token()

    # Get all non-free users
    users = VerificationService.get_all_non_free_users()

    # Get service role client for updates
    from server.core.service.supabase_connectors.supabase_client import get_supabase_service_role_client
    supabase = get_supabase_service_role_client()

    total_checked = 0
    expired_count = 0
    reverted_count = 0
    error_count = 0
    active_renewed_count = 0

    try:
        current_time = datetime.now(timezone.utc)
        logfire.info(f"Current UTC time: {current_time.isoformat()}")

        for user in users:
            user_uuid = user.get("uuid")
            product_id = user.get("tier_product_id")
            expiration_time_str = user.get("tier_expiration_time")
            purchase_token = user.get("purchase_token")

            if not expiration_time_str:
                continue

            total_checked += 1

            try:
                # Check if subscription appears expired locally
                if not VerificationService.is_subscription_expired_locally(expiration_time_str):
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

                # Verify subscription status with Google Play API using purchase token
                if not purchase_token:
                    logfire.warning(
                        f"User {user_uuid} has no purchase token, reverting to free",
                        extra={"user_uuid": user_uuid}
                    )
                    # No purchase token, revert to free
                    if VerificationService.revert_user_to_free(supabase, user_uuid):
                        reverted_count += 1
                    else:
                        error_count += 1
                    continue

                # Call Google Play Developer API v2 to check subscription status
                package_name = "info.sebastianorth.effortless"
                google_api_url = (
                    f"https://androidpublisher.googleapis.com/androidpublisher/v3/"
                    f"applications/{package_name}/purchases/subscriptionsv2/tokens/{purchase_token}"
                )

                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }

                async with httpx.AsyncClient() as client:
                    logfire.debug(
                        f"Verifying subscription for user {user_uuid} with Google Play API v2",
                        extra={"user_uuid": user_uuid, "purchase_token": purchase_token[:30]}
                    )
                    response = await client.get(google_api_url, headers=headers, timeout=10.0)

                    if response.status_code != 200:
                        logfire.warning(
                            f"Google API returned {response.status_code} for user {user_uuid}, reverting to free",
                            extra={"user_uuid": user_uuid, "status_code": response.status_code, "response": response.text}
                        )
                        # API call failed or subscription not found, revert to free
                        if VerificationService.revert_user_to_free(supabase, user_uuid):
                            reverted_count += 1
                        else:
                            error_count += 1
                        continue

                    # Parse subscription data
                    subscription_data = response.json()
                    subscription_state = subscription_data.get("subscriptionState")

                    logfire.info(
                        f"Google API subscription state for user {user_uuid}: {subscription_state}",
                        extra={"user_uuid": user_uuid, "state": subscription_state}
                    )

                    # Check if subscription is active
                    # Active states: SUBSCRIPTION_STATE_ACTIVE, SUBSCRIPTION_STATE_IN_GRACE_PERIOD
                    is_active = subscription_state in [
                        "SUBSCRIPTION_STATE_ACTIVE",
                        "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"
                    ]

                    if is_active:
                        # Subscription is still active, update expiration time
                        line_items = subscription_data.get("lineItems", [])
                        if line_items:
                            expiry_time = line_items[0].get("expiryTime")
                            if expiry_time:
                                # Parse RFC 3339 timestamp
                                new_expiry = datetime.fromisoformat(expiry_time.replace('Z', '+00:00'))
                                new_expiry_iso = new_expiry.isoformat()

                                logfire.info(
                                    f"Subscription still active for user {user_uuid}, updating expiry to {new_expiry_iso}",
                                    extra={"user_uuid": user_uuid, "new_expiry": new_expiry_iso}
                                )

                                if VerificationService.update_subscription_expiration(
                                    supabase, user_uuid, new_expiry_iso
                                ):
                                    active_renewed_count += 1
                                else:
                                    error_count += 1
                            else:
                                logfire.error(
                                    f"No expiry time in active subscription for user {user_uuid}",
                                    extra={"user_uuid": user_uuid}
                                )
                                error_count += 1
                        else:
                            logfire.error(
                                f"No line items in subscription data for user {user_uuid}",
                                extra={"user_uuid": user_uuid}
                            )
                            error_count += 1
                    else:
                        # Subscription is not active (expired, canceled, paused, etc.), revert to free
                        logfire.info(
                            f"Subscription not active for user {user_uuid} (state: {subscription_state}), reverting to free",
                            extra={"user_uuid": user_uuid, "state": subscription_state}
                        )

                        if VerificationService.revert_user_to_free(supabase, user_uuid):
                            reverted_count += 1
                        else:
                            error_count += 1

            except Exception as user_error:
                error_count += 1
                logfire.error(
                    f"Error processing user {user_uuid}: {str(user_error)}",
                    extra={"user_uuid": user_uuid, "error": str(user_error)}
                )
                continue

        logfire.info(
            f"Android subscription check completed",
            extra={
                "total_checked": total_checked,
                "expired": expired_count,
                "reverted": reverted_count,
                "active_renewed": active_renewed_count,
                "errors": error_count
            }
        )

        return SubscriptionCheckResponse(
            success=True,
            message=f"Android subscription check completed successfully. Active renewals: {active_renewed_count}",
            total_users_checked=total_checked,
            expired_subscriptions=expired_count,
            reverted_to_free=reverted_count,
            errors=error_count
        )

    except Exception as fatal_error:
        logfire.error(f"Fatal error during subscription check: {str(fatal_error)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check expired subscriptions: {str(fatal_error)}"
        )


if __name__ == "__main__":
    import asyncio
    import sys

    # Test get access token
    print("=" * 80)
    print("TESTING GOOGLE SERVICE ACCOUNT ACCESS TOKEN")
    print("=" * 80)
    token = get_google_access_token()
    print(f"Access Token: {token[:50]}...")

    # Test purchase verification with Google Play API
    async def verify_purchase():
        print("\n" + "=" * 80)
        print("TESTING PURCHASE VERIFICATION ENDPOINT")
        print("=" * 80)

        test_data = {
            "product_id": "abo_premium_20251025",
            "purchase_token": "pjnmjmiheicleagpchmocpme.AO-J1Ow3efP2k4LHsAVH1-JpzBbVk9tWWgfjvX39Ly9pqDQzRNnY-IcZzXEjGhvoNOZqJO-A23UI66EXXeUnpmnQI-jUvffxjh5uYfuOJmMXRZKosxzG254",
            "package_name": "info.sebastianorth.effortless"
        }

        # Construct Google Play Developer API URL
        google_api_url = (
            f"https://androidpublisher.googleapis.com/androidpublisher/v3/"
            f"applications/{test_data['package_name']}/purchases/subscriptions/"
            f"{test_data['product_id']}/tokens/{test_data['purchase_token']}"
        )

        # Prepare headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        print(f"\nTesting Google Play API with:")
        print(f"Product ID: {test_data['product_id']}")
        print(f"Package Name: {test_data['package_name']}")
        print(f"Purchase Token: {test_data['purchase_token'][:50]}...")
        print(f"\nAPI URL: {google_api_url}")

        try:
            async with httpx.AsyncClient() as client:
                print("\nCalling Google Play API...")
                response = await client.get(google_api_url, headers=headers, timeout=10.0)

                print(f"Response Status: {response.status_code}")
                print(f"Response Body: {response.text}")

                if response.status_code == 200:
                    purchase_data = response.json()
                    expiry_time_millis = purchase_data.get("expiryTimeMillis")
                    if expiry_time_millis:
                        expiry_timestamp = datetime.fromtimestamp(int(expiry_time_millis) / 1000)
                        print(f"\nPurchase verified successfully!")
                        print(f"Expiry Time: {expiry_timestamp.isoformat()}")
                else:
                    print(f"\nVerification failed with status: {response.status_code}")

        except Exception as e:
            print(f"\nError during API call: {str(e)}")
    def run_verify_purchase():
        logfire.configure()
        asyncio.run(check_expired_subscriptions())

    run_verify_purchase()