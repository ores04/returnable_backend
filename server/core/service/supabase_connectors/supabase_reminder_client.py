import datetime

import pytz
from supabase import Client

REMINDER_TABLE_NAME="REMINDER"
REMINDER_TIME_TABLE_NAME="REMINDER_TIME"


def get_all_reminders_after(timestamp_after: str, timestamp_before: str, service_client: Client) -> list[dict]:
    """This function returns all reminders after the given timestamp abd before the current time from the database."""
    response = service_client.table(REMINDER_TIME_TABLE_NAME).select("*, REMINDER(*)").gt("reminder_time", timestamp_after).lt("reminder_time", timestamp_before).execute()
    response.raise_when_api_error(response)
    print(response.data)
    return response.data if response.data and len(response.data) > 0 else []


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