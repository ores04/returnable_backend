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


# New functions for API endpoints

import logfire
from typing import List, Optional


def create_task(task_data: dict, service_client: Client) -> int:
    """Create a new task.

    Args:
        task_data: Dictionary with task fields
        service_client: Supabase client instance

    Returns:
        ID of created task
    """
    logfire.info(f"Creating task for return_request {task_data.get('return_request_id')}")

    response = service_client.table(RETURN_TASKS_TABLE_NAME).insert(task_data).execute()

    if not response.data or len(response.data) == 0:
        raise ValueError("Failed to create task")

    return response.data[0]['id']


def find_task_by_id(task_id: int, service_client: Client) -> Optional[dict]:
    """Get a task by ID.

    Args:
        task_id: ID of the task
        service_client: Supabase client instance

    Returns:
        Task dictionary or None
    """
    logfire.debug(f"Finding task {task_id}")

    response = service_client.table(RETURN_TASKS_TABLE_NAME) \
        .select('*') \
        .eq('id', task_id) \
        .execute()

    if not response.data or len(response.data) == 0:
        return None

    return response.data[0]


def find_all_tasks(service_client: Client, limit: Optional[int] = None) -> List[dict]:
    """Get all tasks ordered by created_at.

    Args:
        service_client: Supabase client instance
        limit: Optional limit on number of results

    Returns:
        List of task dictionaries
    """
    logfire.debug(f"Finding all tasks (limit={limit})")

    query = service_client.table(RETURN_TASKS_TABLE_NAME) \
        .select('*') \
        .order('created_at', desc=True)

    if limit:
        query = query.limit(limit)

    response = query.execute()

    return response.data


def find_tasks_by_return_request_id(return_request_id: int, service_client: Client) -> List[dict]:
    """Get tasks by return request ID.

    Args:
        return_request_id: ID of the return request
        service_client: Supabase client instance

    Returns:
        List of task dictionaries
    """
    logfire.debug(f"Finding tasks for return_request {return_request_id}")

    response = service_client.table(RETURN_TASKS_TABLE_NAME) \
        .select('*') \
        .eq('return_request_id', return_request_id) \
        .execute()

    return response.data


def update_task(task_id: int, task_data: dict, service_client: Client) -> dict:
    """Update a task.

    Args:
        task_id: ID of the task
        task_data: Dictionary with fields to update
        service_client: Supabase client instance

    Returns:
        Updated task dictionary
    """
    logfire.info(f"Updating task {task_id}")

    response = service_client.table(RETURN_TASKS_TABLE_NAME) \
        .update(task_data) \
        .eq('id', task_id) \
        .execute()

    if not response.data or len(response.data) == 0:
        raise ValueError(f"Task {task_id} not found")

    return response.data[0]


def delete_task(task_id: int, service_client: Client) -> None:
    """Delete a task.

    Args:
        task_id: ID of the task
        service_client: Supabase client instance
    """
    logfire.info(f"Deleting task {task_id}")

    service_client.table(RETURN_TASKS_TABLE_NAME) \
        .delete() \
        .eq('id', task_id) \
        .execute()
