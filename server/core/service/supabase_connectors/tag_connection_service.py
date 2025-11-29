"""Service for managing reminder-tag connections."""
import logfire
from supabase import Client
from typing import List, Optional, Dict
from datetime import datetime

from core.models.reminder_models import ReminderTagConnectionModel


def create_connection(connection_data: dict, service_client: Client) -> int:
    """Create a reminder-tag connection.

    Args:
        connection_data: Dictionary containing reminder_id and tag_id
        service_client: Supabase client instance

    Returns:
        ID of the created connection
    """
    logfire.info(f"Creating tag connection: reminder={connection_data.get('reminder_id')}, tag={connection_data.get('tag_id')}")

    response = service_client.table('REMINDER_TAG_CONNECTION').insert(connection_data).execute()

    if not response.data or len(response.data) == 0:
        raise ValueError("Failed to create tag connection")

    return response.data[0]['id']


def find_by_reminder_id(reminder_id: int, service_client: Client) -> List[dict]:
    """Get all tag connections for a reminder.

    Args:
        reminder_id: ID of the reminder
        service_client: Supabase client instance

    Returns:
        List of connection dictionaries
    """
    logfire.debug(f"Finding tag connections for reminder {reminder_id}")

    response = service_client.table('REMINDER_TAG_CONNECTION') \
        .select('*') \
        .eq('reminder_id', reminder_id) \
        .execute()

    return response.data


def find_by_tag_id(tag_id: int, service_client: Client) -> List[dict]:
    """Get all reminder connections for a tag.

    Args:
        tag_id: ID of the tag
        service_client: Supabase client instance

    Returns:
        List of connection dictionaries
    """
    logfire.debug(f"Finding reminder connections for tag {tag_id}")

    response = service_client.table('REMINDER_TAG_CONNECTION') \
        .select('*') \
        .eq('tag_id', tag_id) \
        .execute()

    return response.data


def find_by_tag_id_list(tag_ids: List[int], service_client: Client) -> List[dict]:
    """Get connections for multiple tags.

    Args:
        tag_ids: List of tag IDs
        service_client: Supabase client instance

    Returns:
        List of connection dictionaries
    """
    logfire.debug(f"Finding connections for {len(tag_ids)} tags")

    if not tag_ids:
        return []

    response = service_client.table('REMINDER_TAG_CONNECTION') \
        .select('*') \
        .in_('tag_id', tag_ids) \
        .execute()

    return response.data


def find_by_tag_id_list_with_reminder_filters(
    tag_ids: List[int],
    after: Optional[datetime] = None,
    include_overdue: bool = False,
    service_client: Client = None
) -> List[dict]:
    """Get connections by tag list with reminder filters using inner join.

    This preserves the complex query pattern from the frontend:
    - Uses !inner join to filter by reminder properties
    - Supports OR query for overdue reminders

    Args:
        tag_ids: List of tag IDs
        after: Filter reminders after this datetime
        include_overdue: Include overdue reminders regardless of date
        service_client: Supabase client instance

    Returns:
        List of connection dictionaries with nested reminder data
    """
    logfire.info(f"Finding connections for {len(tag_ids)} tags with reminder filters (after={after}, include_overdue={include_overdue})")

    if not tag_ids:
        return []

    # Build query with inner join to REMINDER table
    query = service_client.table('REMINDER_TAG_CONNECTION') \
        .select('*, REMINDER!inner(event_time, done)') \
        .in_('tag_id', tag_ids)

    # Apply filters on the joined REMINDER table
    if after and include_overdue:
        # OR query: event_time > after OR done = false
        after_str = after.isoformat()
        query = query.or_(f'event_time.gt.{after_str},done.eq.false', referencedTable='REMINDER')
    elif after:
        # Simple filter: event_time > after
        query = query.filter('REMINDER.event_time', 'gt', after.isoformat())

    response = query.execute()

    return response.data


def delete_connection(connection_id: int, service_client: Client) -> None:
    """Delete a single connection by ID.

    Args:
        connection_id: ID of the connection
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting tag connection {connection_id}")

    service_client.table('REMINDER_TAG_CONNECTION') \
        .delete() \
        .eq('id', connection_id) \
        .execute()


def delete_by_reminder_and_tag(reminder_id: int, tag_id: int, service_client: Client) -> None:
    """Delete a specific reminder-tag connection.

    Args:
        reminder_id: ID of the reminder
        tag_id: ID of the tag
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting connection between reminder {reminder_id} and tag {tag_id}")

    service_client.table('REMINDER_TAG_CONNECTION') \
        .delete() \
        .eq('reminder_id', reminder_id) \
        .eq('tag_id', tag_id) \
        .execute()


def delete_all_by_reminder_id(reminder_id: int, service_client: Client) -> None:
    """Delete all tag connections for a reminder.

    Args:
        reminder_id: ID of the reminder
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting all tag connections for reminder {reminder_id}")

    service_client.table('REMINDER_TAG_CONNECTION') \
        .delete() \
        .eq('reminder_id', reminder_id) \
        .execute()


def delete_all_by_tag_id(tag_id: int, service_client: Client) -> None:
    """Delete all reminder connections for a tag.

    Args:
        tag_id: ID of the tag
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting all reminder connections for tag {tag_id}")

    service_client.table('REMINDER_TAG_CONNECTION') \
        .delete() \
        .eq('tag_id', tag_id) \
        .execute()
