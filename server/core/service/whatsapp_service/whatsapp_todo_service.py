import os

import logfire
from dotenv import load_dotenv

from server.core.ai.agents.extract_todo_agent import TodoModel, master_extract_todo_agent, TodoDeps, \
    todo_usage_limit
from server.core.service.supabase_connectors.supabase_client import get_uuid_from_phone_number, \
    get_supabase_service_role_client
from server.core.service.supabase_connectors.supabase_reminder_client import add_todo_with_service_client
from server.core.service.supabase_connectors.supabase_tag_service import ReminderTag
from server.core.service.whatsapp_service.whatsapp_utils import send_message


WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

async def todo_service(text: str, phone_number: str|None, uuid=None, possible_tags: list[ReminderTag] = None) -> TodoModel:
    if uuid is None:
        uuid = get_uuid_from_phone_number(phone_number)
    if uuid is None:
        raise ValueError("User not found")
    if phone_number is not None:
        send_message(phone_number, "Erstelle dein Todo...", WHATSAPP_PHONE_ID)

    # add timezone info
    user_tz = get_user_timezone(uuid)
    todoModel = await extract_todo_from_text(text, user_tz, possible_tags=possible_tags)

    # Prepare the dictionary for database insertion
    dict_data = {
        "todo_text": todoModel.todo_text,
        "event_time": todoModel.event_time,
        "user_id": uuid
    }

    client = get_supabase_service_role_client()
    resp = add_todo_with_service_client(client, dict_data)
    if not resp:
        raise ValueError("Could not add todo to database")

    # get the tag ids to add
    if todoModel.todo_tags is not None and len(todoModel.todo_tags) > 0 and possible_tags is not None:
        tag_ids = []
        for tag in possible_tags:
            if tag.name in todoModel.todo_tags:
                tag_ids.append(tag.id)
        # now add the tags to the to_do (stored as reminder in DB)
        for tag_id in tag_ids:
            client.table("REMINDER_TAG_CONNECTION").insert({
                "reminder_id": resp.id,
                "tag_id": tag_id
            }).execute()

        logfire.info(f"Added tags {tag_ids} to todo {resp.id}")

    return todoModel

def get_user_timezone(uuid: str) -> str:
    """ For now dummy to always return Europe/Berlin"""
    return "Europe/Berlin"

async def extract_todo_from_text(text: str, tz: str, possible_tags: list[ReminderTag] = None) -> TodoModel:
    """
    Extracts a to_do from the given text.

    Args:
        text (str): The text to extract the to_do from.
        tz (str): The timezone to use for date parsing.
        possible_tags (list[str], optional): A list of possible tags for the to_do. Defaults to None.

    Returns:
        TodoModel: The extracted to_do.
    """
    tag_str = [tag.name for tag in possible_tags] if possible_tags is not None else []
    result = await master_extract_todo_agent.run(text, deps=TodoDeps(tzinfo=tz, possible_tags=tag_str),
                                                  usage_limits=todo_usage_limit)
    return result.output


if __name__ == "__main__":
    load_dotenv()
    LOGFIRE_TOKEN = os.environ.get("LOGFIRE_TOKEN")
    logfire.configure(
        token=LOGFIRE_TOKEN,
    )
    # Test the todo service
    test_text = "Merk dir: Milch kaufen bis morgen 15 Uhr"
    test_phone = "+1234567890"  # Replace with actual test phone number
    result = todo_service(test_text, test_phone)
    print(result)
