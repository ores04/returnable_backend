
from supabase import Client
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


# Table name constants
REMINDER_TAG_TABLE_NAME = "REMINDER_TAG"
REMINDER_TAG_SHARED_TABLE_NAME = "REMINDER_TAG_SHARED"
REMINDER_TAG_CONNECTION_TABLE_NAME = "REMINDER_TAG_CONNECTION"


class ReminderTag(BaseModel):
    """Pydantic model for REMINDER_TAG table."""
    id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    name: Optional[str] = None
    color: Optional[str] = None
    user_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class ReminderTagShared(BaseModel):
    """Pydantic model for REMINDER_TAG_SHARED table."""
    uuid: UUID
    created_at: datetime = Field(default_factory=datetime.now)
    tag_id: Optional[int] = None
    user_shared_with: Optional[UUID] = None
    user_shares: Optional[UUID] = None
    share_accepted: Optional[bool] = False

    class Config:
        from_attributes = True


class ReminderTagConnection(BaseModel):
    """Pydantic model for REMINDER_TAG_CONNECTION table."""
    id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    reminder_id: int
    tag_id: int

    class Config:
        from_attributes = True


def get_all_user_owned_tags(uuid: str, service_client: Client) -> list[ReminderTag]:
    """ This function returns all tags owned by the user with the given uuid."""
    response = service_client.table(REMINDER_TAG_TABLE_NAME).select("*").eq("user_id", uuid).execute()
    response.raise_when_api_error(response)

    tags = [ReminderTag(**tag) for tag in response.data]
    return tags


def get_all_shared_with_user_tags(uuid: str, service_client: Client) -> list[ReminderTag]:
    """ This function returns all tags shared with the user with the given uuid."""
    response = service_client.table(REMINDER_TAG_SHARED_TABLE_NAME).select("tag_id").eq("user_shared_with", uuid).eq("share_accepted", True).execute()
    response.raise_when_api_error(response)

    tag_ids = [ReminderTagShared(**tag) for tag in response.data]
    tags = []
    for tag_id in tag_ids:
        tag_response = service_client.table(REMINDER_TAG_TABLE_NAME).select("*").eq("id", tag_id.tag_id).execute()
        tag_response.raise_when_api_error(tag_response)
        if tag_response.data:
            tags.append(ReminderTag(**tag_response.data[0]))
    return tags

def get_all_uuids_with_accsess_to_reminder(reminder_id: int, service_client: Client) -> list[UUID]:
    """ This function returns all uuids that have access to the reminder with the given id."""
    response = service_client.table(REMINDER_TAG_CONNECTION_TABLE_NAME).select("*").eq("reminder_id", reminder_id).execute()
    response.raise_when_api_error(response)

    tag_ids = [ReminderTagConnection(**tag) for tag in response.data]
    uuids = set()
    for tag_id in tag_ids:
        shared_response = service_client.table(REMINDER_TAG_SHARED_TABLE_NAME).select("*").eq("tag_id", tag_id.tag_id).eq("share_accepted", True).execute()
        shared_response.raise_when_api_error(shared_response)
        for shared in shared_response.data:
            shared_tag = ReminderTagShared(**shared)
            uuids.add(shared_tag.user_shared_with)
    return list(uuids)



def get_all_user_accessible_tags(uuid: str, service_client: Client) -> list[ReminderTag]:
    """ This function returns all tags accessible by the user with the given uuid."""
    owned_tags = get_all_user_owned_tags(uuid, service_client)
    shared_tags = get_all_shared_with_user_tags(uuid, service_client)
    all_tags = owned_tags + shared_tags
    return all_tags

def add_tag_to_reminder(tag_id: int, reminder_id: int, service_client: Client) -> ReminderTagConnection:
    """ This function adds a tag to a reminder."""
    data = {
        "tag_id": tag_id,
        "reminder_id": reminder_id
    }
    response = service_client.table(REMINDER_TAG_CONNECTION_TABLE_NAME).insert(data).execute()
    response.raise_when_api_error(response)

    if response.data:
        return ReminderTagConnection(**response.data[0])
    raise Exception("Failed to create tag connection")


# New functions for API endpoints

import logfire
from typing import List, Dict


def find_tags_accessible_to_user(user_id: str, service_client: Client) -> List[dict]:
    """Get both owned and shared tags with deduplication.

    This combines owned tags and accepted shared tags.

    Args:
        user_id: UUID of the user
        service_client: Supabase client instance

    Returns:
        List of tag dictionaries (deduplicated)
    """
    logfire.debug(f"Finding accessible tags for user {user_id}")

    # Get owned tags
    owned_response = service_client.table(REMINDER_TAG_TABLE_NAME) \
        .select('*') \
        .eq('user_id', user_id) \
        .execute()

    owned_tags = owned_response.data

    # Get shared tags
    shared_response = service_client.table(REMINDER_TAG_SHARED_TABLE_NAME) \
        .select('tag_id') \
        .eq('user_shared_with', user_id) \
        .eq('share_accepted', True) \
        .execute()

    shared_tag_ids = [item['tag_id'] for item in shared_response.data]

    # Fetch the actual tag data for shared tags
    shared_tags = []
    if shared_tag_ids:
        shared_tags_response = service_client.table(REMINDER_TAG_TABLE_NAME) \
            .select('*') \
            .in_('id', shared_tag_ids) \
            .execute()
        shared_tags = shared_tags_response.data

    # Combine and deduplicate by ID
    all_tags = owned_tags + shared_tags
    seen_ids = set()
    deduplicated_tags = []
    for tag in all_tags:
        if tag['id'] not in seen_ids:
            seen_ids.add(tag['id'])
            deduplicated_tags.append(tag)

    return deduplicated_tags


