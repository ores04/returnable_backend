"""Tasks API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional
import logfire

from core.service.supabase_connectors.supabase_client import get_supabase_client
from core.service.supabase_connectors import tasks_client
from core.models.reminder_models import (
    ReturnTaskModel,
    CreateTaskRequest,
    UpdateTaskRequest
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
router = APIRouter()


@router.post("/create", response_model=dict)
async def create_task(
    request: CreateTaskRequest,
    token: str = Depends(oauth2_scheme)
):
    """Create a new task."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        task_data = {
            'type': request.type,
            'text': request.text,
            'return_request_id': request.return_request_id,
            'answer': request.answer
        }

        # Remove None values
        task_data = {k: v for k, v in task_data.items() if v is not None}

        task_id = tasks_client.create_task(task_data, supabase_client)

        return {"id": task_id, "message": "Task created successfully"}

    except ValueError as e:
        logfire.error(f"Validation error creating task: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logfire.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}", response_model=ReturnTaskModel)
async def get_task(
    task_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Get a task by ID."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        task = tasks_client.find_task_by_id(task_id, supabase_client)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return task

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=List[ReturnTaskModel])
async def list_all_tasks(
    limit: Optional[int] = None,
    token: str = Depends(oauth2_scheme)
):
    """List all tasks ordered by created_at."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tasks = tasks_client.find_all_tasks(supabase_client, limit)

        return tasks

    except Exception as e:
        logfire.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-return-request/{return_request_id}", response_model=List[ReturnTaskModel])
async def get_tasks_by_return_request(
    return_request_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Get all tasks for a return request."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tasks = tasks_client.find_tasks_by_return_request_id(return_request_id, supabase_client)

        return tasks

    except Exception as e:
        logfire.error(f"Error fetching tasks by return request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{task_id}", response_model=ReturnTaskModel)
async def update_task(
    task_id: int,
    request: UpdateTaskRequest,
    token: str = Depends(oauth2_scheme)
):
    """Update a task."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        task_data = {}
        if request.type is not None:
            task_data['type'] = request.type
        if request.text is not None:
            task_data['text'] = request.text
        if request.answer is not None:
            task_data['answer'] = request.answer

        updated_task = tasks_client.update_task(task_id, task_data, supabase_client)

        return updated_task

    except ValueError as e:
        logfire.error(f"Validation error updating task: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logfire.error(f"Error updating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}", response_model=dict)
async def delete_task(
    task_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Delete a task."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tasks_client.delete_task(task_id, supabase_client)

        return {"message": "Task deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
