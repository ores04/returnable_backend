import datetime

import pytz
from supabase import Client

REMINDER_TABLE_NAME="REMINDER"
REMINDER_TIME_TABLE_NAME="REMINDER_TIME"


class ReminderTime:
    def __init__(self, id: int, reminder_id: int, reminder_time: str, created_at: str):
        self.id = id
        self.reminder_id = reminder_id
        self.reminder_time = reminder_time
        self.created_at = created_at

class Reminder:
    def __init__(self, id: int | None, user_id: str | None, reminder_text: str | None, event_time: str | None, created_at: str | None, done: bool | None):
        self.id = id
        self.user_id = user_id
        self.reminder_text = reminder_text
        self.event_time = event_time
        self.reminder_times: list[ReminderTime] = []
        self.created_at = created_at
        self.done = done

    @classmethod
    def create_dummy_reminder(cls):
        return cls(None, None, None, None, None, None)



def get_all_reminders_after(timestamp_after: str, timestamp_before: str, service_client: Client) -> list[Reminder]:
    """This function returns all reminders after the given timestamp abd before the current time from the database."""
    response = service_client.table(REMINDER_TIME_TABLE_NAME).select("*, REMINDER(*)").gt("reminder_time", timestamp_after).lt("reminder_time", timestamp_before).execute()
    response.raise_when_api_error(response)
    print(response.data)

    reminders = sort_reminder_times_by_reminder(response.data)
    reminders = fill_reminder_details(reminders, service_client)

    return reminders


def sort_reminder_times_by_reminder(reminder_times: list[dict]) -> list[Reminder]:
    """ This function first parse the reminder times into ReminderTime objects and then groups them by their reminder id into Reminder objects."""
    reminders_dict = {}
    for rt in reminder_times:
        reminder_time_object = ReminderTime(rt["id"], rt["reminder_id"], rt["reminder_time"], rt["created_at"])
        reminder_id = reminder_time_object.reminder_id

        if reminder_id not in reminders_dict:
            dummy_reminder = Reminder.create_dummy_reminder()
            dummy_reminder.id = reminder_id
            dummy_reminder.reminder_times.append(reminder_time_object)

            reminders_dict[reminder_id] = dummy_reminder

        else:
            reminders_dict[reminder_id].reminder_times.append(reminder_time_object)

    return list(reminders_dict.values())

def fill_reminder_details(reminders: list[Reminder], service_client: Client) -> list[Reminder]:
    """ This function fills the details of the reminders from the database."""
    for reminder in reminders:
        response = service_client.table(REMINDER_TABLE_NAME).select("*").eq("id", reminder.id).execute()
        response.raise_when_api_error(response)
        if response.data and len(response.data) > 0:
            reminder_data = response.data[0]
            reminder.user_id = reminder_data["user_id"]
            reminder.reminder_text = reminder_data["reminder_text"]
            reminder.event_time = reminder_data["event_time"]
            reminder.created_at = reminder_data["created_at"]
            reminder.done = reminder_data["done"]
    return reminders




def add_reminder_with_service_client(service_client: Client, reminder_data: dict):
    """This function adds a new reminder to the database."""
    required_fields = ["user_id", "reminder_text", "reminder_time", "event_time"]

    for field in required_fields:
        if field not in reminder_data:
            raise ValueError(f"Missing required field: {field}")

    # ensure reminder time and event time have the correct timezone info
    local_tz = pytz.timezone("Europe/Berlin") # TODO use replace with your local timezone
    if isinstance(reminder_data.get("reminder_time"), str):
        reminder_data["reminder_time"] = datetime.datetime.fromisoformat(reminder_data["reminder_time"]).astimezone(local_tz).isoformat()
    if isinstance(reminder_data.get("event_time"), str):
        reminder_data["event_time"] = datetime.datetime.fromisoformat(reminder_data["event_time"]).astimezone(local_tz).isoformat()

    reminder_payload = {
        "user_id": reminder_data["user_id"],
        "reminder_text": reminder_data["reminder_text"],
        "event_time": reminder_data["event_time"]
    }

    response = service_client.table(REMINDER_TABLE_NAME).insert(reminder_payload).execute()
    response.raise_when_api_error(response)

    if not response.data or len(response.data) == 0:
        raise Exception("Failed to create reminder")

    reminder_id = response.data[0]["id"]
    reminder_time_payload = {
        "reminder_id": reminder_id,
        "reminder_time": reminder_data["reminder_time"]
    }

    response = service_client.table(REMINDER_TIME_TABLE_NAME).insert(reminder_time_payload).execute()
    response.raise_when_api_error(response)


    return response.data


