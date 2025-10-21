"""
iOS/App Store In-App Purchase Verification Endpoint.
"""
import os
import logfire
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any
import httpx
from datetime import datetime, timezone
import jwt
import time

from server.core.service.purchase_verification.models import (
    IOSPurchaseVerificationRequest,
    PurchaseVerificationResponse,
    SubscriptionCheckResponse
)
from server.core.service.purchase_verification.verification_service import VerificationService

router = APIRouter()

# OAuth2 scheme for JWT token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Path to the App Store Connect API key file
APP_STORE_KEY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "app_store_connect_key.p8"
)

# Apple App Store Connect credentials from environment variables
APPLE_KEY_ID = os.environ.get("APPLE_KEY_ID")
APPLE_ISSUER_ID = os.environ.get("APPLE_ISSUER_ID")

# Validate credentials are configured
if not APPLE_KEY_ID:
    logfire.error("APPLE_KEY_ID environment variable is not set")
if not APPLE_ISSUER_ID:
    logfire.error("APPLE_ISSUER_ID environment variable is not set")
if not os.path.exists(APP_STORE_KEY_FILE):
    logfire.error(f"App Store Connect key file not found at {APP_STORE_KEY_FILE}")

# Load private key
_private_key = None
try:
    with open(APP_STORE_KEY_FILE, 'r') as key_file:
        _private_key = key_file.read()
    logfire.info(f"Successfully loaded App Store Connect private key from {APP_STORE_KEY_FILE}")
except Exception as e:
    logfire.error(f"Failed to load App Store Connect private key: {str(e)}")


def generate_app_store_jwt() -> str:
    """
    Generate a JWT token for App Store Server API authentication.

    The JWT is valid for 60 minutes and uses ES256 algorithm.

    Returns:
        str: JWT token for authentication

    Raises:
        HTTPException: If credentials are not configured or JWT generation fails
    """
    if not APPLE_KEY_ID or not APPLE_ISSUER_ID or not _private_key:
        raise HTTPException(
            status_code=500,
            detail="App Store Connect credentials not properly configured"
        )

    # JWT expires in 60 minutes (max allowed by Apple is 60 minutes)
    expiration_time = int(time.time()) + 3600

    headers = {
        "alg": "ES256",
        "kid": APPLE_KEY_ID,
        "typ": "JWT"
    }

    payload = {
        "iss": APPLE_ISSUER_ID,
        "iat": int(time.time()),
        "exp": expiration_time,
        "aud": "appstoreconnect-v1",
        "bid": "info.sebastianorth.effortless"  # Bundle ID
    }

    try:
        token = jwt.encode(payload, _private_key, algorithm="ES256", headers=headers)
        logfire.debug("Generated App Store JWT token")
        return token
    except Exception as e:
        logfire.error(f"Failed to generate JWT token: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate App Store authentication token: {str(e)}"
        )


