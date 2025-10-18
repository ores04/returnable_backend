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