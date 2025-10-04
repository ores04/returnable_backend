import datetime
import os

import logfire
import asyncio

from server.core.ai.agents.exract_reminder_agent import ReminderModel, master_extract_reminder_agent
from server.core.service.supabase_connectors.supabase_client import get_uuid_from_phone_number, \
    get_supabase_service_role_client, get_phone_number_from_uuid
from server.core.service.supabase_connectors.supabase_reminder_client import add_reminder_with_service_client, \
    get_all_reminders_after
from server.core.service.whatsapp_service.whatsapp_utils import send_message


WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

def reminder_service(text: str, phone_number: str, uuid=None) -> ReminderModel:
    if uuid is None:
        uuid = get_uuid_from_phone_number(phone_number)
    if uuid is None:
        raise ValueError("User not found")
    send_message(phone_number, "Erstlle deine Erinnerung...", WHATSAPP_PHONE_ID)
    reminderModel = asyncio.run(extract_reminders_from_text(text))

    # if either the event time or reminder time is missing then make them the same
    if reminderModel.event_time is None and reminderModel.reminder_time is not None:
        reminderModel.event_time = reminderModel.reminder_time
    elif reminderModel.reminder_time is None and reminderModel.event_time is not None:
        reminderModel.reminder_time = reminderModel.event_time
    elif reminderModel.event_time is None and reminderModel.reminder_time is None:
        raise ValueError("Could not extract reminder time or event time from text")


    dict = {
        "reminder_text": reminderModel.reminder_text,
        "reminder_time": reminderModel.reminder_time,
        "event_time": reminderModel.event_time,
        "user_id": uuid
    }

    client = get_supabase_service_role_client()
    resp = add_reminder_with_service_client(client, dict)


    return reminderModel



async def extract_reminders_from_text(text: str) -> ReminderModel:
    """
    Extracts reminders from the given text.

    Args:
        text (str): The text to extract reminders from.

    Returns:
        list[str]: A list of extracted reminders.
    """
    result = await master_extract_reminder_agent.run(text)
    return result.output


def remind_users(last_timestamp: datetime.datetime, current_timestamp: datetime.datetime):
    """ Checks for reminders that are due and sends them via WhatsApp."""
    logfire.info(f"Checking for due reminders... from {last_timestamp} to {current_timestamp}")
    client = get_supabase_service_role_client()
    due_reminders = get_all_reminders_after(last_timestamp.isoformat(), current_timestamp.isoformat(), client)
    logfire.info(f"Found {len(due_reminders)} due reminders.")
    for reminder in due_reminders:
        phone_number = get_phone_number_from_uuid(reminder["user_id"])
        if phone_number is None:
            logfire.error(f"Could not find phone number for user {reminder['user_id']}")
            continue
        send_message(phone_number,reminder["reminder_text"] ,phone_number_id="836828019507106")



