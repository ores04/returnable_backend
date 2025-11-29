"""Parent Reminder Service for orchestrating complex reminder operations."""
import logfire
from supabase import Client
from typing import List, Optional
from datetime import datetime

from . import supabase_reminder_client as reminder_client
from . import tag_connection_service
from . import tag_shared_service
from . import supabase_tag_service as tag_service


def find_all_reminders_by_user_id(
    user_id: str,
    after: Optional[datetime],
    service_client: Client
) -> List[dict]:
    """Orchestrates: owned reminders + shared reminders, then fetches full data.

    This combines owned and shared reminder IDs, deduplicates, and fetches
    full reminder data with nested times and tags.

    Args:
        user_id: UUID of the user
        after: Filter reminders after this datetime
        service_client: Supabase client instance

    Returns:
        List of reminder dictionaries with nested times and tags
    """
    logfire.info(f"Finding all reminders for user {user_id} (after={after})")

    # Step 1: Get owned reminder IDs
    owned_ids = reminder_client.find_user_reminder_ids(
        user_id=user_id,
        after=after,
        limit=1000,  # Reasonable limit
        include_overdue=True,
        service_client=service_client
    )

    # Step 2: Get shared reminder IDs via shared tags
    shared_ids = find_reminders_ids_shared_with_user(
        user_id=user_id,
        after=after,
        include_overdue=True,
        service_client=service_client
    )

    # Step 3: Combine and deduplicate
    all_ids = list(set(owned_ids + shared_ids))

    if not all_ids:
        return []

    # Step 4: Fetch full reminders with nested times and tags
    reminders = reminder_client.find_reminders_by_id_list(all_ids, service_client)

    return reminders


def find_reminders_ids_shared_with_user(
    user_id: str,
    after: Optional[datetime],
    include_overdue: bool,
    service_client: Client
) -> List[int]:
    """Get reminder IDs from shared tags.

    Args:
        user_id: UUID of the user
        after: Filter by event_time
        include_overdue: Include overdue reminders
        service_client: Supabase client instance

    Returns:
        List of reminder IDs
    """
    logfire.debug(f"Finding reminder IDs shared with user {user_id}")

    # Step 1: Find shared tags (accepted shares)
    shared_tags_data = tag_shared_service.find_shared_with_user(user_id, service_client)

    if not shared_tags_data:
        return []

    shared_tag_ids = [share['tag_id'] for share in shared_tags_data]

    # Step 2: Find connections with reminder filters
    connections = tag_connection_service.find_by_tag_id_list_with_reminder_filters(
        tag_ids=shared_tag_ids,
        after=after,
        include_overdue=include_overdue,
        service_client=service_client
    )

    # Step 3: Extract unique reminder IDs
    reminder_ids = list(set(conn['reminder_id'] for conn in connections))

    return reminder_ids


def create_reminder_with_tags(
    reminder_data: dict,
    tag_ids: List[int],
    service_client: Client
) -> int:
    """Create reminder and attach tags.

    Args:
        reminder_data: Dictionary with reminder fields
        tag_ids: List of tag IDs to attach
        service_client: Supabase client instance

    Returns:
        ID of created reminder
    """
    logfire.info(f"Creating reminder with {len(tag_ids)} tags")

    # Step 1: Create reminder
    reminder_id = reminder_client.create_reminder(reminder_data, service_client)

    # Step 2: Create tag connections
    for tag_id in tag_ids:
        connection_data = {
            'reminder_id': reminder_id,
            'tag_id': tag_id
        }
        tag_connection_service.create_connection(connection_data, service_client)

    return reminder_id


def update_reminder_with_tags(
    reminder_id: int,
    reminder_data: dict,
    tag_ids: Optional[List[int]],
    service_client: Client
) -> dict:
    """Update reminder and sync tags.

    This syncs tags by comparing existing vs new:
    - Deletes removed tags
    - Adds new tags

    Args:
        reminder_id: ID of the reminder
        reminder_data: Dictionary with fields to update
        tag_ids: New list of tag IDs (if None, don't sync tags)
        service_client: Supabase client instance

    Returns:
        Updated reminder dictionary
    """
    logfire.info(f"Updating reminder {reminder_id} with tag sync")

    # Step 1: Update reminder
    updated_reminder = reminder_client.update_reminder(
        reminder_id=reminder_id,
        reminder_data=reminder_data,
        service_client=service_client,
        replace_times=True
    )

    # Step 2: Sync tags if provided
    if tag_ids is not None:
        # Get existing connections
        existing_connections = tag_connection_service.find_by_reminder_id(
            reminder_id,
            service_client
        )
        existing_tag_ids = set(conn['tag_id'] for conn in existing_connections)
        new_tag_ids = set(tag_ids)

        # Delete removed connections
        tags_to_remove = existing_tag_ids - new_tag_ids
        for tag_id in tags_to_remove:
            tag_connection_service.delete_by_reminder_and_tag(
                reminder_id,
                tag_id,
                service_client
            )

        # Add new connections
        tags_to_add = new_tag_ids - existing_tag_ids
        for tag_id in tags_to_add:
            connection_data = {
                'reminder_id': reminder_id,
                'tag_id': tag_id
            }
            tag_connection_service.create_connection(connection_data, service_client)

    return updated_reminder