@router.post(
    "/verify",
    response_model=PurchaseVerificationResponse,
    summary="Verify iOS In-App Purchase",
    description="Verifies an iOS in-app purchase using Apple App Store Server API and updates user subscription status"
)
async def verify_purchase_ios(
    request: IOSPurchaseVerificationRequest,
    token: str = Depends(oauth2_scheme)
) -> PurchaseVerificationResponse:
    """
    Verify an iOS in-app purchase and update the authenticated user's subscription status.

    This endpoint:
    1. Authenticates the user via JWT token (OAuth2)
    2. Calls the Apple App Store Server API to verify the purchase
    3. If verification succeeds (200 OK), updates the USER_META_INFORMATION table
       with the product_id and expiration_time for the authenticated user

    Args:
        request: IOSPurchaseVerificationRequest containing product_id, transaction_id, and bundle_id
        token: JWT token from Authorization header (automatically extracted by Depends)

    Returns:
        PurchaseVerificationResponse with verification status and details

    Raises:
        HTTPException: If authentication fails, Apple API call fails, or database update fails
    """
    logfire.info(f"Verifying iOS purchase for product_id: {request.product_id}")

    # Generate App Store JWT token
    app_store_token = generate_app_store_jwt()

    # Get authenticated user's UUID from token
    supabase, user_uuid = VerificationService.get_authenticated_user_uuid(token)

    # Construct Apple App Store Server API URL
    # Using the subscription status endpoint
    # transaction_id is stored in purchase_token field
    transaction_id = request.purchase_token
    apple_api_url = f"https://api.storekit.apple.com/inAppPurchase/v1/subscriptions/{transaction_id}"

    # Prepare authorization headers
    headers = {
        "Authorization": f"Bearer {app_store_token}",
        "Content-Type": "application/json"
    }

    try:
        # Call Apple App Store Server API to verify the purchase
        async with httpx.AsyncClient() as client:
            logfire.debug(f"Calling Apple App Store Server API for verification")
            response = await client.get(apple_api_url, headers=headers, timeout=10.0)

            logfire.info(
                f"Apple API response status: {response.status_code}",
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

            # Parse the Apple API response
            purchase_data = response.json()
            logfire.debug(f"Purchase data received", extra={"purchase_data": purchase_data})

            # Extract subscription data from response
            # Apple's response structure: { "data": [{ "lastTransactions": [...] }] }
            data_items = purchase_data.get("data", [])
            if not data_items:
                logfire.error("No data in purchase response")
                raise HTTPException(
                    status_code=500,
                    detail="Invalid purchase data: missing data"
                )

            # Get the first subscription data
            subscription_data = data_items[0]
            last_transactions = subscription_data.get("lastTransactions", [])

            if not last_transactions:
                logfire.error("No transactions in subscription data")
                raise HTTPException(
                    status_code=500,
                    detail="Invalid purchase data: missing transactions"
                )

            # Get the most recent transaction
            transaction = last_transactions[0]

            # Decode the signed transaction (JWS format)
            # For simplicity, we'll extract the expiration from the top-level response
            # In production, you should decode and validate the JWS

            # Check subscription status
            subscription_status = subscription_data.get("status")

            # Status codes: 1 = Active, 2 = Expired, 3 = In Billing Retry, 4 = In Grace Period, 5 = Revoked
            active_statuses = [1, 3, 4]  # Active, Billing Retry, Grace Period

            if subscription_status not in active_statuses:
                logfire.warning(
                    f"Subscription not active. Status: {subscription_status}",
                    extra={"user_uuid": user_uuid, "status": subscription_status}
                )
                return PurchaseVerificationResponse(
                    success=False,
                    message=f"Subscription not active (status: {subscription_status})"
                )

            # Extract expiration time from renewalInfo or transaction
            renewal_info = subscription_data.get("renewalInfo")

            # Parse the signed renewal info to get expiration
            # For now, we'll use a simplified approach
            # In production, decode the JWS token to get precise expiration

            # Attempt to get expiration from various fields
            expiry_time_ms = None

            # Try to decode the transaction JWS to get expiresDate
            signed_transaction_info = transaction.get("signedTransactionInfo")
            if signed_transaction_info:
                try:
                    # Decode without verification (for demo purposes)
                    # In production, verify the signature
                    decoded_transaction = jwt.decode(
                        signed_transaction_info,
                        options={"verify_signature": False}
                    )
                    expiry_time_ms = decoded_transaction.get("expiresDate")
                    logfire.debug(f"Decoded transaction expiry: {expiry_time_ms}")
                except Exception as decode_error:
                    logfire.warning(f"Failed to decode transaction JWS: {str(decode_error)}")

            if not expiry_time_ms:
                logfire.error("No expiry time in purchase data")
                raise HTTPException(
                    status_code=500,
                    detail="Invalid purchase data: missing expiry time"
                )

            # Convert milliseconds timestamp to datetime
            expiry_timestamp = datetime.fromtimestamp(int(expiry_time_ms) / 1000, tz=timezone.utc)
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
                purchase_token=transaction_id
            )

            return PurchaseVerificationResponse(
                success=True,
                message="Purchase verified and subscription updated successfully",
                product_id=request.product_id,
                expiration_time=expiry_iso
            )

    except httpx.TimeoutException:
        logfire.error("Timeout calling Apple App Store Server API")
        raise HTTPException(
            status_code=504,
            detail="Timeout verifying purchase with Apple App Store Server API"
        )
    except httpx.RequestError as e:
        logfire.error(f"Request error calling Apple App Store Server API: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Error communicating with Apple App Store Server API: {str(e)}"
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
    "/check-expired-subscription",
    response_model=SubscriptionCheckResponse,
    summary="Check and Update Expired Subscription for Authenticated User",
    description="Checks if the authenticated user's subscription has expired and reverts to free tier if no longer subscribed."
)
async def check_expired_subscription(
    token: str = Depends(oauth2_scheme)
) -> SubscriptionCheckResponse:
    """
    Check if the authenticated user's subscription has expired and revert to free tier if needed.

    This endpoint:
    1. Authenticates the user via JWT token (OAuth2)
    2. Queries the USER_META_INFORMATION table for the user's subscription details
    3. Verifies the subscription status via Apple App Store Server API
    4. If subscription is not active (expired, canceled, etc.), reverts user to 'free' tier
    5. If subscription is still active, updates the expiration time in the database

    Args:
        token: JWT token from Authorization header (automatically extracted by Depends)

    Returns:
        SubscriptionCheckResponse with the result of the check
    """
    logfire.info("Starting expired subscription check for authenticated user (iOS)")

    # Generate App Store JWT token
    app_store_token = generate_app_store_jwt()

    # Get authenticated user's UUID from token
    supabase, user_uuid = VerificationService.get_authenticated_user_uuid(token)

    try:
        # Get user's subscription data
        user_data = VerificationService.get_user_subscription_data(supabase, user_uuid)

        product_id = user_data.get("tier_product_id")
        expiration_time_str = user_data.get("tier_expiration_time")
        purchase_token = user_data.get("purchase_token")  # This is the transaction_id for iOS

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

        # Subscription appears expired, verify with Apple API
        logfire.info(
            f"User {user_uuid} subscription expired at {expiration_time_str}, verifying with Apple",
            extra={"user_uuid": user_uuid, "product_id": product_id}
        )

        if not purchase_token:
            logfire.warning(
                f"User {user_uuid} has no purchase token, reverting to free",
                extra={"user_uuid": user_uuid}
            )
            VerificationService.revert_user_to_free(supabase, user_uuid)
            return SubscriptionCheckResponse(
                success=True,
                message="No purchase token, reverted to free tier",
                total_users_checked=1,
                expired_subscriptions=1,
                reverted_to_free=1,
                errors=0
            )

        # Call Apple App Store Server API to check subscription status
        transaction_id = purchase_token
        apple_api_url = f"https://api.storekit.apple.com/inAppPurchase/v1/subscriptions/{transaction_id}"

        headers = {
            "Authorization": f"Bearer {app_store_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(apple_api_url, headers=headers, timeout=10.0)

            if response.status_code != 200:
                logfire.warning(
                    f"Apple API returned {response.status_code} for user {user_uuid}, reverting to free",
                    extra={"user_uuid": user_uuid, "status_code": response.status_code}
                )
                VerificationService.revert_user_to_free(supabase, user_uuid)
                return SubscriptionCheckResponse(
                    success=True,
                    message="Subscription verification failed, reverted to free tier",
                    total_users_checked=1,
                    expired_subscriptions=1,
                    reverted_to_free=1,
                    errors=0
                )

            # Parse subscription data
            subscription_data = response.json()
            data_items = subscription_data.get("data", [])

            if not data_items:
                VerificationService.revert_user_to_free(supabase, user_uuid)
                return SubscriptionCheckResponse(
                    success=True,
                    message="No subscription data, reverted to free tier",
                    total_users_checked=1,
                    expired_subscriptions=1,
                    reverted_to_free=1,
                    errors=0
                )

            subscription_info = data_items[0]
            subscription_status = subscription_info.get("status")

            # Check if subscription is active
            active_statuses = [1, 3, 4]  # Active, Billing Retry, Grace Period
            is_active = subscription_status in active_statuses

            if is_active:
                # Extract new expiration time
                last_transactions = subscription_info.get("lastTransactions", [])
                if last_transactions:
                    transaction = last_transactions[0]
                    signed_transaction_info = transaction.get("signedTransactionInfo")

                    if signed_transaction_info:
                        try:
                            decoded_transaction = jwt.decode(
                                signed_transaction_info,
                                options={"verify_signature": False}
                            )
                            expiry_time_ms = decoded_transaction.get("expiresDate")

                            if expiry_time_ms:
                                new_expiry = datetime.fromtimestamp(int(expiry_time_ms) / 1000, tz=timezone.utc)
                                new_expiry_iso = new_expiry.isoformat()

                                logfire.info(
                                    f"Subscription still active for user {user_uuid}, updating expiry to {new_expiry_iso}",
                                    extra={"user_uuid": user_uuid, "new_expiry": new_expiry_iso}
                                )

                                VerificationService.update_subscription_expiration(
                                    supabase, user_uuid, new_expiry_iso
                                )

                                return SubscriptionCheckResponse(
                                    success=True,
                                    message="Subscription still active, expiry updated",
                                    total_users_checked=1,
                                    expired_subscriptions=1,
                                    reverted_to_free=0,
                                    errors=0
                                )
                        except Exception as decode_error:
                            logfire.error(f"Failed to decode transaction: {str(decode_error)}")

            # Subscription is not active, revert to free
            logfire.info(
                f"Subscription not active for user {user_uuid} (status: {subscription_status}), reverting to free",
                extra={"user_uuid": user_uuid, "status": subscription_status}
            )

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
        logfire.error("Timeout calling Apple App Store Server API")
        raise HTTPException(
            status_code=504,
            detail="Timeout verifying purchase with Apple App Store Server API"
        )
    except httpx.RequestError as e:
        logfire.error(f"Request error calling Apple App Store Server API: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Error communicating with Apple App Store Server API: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Unexpected error during subscription check: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/check-expired-subscriptions",
    response_model=SubscriptionCheckResponse,
    summary="Check and Update Expired Subscriptions (iOS)",
    description="Checks all iOS users with expired subscriptions and reverts them to free tier if no longer subscribed. Requires service role privileges."
)
async def check_expired_subscriptions() -> SubscriptionCheckResponse:
    """
    Check all iOS users for expired subscriptions and revert to free tier if needed.

    This endpoint:
    1. Uses service role client to query all users with non-free tier_product_id
    2. For each user, verifies their subscription status via Apple App Store Server API
    3. If subscription is not active (expired, canceled, etc.), reverts user to 'free' tier
    4. If subscription is still active, updates the expiration time in the database
    5. Intended to be called by a cron job at midnight

    Returns:
        SubscriptionCheckResponse with statistics about the check

    Note:
        This endpoint has no authentication as it's meant to be called by a cron job.
        In production, you should add IP whitelisting or a secret token for security.
    """
    logfire.info("Starting expired subscription check for all iOS users")

    # Generate App Store JWT token
    app_store_token = generate_app_store_jwt()

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

            # Verify subscription status with Apple API
            if not purchase_token:
                logfire.warning(
                    f"User {user_uuid} has no purchase token, reverting to free",
                    extra={"user_uuid": user_uuid}
                )
                if VerificationService.revert_user_to_free(supabase, user_uuid):
                    reverted_count += 1
                else:
                    error_count += 1
                continue

            # Call Apple App Store Server API
            transaction_id = purchase_token
            apple_api_url = f"https://api.storekit.apple.com/inAppPurchase/v1/subscriptions/{transaction_id}"

            headers = {
                "Authorization": f"Bearer {app_store_token}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient() as client:
                logfire.debug(
                    f"Verifying subscription for user {user_uuid} with Apple API",
                    extra={"user_uuid": user_uuid, "transaction_id": transaction_id[:30]}
                )
                response = await client.get(apple_api_url, headers=headers, timeout=10.0)

                if response.status_code != 200:
                    logfire.warning(
                        f"Apple API returned {response.status_code} for user {user_uuid}, reverting to free",
                        extra={"user_uuid": user_uuid, "status_code": response.status_code}
                    )
                    if VerificationService.revert_user_to_free(supabase, user_uuid):
                        reverted_count += 1
                    else:
                        error_count += 1
                    continue

                # Parse subscription data
                subscription_data = response.json()
                data_items = subscription_data.get("data", [])

                if not data_items:
                    if VerificationService.revert_user_to_free(supabase, user_uuid):
                        reverted_count += 1
                    else:
                        error_count += 1
                    continue

                subscription_info = data_items[0]
                subscription_status = subscription_info.get("status")

                logfire.info(
                    f"Apple API subscription status for user {user_uuid}: {subscription_status}",
                    extra={"user_uuid": user_uuid, "status": subscription_status}
                )

                # Check if subscription is active
                active_statuses = [1, 3, 4]  # Active, Billing Retry, Grace Period
                is_active = subscription_status in active_statuses

                if is_active:
                    # Extract new expiration time
                    last_transactions = subscription_info.get("lastTransactions", [])
                    if last_transactions:
                        transaction = last_transactions[0]
                        signed_transaction_info = transaction.get("signedTransactionInfo")

                        if signed_transaction_info:
                            try:
                                decoded_transaction = jwt.decode(
                                    signed_transaction_info,
                                    options={"verify_signature": False}
                                )
                                expiry_time_ms = decoded_transaction.get("expiresDate")

                                if expiry_time_ms:
                                    new_expiry = datetime.fromtimestamp(int(expiry_time_ms) / 1000, tz=timezone.utc)
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
                            except Exception as decode_error:
                                logfire.error(
                                    f"Failed to decode transaction for user {user_uuid}: {str(decode_error)}",
                                    extra={"user_uuid": user_uuid}
                                )
                                error_count += 1
                        else:
                            logfire.error(
                                f"No signed transaction info for user {user_uuid}",
                                extra={"user_uuid": user_uuid}
                            )
                            error_count += 1
                    else:
                        logfire.error(
                            f"No transactions in subscription data for user {user_uuid}",
                            extra={"user_uuid": user_uuid}
                        )
                        error_count += 1
                else:
                    # Subscription is not active, revert to free
                    logfire.info(
                        f"Subscription not active for user {user_uuid} (status: {subscription_status}), reverting to free",
                        extra={"user_uuid": user_uuid, "status": subscription_status}
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
        f"iOS subscription check completed",
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
        message=f"iOS subscription check completed successfully. Active renewals: {active_renewed_count}",
        total_users_checked=total_checked,
        expired_subscriptions=expired_count,
        reverted_to_free=reverted_count,
        errors=error_count
    )
