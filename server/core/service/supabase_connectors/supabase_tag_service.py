
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



if __name__ == "__main__":
    # test find_all_uuids_with_accsess_to_reminder
    from server.core.service.supabase_connectors.supabase_client import get_supabase_service_role_client
    client = get_supabase_service_role_client()
    reminder_id = 79
    uuids = get_all_uuids_with_accsess_to_reminder(reminder_id, client)
    print(uuids)