def add_todo_with_service_client(service_client: Client, todo_data: dict):
    """This function adds a new todo to the database. A todo is a reminder without reminder_time."""
    required_fields = ["user_id", "todo_text"]

    for field in required_fields:
        if field not in todo_data:
            raise ValueError(f"Missing required field: {field}")

    # ensure event time has the correct timezone info if provided
    local_tz = pytz.timezone("Europe/Berlin")  # TODO use replace with your local timezone
    if todo_data.get("event_time") and isinstance(todo_data.get("event_time"), str):
        todo_data["event_time"] = datetime.datetime.fromisoformat(todo_data["event_time"]).astimezone(local_tz).isoformat()

    todo_payload = {
        "user_id": todo_data["user_id"],
        "reminder_text": todo_data["todo_text"],  # Store todo_text in reminder_text field
        "event_time": todo_data.get("event_time")  # Can be None for todos without a due date
    }

    # Insert into REMINDER table without adding to REMINDER_TIME table
    # A todo is distinguished by having no entries in REMINDER_TIME table
    response = service_client.table(REMINDER_TABLE_NAME).insert(todo_payload).execute()
    response.raise_when_api_error(response)

    if not response.data or len(response.data) == 0:
        raise Exception("Failed to create todo")

    return response.data[0]


# New functions for API endpoints

import logfire
from typing import List, Optional


def find_reminder_by_id(reminder_id: int, service_client: Client, include_times: bool = True, include_tags: bool = False) -> Optional[dict]:
    """Get a single reminder by ID with optional nested data.

    Args:
        reminder_id: ID of the reminder
        service_client: Supabase client instance
        include_times: Whether to include reminder_times
        include_tags: Whether to include tags via REMINDER_TAG_CONNECTION

    Returns:
        Reminder dictionary or None
    """
    logfire.debug(f"Finding reminder {reminder_id} (include_times={include_times}, include_tags={include_tags})")

    # Build select query
    select_parts = ['*']
    if include_times:
        select_parts.append('REMINDER_TIME(*)')
    if include_tags:
        select_parts.append('REMINDER_TAG_CONNECTION(REMINDER_TAG(*))')

    select_query = ', '.join(select_parts)

    response = service_client.table(REMINDER_TABLE_NAME) \
        .select(select_query) \
        .eq('id', reminder_id) \
        .execute()

    if not response.data or len(response.data) == 0:
        return None

    return response.data[0]


def find_reminders_by_id_list(reminder_ids: List[int], service_client: Client) -> List[dict]:
    """Get reminders with JOIN for reminder_times and tags in single query.

    This preserves the complex nested select from the frontend.

    Args:
        reminder_ids: List of reminder IDs
        service_client: Supabase client instance

    Returns:
        List of reminder dictionaries with nested times and tags
    """
    logfire.debug(f"Finding {len(reminder_ids)} reminders with nested times and tags")

    if not reminder_ids:
        return []

    # Preserve complex join: '*, REMINDER_TIME(*), REMINDER_TAG_CONNECTION(REMINDER_TAG(*))'
    response = service_client.table(REMINDER_TABLE_NAME) \
        .select('*, REMINDER_TIME(*), REMINDER_TAG_CONNECTION(REMINDER_TAG(*))') \
        .in_('id', reminder_ids) \
        .execute()

    return response.data


def find_newest_reminders(service_client: Client, limit: int = 10) -> List[dict]:
    """Get newest reminders ordered by created_at.

    Args:
        service_client: Supabase client instance
        limit: Maximum number of reminders to return

    Returns:
        List of reminder dictionaries
    """
    logfire.debug(f"Finding {limit} newest reminders")

    response = service_client.table(REMINDER_TABLE_NAME) \
        .select('*') \
        .order('created_at', desc=True) \
        .limit(limit) \
        .execute()

    return response.data


def find_user_reminders_after(user_id: str, after: datetime.datetime, limit: int, service_client: Client) -> List[dict]:
    """Get user reminders after a specific date.

    Args:
        user_id: UUID of the user
        after: Get reminders after this datetime
        limit: Maximum number of reminders
        service_client: Supabase client instance

    Returns:
        List of reminder dictionaries
    """
    logfire.debug(f"Finding reminders for user {user_id} after {after}")

    response = service_client.table(REMINDER_TABLE_NAME) \
        .select('*') \
        .eq('user_id', user_id) \
        .gt('event_time', after.isoformat()) \
        .limit(limit) \
        .execute()

    return response.data


