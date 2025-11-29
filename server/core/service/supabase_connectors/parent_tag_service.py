"""Parent Tag Service for orchestrating tag operations."""
import logfire
from supabase import Client
from typing import List, Dict

from . import supabase_tag_service as tag_service
from . import tag_shared_service


def find_all_available_tags(user_id: str, service_client: Client) -> Dict[str, any]:
    """Get owned + shared tags with deduplication.

    Returns a dictionary indicating whether the user has shared tags and
    the combined list of tags.

    Args:
        user_id: UUID of the user
        service_client: Supabase client instance

    Returns:
        Dictionary with keys:
        - "has_shared": boolean indicating if user has any shared tags
        - "tags": list of tag dictionaries (deduplicated)
    """
    logfire.info(f"Finding all available tags for user {user_id}")

    # Get owned tags
    owned_tags = tag_service.find_tags_owned_by_user(user_id, service_client)

    # Get shared tags (accepted shares only)
    shared_tags_data = tag_shared_service.find_shared_with_user(user_id, service_client)
    has_shared = len(shared_tags_data) > 0

    # Fetch the actual tag data for shared tags
    shared_tags = []
    if shared_tags_data:
        shared_tag_ids = [share['tag_id'] for share in shared_tags_data]

        # Fetch tags in batch if IDs available
        if shared_tag_ids:
            # Use direct query for efficiency
            response = service_client.table('REMINDER_TAG') \
                .select('*') \
                .in_('id', shared_tag_ids) \
                .execute()
            shared_tags = response.data

    # Combine and deduplicate by ID
    all_tags = owned_tags + shared_tags
    seen_ids = set()
    deduplicated_tags = []
    for tag in all_tags:
        if tag['id'] not in seen_ids:
            seen_ids.add(tag['id'])
            deduplicated_tags.append(tag)

    return {
        "has_shared": has_shared,
        "tags": deduplicated_tags
    }
