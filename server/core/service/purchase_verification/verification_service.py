"""
Shared verification service for iOS and Android in-app purchase verification.

This module contains common logic for:
- User authentication and UUID extraction
- Database operations for subscription management
- Subscription expiration checking
"""
import logfire
from fastapi import HTTPException
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from server.core.service.supabase_connectors.supabase_client import (
    get_supabase_client,
    get_supabase_service_role_client,
    USER_META_INFORMATION_TABLE_NAME
)


class VerificationService:
    """Service class for common purchase verification operations."""

    @staticmethod
    def get_authenticated_user_uuid(jwt_token: str) -> Tuple[Any, str]:
        """
        Extract user UUID from JWT token.

        Args:
            jwt_token: JWT token from Authorization header

        Returns:
            Tuple of (supabase_client, user_uuid)

        Raises:
            HTTPException: If authentication fails
        """
        try:
            supabase = get_supabase_client(jwt_token=jwt_token)
            user = supabase.auth.get_user(jwt_token).user
            user_uuid = user.id
            logfire.info(f"Authenticated user UUID: {user_uuid}")
            return supabase, user_uuid
        except Exception as e:
            logfire.error(f"Authentication failed: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired supabase authentication token"
            )

    @staticmethod
    def update_user_subscription(
        supabase_client: Any,
        user_uuid: str,
        product_id: str,
        expiration_time: str,
        purchase_token: str
    ) -> Dict[str, Any]:
        """
        Update user subscription details in database.

        Args:
            supabase_client: Authenticated Supabase client
            user_uuid: User's unique identifier
            product_id: Product/subscription ID
            expiration_time: ISO format expiration timestamp
            purchase_token: Platform-specific purchase token

        Returns:
            Updated user data

        Raises:
            HTTPException: If user not found or update fails
        """
        update_data = {
            "tier_product_id": product_id,
            "tier_expiration_time": expiration_time,
            "purchase_token": purchase_token
        }

        logfire.info(
            f"Updating user subscription in database",
            extra={"user_uuid": user_uuid, "update_data": update_data}
        )

        result = supabase_client.from_(USER_META_INFORMATION_TABLE_NAME)\
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
            f"Successfully updated subscription for user {user_uuid}",
            extra={
                "product_id": product_id,
                "expiry": expiration_time,
                "user_uuid": user_uuid
            }
        )

        return result.data[0]

    @staticmethod
    def revert_user_to_free(
        supabase_client: Any,
        user_uuid: str
    ) -> bool:
        """
        Revert user to free tier.

        Args:
            supabase_client: Supabase client (can be authenticated or service role)
            user_uuid: User's unique identifier

        Returns:
            True if successful, False otherwise
        """
        logfire.info(
            f"Reverting user {user_uuid} to free tier",
            extra={"user_uuid": user_uuid}
        )

        update_result = supabase_client.from_(USER_META_INFORMATION_TABLE_NAME)\
            .update({
                "tier_product_id": "free",
                "tier_expiration_time": None,
                "purchase_token": None
            })\
            .eq("uuid", user_uuid)\
            .execute()

        success = bool(update_result.data)

        if success:
            logfire.info(f"Successfully reverted user {user_uuid} to free tier")
        else:
            logfire.error(f"Failed to revert user {user_uuid} to free tier")

        return success

    @staticmethod
    def get_user_subscription_data(
        supabase_client: Any,
        user_uuid: str
    ) -> Dict[str, Any]:
        """
        Get user's subscription data from database.

        Args:
            supabase_client: Supabase client
            user_uuid: User's unique identifier

        Returns:
            Dictionary with subscription data

        Raises:
            HTTPException: If user not found
        """
        result = supabase_client.from_(USER_META_INFORMATION_TABLE_NAME)\
            .select("tier_product_id, tier_expiration_time, purchase_token")\
            .eq("uuid", user_uuid)\
            .single()\
            .execute()

        user_data = result.data
        if not user_data:
            logfire.error(f"User profile not found in USER_META_INFORMATION for UUID: {user_uuid}")
            raise HTTPException(
                status_code=404,
                detail="User profile not found in USER_META_INFORMATION table"
            )

        return user_data

    @staticmethod
    def is_subscription_expired_locally(expiration_time_str: str) -> bool:
        """
        Check if subscription has expired based on local timestamp comparison.

        Args:
            expiration_time_str: ISO format expiration timestamp

        Returns:
            True if expired, False if still valid
        """
        current_time = datetime.now(timezone.utc)
        expiration_time = datetime.fromisoformat(expiration_time_str.replace('Z', '+00:00'))
        return expiration_time <= current_time

    @staticmethod
    def update_subscription_expiration(
        supabase_client: Any,
        user_uuid: str,
        new_expiration_time: str
    ) -> bool:
        """
        Update subscription expiration time only (subscription still active).

        Args:
            supabase_client: Supabase client
            user_uuid: User's unique identifier
            new_expiration_time: New ISO format expiration timestamp

        Returns:
            True if successful, False otherwise
        """
        logfire.info(
            f"Updating expiration time for user {user_uuid} to {new_expiration_time}",
            extra={"user_uuid": user_uuid, "new_expiry": new_expiration_time}
        )

        update_result = supabase_client.from_(USER_META_INFORMATION_TABLE_NAME)\
            .update({
                "tier_expiration_time": new_expiration_time
            })\
            .eq("uuid", user_uuid)\
            .execute()

        return bool(update_result.data)

    @staticmethod
    def get_all_non_free_users() -> List[Dict[str, Any]]:
        """
        Get all users with non-free subscriptions.

        Returns:
            List of user subscription data

        Raises:
            HTTPException: If service role client fails
        """
        try:
            supabase = get_supabase_service_role_client()
        except Exception as db_error:
            logfire.error(f"Failed to get service role client: {str(db_error)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to get privileged database access"
            )

        result = supabase.from_(USER_META_INFORMATION_TABLE_NAME)\
            .select("uuid, tier_product_id, tier_expiration_time, purchase_token")\
            .neq("tier_product_id", "free")\
            .not_.is_("tier_expiration_time", "null")\
            .execute()

        users = result.data if result.data else []
        logfire.info(f"Found {len(users)} users with non-free tiers")

        return users
