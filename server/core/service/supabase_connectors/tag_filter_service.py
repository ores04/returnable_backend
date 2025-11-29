"""Service for managing user tag filter preferences."""
import logfire
from supabase import Client
from typing import List, Optional


def create_tag_filter(filter_data: dict, service_client: Client) -> int:
    """Create a tag filter.

    Args:
        filter_data: Dictionary containing tag_id and user_id
        service_client: Supabase client instance

    Returns:
        ID of the created filter
    """
    logfire.info(f"Creating tag filter: tag={filter_data.get('tag_id')}, user={filter_data.get('user_id')}")

    response = service_client.table('TAG_FILTER').insert(filter_data).execute()

    if not response.data or len(response.data) == 0:
        raise ValueError("Failed to create tag filter")

    return response.data[0]['id']


def find_all_tag_filters(
    user_id: Optional[str] = None,
    limit: Optional[int] = None,
    service_client: Client = None
) -> List[dict]:
    """Get all tag filters with optional filters.

    Args:
        user_id: Optional user ID to filter by
        limit: Optional limit on number of results
        service_client: Supabase client instance

    Returns:
        List of filter dictionaries
    """
    logfire.debug(f"Finding tag filters (user_id={user_id}, limit={limit})")

    query = service_client.table('TAG_FILTER').select('*')

    if user_id:
        query = query.eq('user_id', user_id)

    if limit:
        query = query.limit(limit)

    response = query.execute()

    return response.data


def find_by_id(filter_id: int, service_client: Client) -> Optional[dict]:
    """Get a tag filter by ID.

    Args:
        filter_id: ID of the filter
        service_client: Supabase client instance

    Returns:
        Filter dictionary or None
    """
    logfire.debug(f"Finding tag filter {filter_id}")

    response = service_client.table('TAG_FILTER') \
        .select('*') \
        .eq('id', filter_id) \
        .execute()

    if not response.data or len(response.data) == 0:
        return None

    return response.data[0]


def update_tag_filter(filter_id: int, filter_data: dict, service_client: Client) -> dict:
    """Update a tag filter.

    Args:
        filter_id: ID of the filter
        filter_data: Dictionary with fields to update
        service_client: Supabase client instance

    Returns:
        Updated filter dictionary
    """
    logfire.info(f"Updating tag filter {filter_id}")

    response = service_client.table('TAG_FILTER') \
        .update(filter_data) \
        .eq('id', filter_id) \
        .execute()

    if not response.data or len(response.data) == 0:
        raise ValueError(f"Tag filter {filter_id} not found")

    return response.data[0]


def delete_tag_filter(filter_id: int, service_client: Client) -> None:
    """Delete a tag filter by ID.

    Args:
        filter_id: ID of the filter
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting tag filter {filter_id}")

    service_client.table('TAG_FILTER') \
        .delete() \
        .eq('id', filter_id) \
        .execute()


def delete_by_tag_id(tag_id: int, service_client: Client) -> None:
    """Delete all filters for a tag.

    Args:
        tag_id: ID of the tag
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting all filters for tag {tag_id}")

    service_client.table('TAG_FILTER') \
        .delete() \
        .eq('tag_id', tag_id) \
        .execute()


def replace_user_tag_filters(user_id: str, tag_ids: List[int], service_client: Client) -> None:
    """Replace all tag filters for a user.

    This preserves the delete-all + insert pattern from the frontend:
    1. Delete all existing filters for the user
    2. Insert new filters for the provided tag IDs

    Args:
        user_id: UUID of the user
        tag_ids: List of tag IDs to set as filters
        service_client: Supabase client instance
    """
    logfire.info(f"Replacing tag filters for user {user_id} with {len(tag_ids)} tags")

    # Step 1: Delete all existing filters for the user
    service_client.table('TAG_FILTER') \
        .delete() \
        .eq('user_id', user_id) \
        .execute()

    # Step 2: Insert new filters if any
    if tag_ids:
        filters = [{'tag_id': tag_id, 'user_id': user_id} for tag_id in tag_ids]
        service_client.table('TAG_FILTER').insert(filters).execute()


def get_active_tag_ids(user_id: str, service_client: Client) -> List[int]:
    """Get active tag IDs for a user.

    Args:
        user_id: UUID of the user
        service_client: Supabase client instance

    Returns:
        List of tag IDs
    """
    logfire.debug(f"Getting active tag IDs for user {user_id}")

    response = service_client.table('TAG_FILTER') \
        .select('tag_id') \
        .eq('user_id', user_id) \
        .execute()

    return [item['tag_id'] for item in response.data]
