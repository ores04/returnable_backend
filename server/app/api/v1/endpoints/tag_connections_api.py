"""Tag Connection API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional
from datetime import datetime
import logfire

from core.service.supabase_connectors.supabase_client import get_supabase_client
from core.service.supabase_connectors import tag_connection_service
from core.models.reminder_models import (
    ReminderTagConnectionModel,
    CreateTagConnectionRequest
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
router = APIRouter()


@router.post("/create", response_model=dict)
async def create_connection(
    request: CreateTagConnectionRequest,
    token: str = Depends(oauth2_scheme)
):
    """Create a reminder-tag connection."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        connection_data = {
            'reminder_id': request.reminder_id,
            'tag_id': request.tag_id
        }

        connection_id = tag_connection_service.create_connection(connection_data, supabase_client)

        return {"id": connection_id, "message": "Tag connection created successfully"}

    except ValueError as e:
        logfire.error(f"Validation error creating tag connection: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logfire.error(f"Error creating tag connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-reminder/{reminder_id}", response_model=List[ReminderTagConnectionModel])
async def get_connections_by_reminder(
    reminder_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Get all tag connections for a reminder."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        connections = tag_connection_service.find_by_reminder_id(reminder_id, supabase_client)

        return connections

    except Exception as e:
        logfire.error(f"Error fetching connections by reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-tag/{tag_id}", response_model=List[ReminderTagConnectionModel])
async def get_connections_by_tag(
    tag_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Get all reminder connections for a tag."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        connections = tag_connection_service.find_by_tag_id(tag_id, supabase_client)

        return connections

    except Exception as e:
        logfire.error(f"Error fetching connections by tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-tag-list", response_model=List[ReminderTagConnectionModel])
async def get_connections_by_tag_list(
    ids: str = Query(..., description="Comma-separated list of tag IDs"),
    token: str = Depends(oauth2_scheme)
):
    """Get connections for multiple tags.

    Query parameter 'ids' should be comma-separated list, e.g., "1,2,3"
    """
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Parse comma-separated IDs
        tag_ids = [int(id_str.strip()) for id_str in ids.split(',')]

        connections = tag_connection_service.find_by_tag_id_list(tag_ids, supabase_client)

        return connections

    except ValueError as e:
        logfire.error(f"Invalid ID format: {e}")
        raise HTTPException(status_code=400, detail="Invalid ID format. Use comma-separated integers.")
    except Exception as e:
        logfire.error(f"Error fetching connections by tag list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-tag-list-filtered", response_model=List[dict])
async def get_connections_by_tag_list_filtered(
    ids: str = Query(..., description="Comma-separated list of tag IDs"),
    after: Optional[str] = Query(None, description="ISO 8601 datetime string to filter reminders after"),
    include_overdue: bool = Query(False, description="Include overdue reminders (done=false)"),
    token: str = Depends(oauth2_scheme)
):
    """Get connections by tag list with reminder filters (complex join).

    This endpoint uses an inner join with the REMINDER table to filter connections
    based on reminder properties. Supports OR query for overdue reminders.

    Query parameters:
    - ids: Comma-separated list of tag IDs (e.g., "1,2,3")
    - after: ISO 8601 datetime to filter by event_time (optional)
    - include_overdue: Include reminders where done=false regardless of date
    """
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Parse comma-separated IDs
        tag_ids = [int(id_str.strip()) for id_str in ids.split(',')]

        # Parse datetime if provided
        after_dt = None
        if after:
            after_dt = datetime.fromisoformat(after.replace('Z', '+00:00'))

        # Call service with complex join query
        connections = tag_connection_service.find_by_tag_id_list_with_reminder_filters(
            tag_ids=tag_ids,
            after=after_dt,
            include_overdue=include_overdue,
            service_client=supabase_client
        )

        return connections

    except ValueError as e:
        logfire.error(f"Invalid parameter format: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logfire.error(f"Error fetching filtered connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{connection_id}", response_model=dict)
async def delete_connection(
    connection_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Delete a single tag connection."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_connection_service.delete_connection(connection_id, supabase_client)

        return {"message": "Tag connection deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting tag connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/by-reminder-tag", response_model=dict)
async def delete_connection_by_reminder_and_tag(
    reminder_id: int = Query(..., description="Reminder ID"),
    tag_id: int = Query(..., description="Tag ID"),
    token: str = Depends(oauth2_scheme)
):
    """Delete a specific reminder-tag connection."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_connection_service.delete_by_reminder_and_tag(reminder_id, tag_id, supabase_client)

        return {"message": f"Connection between reminder {reminder_id} and tag {tag_id} deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting tag connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/by-reminder/{reminder_id}", response_model=dict)
async def delete_all_connections_by_reminder(
    reminder_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Delete all tag connections for a reminder."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_connection_service.delete_all_by_reminder_id(reminder_id, supabase_client)

        return {"message": f"All tag connections for reminder {reminder_id} deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting tag connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/by-tag/{tag_id}", response_model=dict)
async def delete_all_connections_by_tag(
    tag_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Delete all reminder connections for a tag."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_connection_service.delete_all_by_tag_id(tag_id, supabase_client)

        return {"message": f"All reminder connections for tag {tag_id} deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting tag connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))
