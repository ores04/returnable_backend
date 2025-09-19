from supabase import Client

from server.core.ai.agents.email_reply_service import TodoItem, InputItem
from server.core.service.supabase_connectors.supabase_client import get_supabase_client

RETURN_TASKS_TABLE_NAME = "RETURN_TASKS"


def add_task_to_db(service_client: Client, task: TodoItem | InputItem, returnable_id: str):
    """This function adds a new task to the database."""
    task_data = {
        "type": task.requested_type,
        "return_request_id": returnable_id,
        "text": task.description,
    }

    response = service_client.table(RETURN_TASKS_TABLE_NAME).insert(task_data).execute()
    response.raise_when_api_error(response)

    return response.data
