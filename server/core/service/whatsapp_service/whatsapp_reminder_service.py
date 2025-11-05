import datetime
import os
from typing import Optional

import logfire
import pytz
import asyncio

from dotenv import load_dotenv

from server.core.ai.agents.exract_reminder_agent import ReminderModel, master_extract_reminder_agent, ReminderDeps, \
    reminder_usage_limit
from server.core.service.supabase_connectors.supabase_client import get_uuid_from_phone_number, \
    get_supabase_service_role_client, get_phone_number_from_uuid
from server.core.service.supabase_connectors.supabase_reminder_client import add_reminder_with_service_client, \
    get_all_reminders_after
from server.core.service.supabase_connectors.supabase_tag_service import ReminderTag, \
    get_all_uuids_with_accsess_to_reminder
from server.core.service.whatsapp_service.whatsapp_utils import send_message


WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

def reminder_service(text: str, phone_number: str, uuid=None, possible_tags:list[ReminderTag] = None) -> ReminderModel:
    if uuid is None:
        uuid = get_uuid_from_phone_number(phone_number)
    if uuid is None:
        raise ValueError("User not found")
    send_message(phone_number, "Erstlle deine Erinnerung...", WHATSAPP_PHONE_ID)

    # add timezone info
    user_tz = get_user_timezone(uuid)
    reminderModel = asyncio.run(extract_reminders_from_text(text, user_tz, possible_tags=possible_tags))

    # if either the event time or reminder time is missing then make them the same
    if reminderModel.event_time is None and len(reminderModel.reminder_time) >0:
        reminderModel.event_time = reminderModel.reminder_time[0]
    if (reminderModel.reminder_time is None or len(reminderModel.reminder_time) == 0) and reminderModel.event_time is not None:
        reminderModel.reminder_time = [reminderModel.event_time]
    elif reminderModel.event_time is None and reminderModel.reminder_time is None:
        raise ValueError("Could not extract reminder time or event time from text")

    """ prob not needed as already done in the agent
    reminderModel.event_time = add_tz_info_to_datetime(reminderModel.event_time, user_tz)
    for i in range(len(reminderModel.reminder_time)):
        reminderModel.reminder_time[i] = add_tz_info_to_datetime(reminderModel.reminder_time[i], user_tz)
"""
    dict = {
        "reminder_text": reminderModel.reminder_text,
        "reminder_time": reminderModel.reminder_time,
        "event_time": reminderModel.event_time,
        "user_id": uuid
    }


    client = get_supabase_service_role_client()
    resp = add_reminder_with_service_client(client, dict)
    if not resp:
        raise ValueError("Could not add reminder to database")

    # get the tag ids to add
    if reminderModel.reminder_tags is not None and len(reminderModel.reminder_tags) >0:
        tag_ids = []
        for tag in possible_tags:
            if tag.name in reminderModel.reminder_tags:
                tag_ids.append(tag.id)
        # now add the tags to the reminder
        for tag_id in tag_ids:
            client.table("REMINDER_TAG_CONNECTION").insert({
                "reminder_id": resp.id,
                "tag_id": tag_id
            }).execute()

        logfire.info(f"Added tags {tag_ids} to reminder {resp.id}")

    return reminderModel

def add_tz_info_to_datetime(dt: str, tz_str: str) -> str:
    """ Adds timezone info to a datetime object."""
    dt = datetime.datetime.fromisoformat(dt)
    local_tz = pytz.timezone(tz_str)
    if dt.tzinfo is None:
        dt = local_tz.localize(dt)
    else:
        dt = dt.astimezone(local_tz)
    return dt.isoformat()



async def extract_reminders_from_text(text: str, tz: str, possible_tags: list[ReminderTag] = None) -> ReminderModel:
    """
    Extracts reminders from the given text.

    Args:
        text (str): The text to extract reminders from.
        tz (str): The timezone to use for date parsing.
        possible_tags (list[str], optional): A list of possible tags for the reminder. Defaults to None.

    Returns:
        list[str]: A list of extracted reminders.
    """
    tag_str = [tag.name for tag in possible_tags] if possible_tags is not None else []
    result = await master_extract_reminder_agent.run(text,deps=ReminderDeps(tzinfo=tz, possible_tags=tag_str),
                                                     usage_limits=reminder_usage_limit)
    return result.output


def remind_users(last_timestamp: datetime.datetime, current_timestamp: datetime.datetime):
    """ Checks for reminders that are due and sends them via WhatsApp."""
    logfire.info(f"Checking for due reminders... from {last_timestamp} to {current_timestamp}")
    client = get_supabase_service_role_client()
    due_reminders = get_all_reminders_after(last_timestamp.isoformat(), current_timestamp.isoformat(), client)
    logfire.info(f"Found {len(due_reminders)} due reminders.")
    for reminder in due_reminders:
        # if the reminder is done then skip it
        if reminder.done:
            continue

        # find possible shared users and send them the reminder as well
        uuids_with_access = get_all_uuids_with_accsess_to_reminder(reminder.id, client)
        for uuid in uuids_with_access:
            phone_number = get_phone_number_from_uuid(uuid)
            if phone_number is None:
                logfire.error(f"Could not find phone number for user {uuid}")
                continue
            send_message(phone_number,reminder.reminder_text ,phone_number_id="836828019507106")

        phone_number = get_phone_number_from_uuid(reminder.user_id)
        if phone_number is None:
            logfire.error(f"Could not find phone number for user {reminder.user_id}")
            continue
        send_message(phone_number,reminder.reminder_text ,phone_number_id="836828019507106")



if __name__ == "__main__":
    load_dotenv()
    LOGFIRE_TOKEN = os.environ.get("LOGFIRE_TOKEN")
    logfire.configure(
        token=LOGFIRE_TOKEN,
    )
    remind_users(datetime.datetime.now(tz=datetime.timezone.utc), datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60))