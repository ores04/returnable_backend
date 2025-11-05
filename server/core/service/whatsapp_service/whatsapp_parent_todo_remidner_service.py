import datetime
from functools import reduce

import pytz
from openai import BaseModel

from server.core.ai.ai_clients.openai_client import OpenAIClient
from server.core.service.supabase_connectors.supabase_tag_service import ReminderTag
from server.core.service.whatsapp_service.whatsapp_reminder_service import reminder_service
from server.core.service.whatsapp_service.whatsapp_todo_service import todo_service
from server.core.service.whatsapp_service.whatsapp_utils import send_message


class ExtractionResult(BaseModel):
    candidates:list[tuple[str,str]]  = []

def get_user_timezone(uuid: str) -> str:
    """ For now dummy to always return Europe/Berlin"""
    return "Europe/Berlin"

def handle_todo_or_reminder_extraction(text: str, phone_number: str,to,phone_number_id, uuid=None, possible_tags: list[ReminderTag] = None, ) -> None:
    """This function processes the extracted text from a message to determine if it contains a to-do item or a reminder.

    Args:
        text (str): The text extracted from the user's message.

    """

    ai_agent = OpenAIClient()

    PROMPT = """
You are an extractor whose only job is to parse a single user message and return a strict JSON array of candidate pairs.
Each candidate must be a two-element array: [type, text]
- type MUST be exactly either the string "reminder" or the string "todo".
- text MUST be a short natural-language phrase that represents the reminder or the todo.

Rules:
1) A candidate is classified as "reminder" ONLY if the message contains a clear time expression indicating when the user wants to be reminded. Time expressions include absolute dates/times (e.g. "2025-11-06 09:00", "2025-11-06T09:00Z"), relative expressions (e.g. "tomorrow at 9am", "in 2 hours", "next Monday at 15:00"), or calendar-like words with times (e.g. "June 3rd at 18:00"). If such a time expression exists for an item, include it in the text so downstream parsing can find it.
2) If the item does not contain any time information, classify it as "todo". A "todo" represents an actionable task without an associated reminder time.
3) If the message contains multiple items, return multiple candidate arrays in the JSON output, preserving their natural order if possible.
4) If the message contains no actionable todo or reminder, return an empty JSON array: []

Formatting requirements and examples (the output must follow these exactly):
- Valid output example with two items:
  [["reminder", "Pay rent tomorrow at 9am"], ["todo", "Buy milk"]]
- Valid output example with a single todo:
  [["todo", "Clean the kitchen"]]
- Valid output for no actionable items:
  []

Do NOT invent times for items that have none. Do NOT output any fields other than the two-element arrays described.

"""

    # pass an instance of the BaseModel-derived class to match the client's expected type
    response = ai_agent.request_text_model(PROMPT, text, model="gpt-5-mini", response_model=ExtractionResult())

    for candidate in response.candidates:
        item_type, item_text = candidate
        if item_type == "todo":
            todo = todo_service(item_text, phone_number, uuid, possible_tags=possible_tags)
            tz_str = get_user_timezone(uuid)
            local_tz = pytz.timezone(tz_str)

            # Create confirmation message with to_do text
            if todo.event_time:
                pretty_event_time = datetime.datetime.fromisoformat(todo.event_time).astimezone(
                    local_tz).strftime("%d.%m.%Y %H:%M")
                message = f"Todo erstellt: \"{todo.todo_text}\" (fällig am {pretty_event_time})"
            else:
                message = f"Todo erstellt: \"{todo.todo_text}\""

            send_message(to, message, phone_number_id)
        elif item_type == "reminder":
            reminder = reminder_service(item_text, phone_number, uuid, possible_tags=possible_tags)
            tz_str = get_user_timezone(uuid)
            local_tz = pytz.timezone(tz_str)
            pretty_reminder_time_list = [datetime.datetime.fromisoformat(reminder_time).astimezone(
                local_tz).strftime("%d.%m.%Y %H:%M") for reminder_time in
                                         reminder.reminder_time]
            message = f"Du wirst am {reduce(lambda x, y: str(x) + "," + str(y), pretty_reminder_time_list, "") if len(pretty_reminder_time_list) > 1 else pretty_reminder_time_list[0]} erinnert. "
            send_message(to, message, phone_number_id)