import asyncio
import datetime
from functools import reduce

import logfire
import pytz
from pydantic import BaseModel

from server.core.ai.ai_clients.openai_client import OpenAIClient
from server.core.service.supabase_connectors.supabase_tag_service import ReminderTag
from server.core.service.whatsapp_service.whatsapp_reminder_service import reminder_service
from server.core.service.whatsapp_service.whatsapp_todo_service import todo_service
from server.core.service.whatsapp_service.whatsapp_utils import send_message


class Candidate(BaseModel):
    type: str  # "todo" or "reminder"
    text: str  # The text of the todo or reminder

class ExtractionResult(BaseModel):
    candidates: list[Candidate] = []

def get_user_timezone(uuid: str) -> str:
    """ For now dummy to always return Europe/Berlin"""
    return "Europe/Berlin"

async def process_candidate(candidate: Candidate, phone_number: str | None, uuid: str, possible_tags: list[ReminderTag], local_tz):
    """Process a single candidate and return the created item and message"""
    item_type = candidate.type
    item_text = candidate.text

    if item_type == "todo":
        todo = await todo_service(item_text, phone_number, uuid, possible_tags=possible_tags)

        if todo.event_time:
            pretty_event_time = datetime.datetime.fromisoformat(todo.event_time).astimezone(
                local_tz).strftime("%d.%m.%Y %H:%M")
            message = f"Todo erstellt: \"{todo.todo_text}\" (fällig am {pretty_event_time})"
        else:
            message = f"Todo erstellt: \"{todo.todo_text}\""

        created_item = {
            "type": "todo",
            "todo_text": todo.todo_text,
            "event_time": todo.event_time,
            "tags": todo.todo_tags
        }
        return created_item, message

    elif item_type == "reminder":
        reminder = await reminder_service(item_text, phone_number, uuid, possible_tags=possible_tags)

        pretty_reminder_time_list = [
            datetime.datetime.fromisoformat(reminder_time).astimezone(local_tz).strftime("%d.%m.%Y %H:%M")
            for reminder_time in reminder.reminder_time
        ]
        message = f"Du wirst am {reduce(lambda x, y: str(x) + ',' + str(y), pretty_reminder_time_list, '') if len(pretty_reminder_time_list) > 1 else pretty_reminder_time_list[0]} erinnert. "

        created_item = {
            "type": "reminder",
            "reminder_text": reminder.reminder_text,
            "event_time": reminder.event_time,
            "reminder_time": reminder.reminder_time,
            "tags": reminder.reminder_tags
        }
        return created_item, message

    return None, None

async def extract_and_create_items(text: str, phone_number: str | None, uuid=None, possible_tags: list[ReminderTag] = None):
    """Extracts todos/reminders from text and creates them without sending WhatsApp messages.

    Args:
        text: The text to extract todos/reminders from
        phone_number: User's phone number
        uuid: Optional user UUID (will be looked up from phone_number if not provided)
        possible_tags: Optional list of tags that can be assigned

    Returns:
        dict: A dictionary containing:
            - 'items': list of created items (todos and reminders)
            - 'messages': list of confirmation messages for each item
    """
    ai_agent = OpenAIClient()

    PROMPT = """
You are an extractor whose only job is to parse a single user message and return a list of candidates.
Each candidate must have two fields: type and text
- type MUST be exactly either the string "reminder" or the string "todo".
- text MUST be a short natural-language phrase that represents the reminder or the todo.

Rules:
1) A candidate is classified as "reminder" ONLY if the message contains a clear time expression indicating when the user wants to be reminded. Time expressions include absolute dates/times (e.g. "2025-11-06 09:00", "2025-11-06T09:00Z"), relative expressions (e.g. "tomorrow at 9am", "in 2 hours", "next Monday at 15:00"), or calendar-like words with times (e.g. "June 3rd at 18:00"). If such a time expression exists for an item, include it in the text so downstream parsing can find it.
2) If the item does not contain any time information, classify it as "todo". A "todo" represents an actionable task without an associated reminder time.
3) If the message contains multiple items, return multiple candidates in the JSON output, preserving their natural order if possible.
4) If the message contains no actionable todo or reminder, return an empty candidates array.

Example output format:
{
  "candidates": [
    {"type": "reminder", "text": "Pay rent tomorrow at 9am"},
    {"type": "todo", "text": "Buy milk"}
  ]
}

Do NOT invent times for items that have none.

"""
    logfire.info(f"Extracting todos/reminders from text: {text}")
    response = ai_agent.request_text_model(PROMPT, text, model="gpt-5-nano", response_model=ExtractionResult)
    logfire.info(response)

    tz_str = get_user_timezone(uuid)
    local_tz = pytz.timezone(tz_str)

    # Process all candidates in parallel
    tasks = [
        process_candidate(candidate, phone_number, uuid, possible_tags, local_tz)
        for candidate in response.candidates
    ]

    results = await asyncio.gather(*tasks)

    created_items = []
    messages = []
    for created_item, message in results:
        if created_item and message:
            created_items.append(created_item)
            messages.append(message)

    return {
        "items": created_items,
        "messages": messages
    }

async def handle_todo_or_reminder_extraction(text: str, phone_number: str,to,phone_number_id, uuid=None, possible_tags: list[ReminderTag] = None, ) -> None:
    """This function processes the extracted text from a message to determine if it contains a to-do item or a reminder.
    This is the WhatsApp-specific version that sends messages via WhatsApp.

    Args:
        text (str): The text extracted from the user's message.
        phone_number (str): User's phone number
        to (str): WhatsApp ID to send response to
        phone_number_id (str): WhatsApp Business phone number ID
        uuid (str, optional): User UUID
        possible_tags (list[ReminderTag], optional): List of possible tags

    """
    # Use the core extraction method
    result = await extract_and_create_items(text, phone_number, uuid, possible_tags)

    # Send WhatsApp messages for each created item
    for message in result["messages"]:
        send_message(to, message, phone_number_id)



if __name__ == "__main__":
    # Example usage
    text = "Remind me to call mom tomorrow at 5pm and buy groceries."
    phone_number = "+1234567890"
    to = phone_number
    phone_number_id = "your_whatsapp_business_phone_number_id"
    uuid = "8912d63f-f27d-497c-aaa1-4210089ae9a5"

    resp = extract_and_create_items(text, None, uuid, possible_tags=[])
    print(resp)