def find_user_reminder_ids(user_id: str, after: Optional[datetime.datetime], limit: int, include_overdue: bool, service_client: Client) -> List[int]:
    """Get reminder IDs with OR query for overdue reminders.

    This preserves the OR query pattern: event_time > after OR done = false

    Args:
        user_id: UUID of the user
        after: Filter by event_time (optional)
        limit: Maximum number of IDs
        include_overdue: Include overdue reminders (done=false) regardless of date
        service_client: Supabase client instance

    Returns:
        List of reminder IDs
    """
    logfire.debug(f"Finding reminder IDs for user {user_id} (after={after}, include_overdue={include_overdue})")

    query = service_client.table(REMINDER_TABLE_NAME) \
        .select('id') \
        .eq('user_id', user_id)

    # Apply OR query if needed
    if after and include_overdue:
        after_str = after.isoformat()
        query = query.or_(f'event_time.gt.{after_str},done.eq.false')
    elif after:
        query = query.gt('event_time', after.isoformat())

    if limit:
        query = query.limit(limit)

    response = query.execute()

    return [item['id'] for item in response.data]


def create_reminder(reminder_data: dict, service_client: Client) -> int:
    """Create a new reminder.

    Args:
        reminder_data: Dictionary with reminder fields
        service_client: Supabase client instance

    Returns:
        ID of created reminder
    """
    logfire.info(f"Creating reminder for user {reminder_data.get('user_id')}")

    response = service_client.table(REMINDER_TABLE_NAME).insert(reminder_data).execute()

    if not response.data or len(response.data) == 0:
        raise ValueError("Failed to create reminder")

    return response.data[0]['id']


def update_reminder(reminder_id: int, reminder_data: dict, service_client: Client, replace_times: bool = True) -> dict:
    """Update a reminder and optionally replace reminder_times.

    Args:
        reminder_id: ID of the reminder
        reminder_data: Dictionary with fields to update
        service_client: Supabase client instance
        replace_times: Whether to replace reminder_times (if provided in data)

    Returns:
        Updated reminder dictionary
    """
    logfire.info(f"Updating reminder {reminder_id} (replace_times={replace_times})")

    # Extract reminder_times if present
    reminder_times = reminder_data.pop('reminder_times', None)

    # Update main reminder record
    response = service_client.table(REMINDER_TABLE_NAME) \
        .update(reminder_data) \
        .eq('id', reminder_id) \
        .execute()

    if not response.data or len(response.data) == 0:
        raise ValueError(f"Reminder {reminder_id} not found")

    # Replace reminder times if requested
    if replace_times and reminder_times is not None:
        replace_reminder_times(reminder_id, reminder_times, service_client)

    return response.data[0]


def toggle_reminder_done(reminder_id: int, done: bool, service_client: Client) -> dict:
    """Toggle the done status of a reminder.

    Args:
        reminder_id: ID of the reminder
        done: New done status
        service_client: Supabase client instance

    Returns:
        Updated reminder dictionary
    """
    logfire.info(f"Toggling reminder {reminder_id} done={done}")

    response = service_client.table(REMINDER_TABLE_NAME) \
        .update({'done': done}) \
        .eq('id', reminder_id) \
        .execute()

    if not response.data or len(response.data) == 0:
        raise ValueError(f"Reminder {reminder_id} not found")

    return response.data[0]


def delete_reminder(reminder_id: int, service_client: Client) -> None:
    """Delete a reminder and associated reminder_times (cascade).

    Args:
        reminder_id: ID of the reminder
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting reminder {reminder_id}")

    # Delete reminder (should cascade to REMINDER_TIME)
    service_client.table(REMINDER_TABLE_NAME) \
        .delete() \
        .eq('id', reminder_id) \
        .execute()


def replace_reminder_times(reminder_id: int, reminder_times: List[dict], service_client: Client) -> None:
    """Delete all existing reminder times and insert new ones.

    This preserves the delete-all + insert pattern from the frontend.

    Args:
        reminder_id: ID of the reminder
        reminder_times: List of reminder time dictionaries
        service_client: Supabase client instance
    """
    logfire.debug(f"Replacing reminder times for reminder {reminder_id}")

    # Step 1: Delete all existing times
    service_client.table(REMINDER_TIME_TABLE_NAME) \
        .delete() \
        .eq('reminder_id', reminder_id) \
        .execute()

    # Step 2: Insert new times if any
    if reminder_times:
        # Ensure reminder_id is set
        for rt in reminder_times:
            rt['reminder_id'] = reminder_id

        service_client.table(REMINDER_TIME_TABLE_NAME).insert(reminder_times).execute()

