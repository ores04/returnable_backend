"""Service for managing shared tags between users."""
import logfire
from supabase import Client
from typing import List, Optional


def create_shared_tag(share_data: dict, service_client: Client) -> str:
    """Create a tag share between users.

    Args:
        share_data: Dictionary containing tag_id, user_shared_with, user_shares
        service_client: Supabase client instance

    Returns:
        UUID of the created share

    Raises:
        ValueError: If user tries to share with themselves
    """
    user_shared_with = share_data.get('user_shared_with')
    user_shares = share_data.get('user_shares')

    # Validate: user cannot share with themselves
    if user_shared_with == user_shares:
        raise ValueError("Cannot share tag with yourself")

    logfire.info(f"Creating shared tag: tag={share_data.get('tag_id')}, from={user_shares}, to={user_shared_with}")

    response = service_client.table('REMINDER_TAG_SHARED').insert(share_data).execute()

    if not response.data or len(response.data) == 0:
        raise ValueError("Failed to create shared tag")

    return response.data[0]['uuid']


def find_by_tag_id(tag_id: int, service_client: Client) -> List[dict]:
    """Get all shares for a tag.

    Args:
        tag_id: ID of the tag
        service_client: Supabase client instance

    Returns:
        List of share dictionaries
    """
    logfire.debug(f"Finding shares for tag {tag_id}")

    response = service_client.table('REMINDER_TAG_SHARED') \
        .select('*') \
        .eq('tag_id', tag_id) \
        .execute()

    return response.data


def find_shared_with_user(user_id: str, service_client: Client) -> List[dict]:
    """Get tags shared with a user.

    Args:
        user_id: UUID of the user
        service_client: Supabase client instance

    Returns:
        List of share dictionaries
    """
    logfire.debug(f"Finding tags shared with user {user_id}")

    response = service_client.table('REMINDER_TAG_SHARED') \
        .select('*') \
        .eq('user_shared_with', user_id) \
        .execute()

    return response.data


def find_shared_by_user(user_id: str, service_client: Client) -> List[dict]:
    """Get tags shared by a user.

    Args:
        user_id: UUID of the user
        service_client: Supabase client instance

    Returns:
        List of share dictionaries
    """
    logfire.debug(f"Finding tags shared by user {user_id}")

    response = service_client.table('REMINDER_TAG_SHARED') \
        .select('*') \
        .eq('user_shares', user_id) \
        .execute()

    return response.data


def find_shared_with_user_or_shared_by(user_id: str, service_client: Client) -> List[dict]:
    """Get tags shared with or by a user (bidirectional).

    Uses OR query to find shares in both directions.

    Args:
        user_id: UUID of the user
        service_client: Supabase client instance

    Returns:
        List of share dictionaries
    """
    logfire.debug(f"Finding tags shared with or by user {user_id}")

    # OR query: user_shares = user_id OR user_shared_with = user_id
    response = service_client.table('REMINDER_TAG_SHARED') \
        .select('*') \
        .or_(f'user_shares.eq.{user_id},user_shared_with.eq.{user_id}') \
        .execute()

    return response.data


def find_by_uuid(uuid: str, service_client: Client) -> Optional[dict]:
    """Get a share by its UUID.

    Args:
        uuid: UUID of the share
        service_client: Supabase client instance

    Returns:
        Share dictionary or None
    """
    logfire.debug(f"Finding share by UUID {uuid}")

    response = service_client.table('REMINDER_TAG_SHARED') \
        .select('*') \
        .eq('uuid', uuid) \
        .execute()

    if not response.data or len(response.data) == 0:
        return None

    return response.data[0]


def claim_shared_tag(share_id: str, user_id: str, service_client: Client) -> None:
    """Claim a shared tag by calling the RPC function.

    This calls the Supabase RPC function 'claim_shared_tag' which handles
    the complex logic of accepting a tag share.

    Args:
        share_id: UUID of the share
        user_id: UUID of the user claiming the tag
        service_client: Supabase client instance
    """
    logfire.info(f"Claiming shared tag: share_id={share_id}, user_id={user_id}")

    service_client.rpc('claim_shared_tag', {
        'p_share_id': share_id,
        'p_user_id': user_id
    }).execute()


def delete_shared_tag(uuid: str, service_client: Client) -> None:
    """Delete a share by UUID.

    Args:
        uuid: UUID of the share
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting shared tag {uuid}")

    service_client.table('REMINDER_TAG_SHARED') \
        .delete() \
        .eq('uuid', uuid) \
        .execute()


def delete_by_tag_and_user(tag_id: int, user_shared_with: str, service_client: Client) -> None:
    """Delete a specific share between tag and user.

    Args:
        tag_id: ID of the tag
        user_shared_with: UUID of the user the tag is shared with
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting share for tag {tag_id} with user {user_shared_with}")

    service_client.table('REMINDER_TAG_SHARED') \
        .delete() \
        .eq('tag_id', tag_id) \
        .eq('user_shared_with', user_shared_with) \
        .execute()


def delete_all_by_tag_id(tag_id: int, service_client: Client) -> None:
    """Delete all shares for a tag.

    Args:
        tag_id: ID of the tag
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting all shares for tag {tag_id}")

    service_client.table('REMINDER_TAG_SHARED') \
        .delete() \
        .eq('tag_id', tag_id) \
        .execute()