def find_tags_by_reminder_id_list(reminder_ids: List[int], service_client: Client) -> Dict[int, List[dict]]:
    """Get tags for multiple reminders efficiently.

    Returns a map of reminder_id -> [tags]

    Args:
        reminder_ids: List of reminder IDs
        service_client: Supabase client instance

    Returns:
        Dictionary mapping reminder_id to list of tag dictionaries
    """
    logfire.debug(f"Finding tags for {len(reminder_ids)} reminders")

    if not reminder_ids:
        return {}

    # Step 1: Get all connections for these reminders
    connections_response = service_client.table(REMINDER_TAG_CONNECTION_TABLE_NAME) \
        .select('reminder_id, tag_id') \
        .in_('reminder_id', reminder_ids) \
        .execute()

    connections = connections_response.data

    # Step 2: Get all unique tag IDs
    tag_ids = list(set(conn['tag_id'] for conn in connections))

    if not tag_ids:
        return {rid: [] for rid in reminder_ids}

    # Step 3: Fetch all tags
    tags_response = service_client.table(REMINDER_TAG_TABLE_NAME) \
        .select('*') \
        .in_('id', tag_ids) \
        .execute()

    tags_by_id = {tag['id']: tag for tag in tags_response.data}

    # Step 4: Build the map
    result = {rid: [] for rid in reminder_ids}
    for conn in connections:
        reminder_id = conn['reminder_id']
        tag_id = conn['tag_id']
        if tag_id in tags_by_id:
            result[reminder_id].append(tags_by_id[tag_id])

    return result


def create_tag(tag_data: dict, service_client: Client) -> int:
    """Create a new tag.

    Args:
        tag_data: Dictionary with tag fields (name, color, user_id)
        service_client: Supabase client instance

    Returns:
        ID of created tag
    """
    logfire.info(f"Creating tag for user {tag_data.get('user_id')}")

    response = service_client.table(REMINDER_TAG_TABLE_NAME).insert(tag_data).execute()

    if not response.data or len(response.data) == 0:
        raise ValueError("Failed to create tag")

    return response.data[0]['id']


def find_tag_by_id(tag_id: int, service_client: Client) -> Optional[dict]:
    """Get a tag by ID.

    Args:
        tag_id: ID of the tag
        service_client: Supabase client instance

    Returns:
        Tag dictionary or None
    """
    logfire.debug(f"Finding tag {tag_id}")

    response = service_client.table(REMINDER_TAG_TABLE_NAME) \
        .select('*') \
        .eq('id', tag_id) \
        .execute()

    if not response.data or len(response.data) == 0:
        return None

    return response.data[0]


def find_tags_owned_by_user(user_id: str, service_client: Client) -> List[dict]:
    """Get tags owned by a user.

    Args:
        user_id: UUID of the user
        service_client: Supabase client instance

    Returns:
        List of tag dictionaries
    """
    logfire.debug(f"Finding tags owned by user {user_id}")

    response = service_client.table(REMINDER_TAG_TABLE_NAME) \
        .select('*') \
        .eq('user_id', user_id) \
        .execute()

    return response.data


def update_tag(tag_id: int, tag_data: dict, service_client: Client) -> dict:
    """Update a tag.

    Args:
        tag_id: ID of the tag
        tag_data: Dictionary with fields to update
        service_client: Supabase client instance

    Returns:
        Updated tag dictionary
    """
    logfire.info(f"Updating tag {tag_id}")

    response = service_client.table(REMINDER_TAG_TABLE_NAME) \
        .update(tag_data) \
        .eq('id', tag_id) \
        .execute()

    if not response.data or len(response.data) == 0:
        raise ValueError(f"Tag {tag_id} not found")

    return response.data[0]


def delete_tag(tag_id: int, service_client: Client) -> None:
    """Delete a tag.

    Args:
        tag_id: ID of the tag
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting tag {tag_id}")

    service_client.table(REMINDER_TAG_TABLE_NAME) \
        .delete() \
        .eq('id', tag_id) \
        .execute()



if __name__ == "__main__":
    # test find_all_uuids_with_accsess_to_reminder
    from server.core.service.supabase_connectors.supabase_client import get_supabase_service_role_client
    client = get_supabase_service_role_client()
    reminder_id = 79
    uuids = get_all_uuids_with_accsess_to_reminder(reminder_id, client)
    print(uuids)
