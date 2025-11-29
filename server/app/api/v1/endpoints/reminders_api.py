"""Reminders API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional
from datetime import datetime
import logfire

from core.service.supabase_connectors.supabase_client import get_supabase_client
from core.service.supabase_connectors import supabase_reminder_client as reminder_client
from core.service.supabase_connectors import parent_reminder_service
from core.models.reminder_models import (
    ReminderModel,
    CreateReminderRequest,
    CreateReminderWithTagsRequest,
    UpdateReminderRequest,
    UpdateReminderWithTagsRequest
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
router = APIRouter()


@router.post("/create", response_model=dict)
async def create_reminder(
    request: CreateReminderRequest,
    token: str = Depends(oauth2_scheme)
):
    """Create a new reminder."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only create reminders for themselves
        if str(user.user.id) != request.user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        reminder_data = {
            'user_id': request.user_id,
            'reminder_text': request.reminder_text,
            'event_time': request.event_time.isoformat() if request.event_time else None,
            'done': request.done
        }

        # Remove None values
        reminder_data = {k: v for k, v in reminder_data.items() if v is not None}

        # Create reminder
        reminder_id = reminder_client.create_reminder(reminder_data, supabase_client)

        # Create reminder times if provided
        if request.reminder_times:
            times_data = [
                {
                    'reminder_id': reminder_id,
                    'reminder_time': rt.reminder_time.isoformat()
                }
                for rt in request.reminder_times
            ]
            supabase_client.table('REMINDER_TIME').insert(times_data).execute()

        return {"id": reminder_id, "message": "Reminder created successfully"}

    except ValueError as e:
        logfire.error(f"Validation error creating reminder: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error creating reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-with-tags", response_model=dict)
async def create_reminder_with_tags(
    request: CreateReminderWithTagsRequest,
    token: str = Depends(oauth2_scheme)
):
    """Create reminder with tags (orchestrated)."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only create reminders for themselves
        if str(user.user.id) != request.user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        reminder_data = {
            'user_id': request.user_id,
            'reminder_text': request.reminder_text,
            'event_time': request.event_time.isoformat() if request.event_time else None,
            'done': request.done
        }

        # Remove None values
        reminder_data = {k: v for k, v in reminder_data.items() if v is not None}

        # Use orchestration service
        reminder_id = parent_reminder_service.create_reminder_with_tags(
            reminder_data=reminder_data,
            tag_ids=request.tag_ids,
            service_client=supabase_client
        )

        # Create reminder times if provided
        if request.reminder_times:
            times_data = [
                {
                    'reminder_id': reminder_id,
                    'reminder_time': rt.reminder_time.isoformat()
                }
                for rt in request.reminder_times
            ]
            supabase_client.table('REMINDER_TIME').insert(times_data).execute()

        return {
            "id": reminder_id,
            "message": f"Reminder created successfully with {len(request.tag_ids)} tags"
        }

    except ValueError as e:
        logfire.error(f"Validation error creating reminder with tags: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error creating reminder with tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{reminder_id}", response_model=dict)
async def get_reminder(
    reminder_id: int,
    include_times: bool = Query(True, description="Include reminder times"),
    include_tags: bool = Query(False, description="Include tags"),
    token: str = Depends(oauth2_scheme)
):
    """Get a reminder by ID with optional nested data."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        reminder = reminder_client.find_reminder_by_id(
            reminder_id=reminder_id,
            service_client=supabase_client,
            include_times=include_times,
            include_tags=include_tags
        )

        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")

        return reminder

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-ids", response_model=List[dict])
async def get_reminders_by_ids(
    ids: str = Query(..., description="Comma-separated list of reminder IDs"),
    token: str = Depends(oauth2_scheme)
):
    """Get reminders by ID list with complex joins.

    This preserves the complex nested select from frontend:
    '*, REMINDER_TIME(*), REMINDER_TAG_CONNECTION(REMINDER_TAG(*))'

    Query parameter 'ids' should be comma-separated list, e.g., "1,2,3"
    """
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Parse comma-separated IDs
        reminder_ids = [int(id_str.strip()) for id_str in ids.split(',')]

        reminders = reminder_client.find_reminders_by_id_list(reminder_ids, supabase_client)

        return reminders

    except ValueError as e:
        logfire.error(f"Invalid ID format: {e}")
        raise HTTPException(status_code=400, detail="Invalid ID format. Use comma-separated integers.")
    except Exception as e:
        logfire.error(f"Error fetching reminders by IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/newest", response_model=List[dict])
async def get_newest_reminders(
    limit: int = Query(10, description="Maximum number of reminders to return"),
    token: str = Depends(oauth2_scheme)
):
    """Get newest reminders ordered by created_at."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        reminders = reminder_client.find_newest_reminders(supabase_client, limit)

        return reminders

    except Exception as e:
        logfire.error(f"Error fetching newest reminders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/after", response_model=List[dict])
async def get_user_reminders_after(
    user_id: str,
    after: str = Query(..., description="ISO 8601 datetime string"),
    limit: int = Query(100, description="Maximum number of reminders"),
    token: str = Depends(oauth2_scheme)
):
    """Get user reminders after a specific date."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own reminders
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Parse datetime
        after_dt = datetime.fromisoformat(after.replace('Z', '+00:00'))

        reminders = reminder_client.find_user_reminders_after(
            user_id=user_id,
            after=after_dt,
            limit=limit,
            service_client=supabase_client
        )

        return reminders

    except ValueError as e:
        logfire.error(f"Invalid datetime format: {e}")
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO 8601.")
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching user reminders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/ids", response_model=List[int])
async def get_user_reminder_ids(
    user_id: str,
    after: Optional[str] = Query(None, description="ISO 8601 datetime string"),
    limit: int = Query(100, description="Maximum number of IDs"),
    include_overdue: bool = Query(False, description="Include overdue reminders (done=false)"),
    token: str = Depends(oauth2_scheme)
):
    """Get user reminder IDs with OR query for overdue."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own reminders
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Parse datetime if provided
        after_dt = None
        if after:
            after_dt = datetime.fromisoformat(after.replace('Z', '+00:00'))

        reminder_ids = reminder_client.find_user_reminder_ids(
            user_id=user_id,
            after=after_dt,
            limit=limit,
            include_overdue=include_overdue,
            service_client=supabase_client
        )

        return reminder_ids

    except ValueError as e:
        logfire.error(f"Invalid datetime format: {e}")
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO 8601.")
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching user reminder IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/all", response_model=List[dict])
async def get_all_user_reminders(
    user_id: str,
    after: Optional[str] = Query(None, description="ISO 8601 datetime string"),
    token: str = Depends(oauth2_scheme)
):
    """Get all user reminders (owned + shared, orchestrated)."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own reminders
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Parse datetime if provided
        after_dt = None
        if after:
            after_dt = datetime.fromisoformat(after.replace('Z', '+00:00'))

        # Use orchestration service
        reminders = parent_reminder_service.find_all_reminders_by_user_id(
            user_id=user_id,
            after=after_dt,
            service_client=supabase_client
        )

        return reminders

    except ValueError as e:
        logfire.error(f"Invalid datetime format: {e}")
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO 8601.")
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching all user reminders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/shared-ids", response_model=List[int])
async def get_shared_reminder_ids(
    user_id: str,
    after: Optional[str] = Query(None, description="ISO 8601 datetime string"),
    include_overdue: bool = Query(False, description="Include overdue reminders"),
    token: str = Depends(oauth2_scheme)
):
    """Get reminder IDs shared with user via shared tags."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own reminders
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Parse datetime if provided
        after_dt = None
        if after:
            after_dt = datetime.fromisoformat(after.replace('Z', '+00:00'))

        # Use orchestration service
        reminder_ids = parent_reminder_service.find_reminders_ids_shared_with_user(
            user_id=user_id,
            after=after_dt,
            include_overdue=include_overdue,
            service_client=supabase_client
        )

        return reminder_ids

    except ValueError as e:
        logfire.error(f"Invalid datetime format: {e}")
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO 8601.")
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching shared reminder IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{reminder_id}", response_model=dict)
async def update_reminder(
    reminder_id: int,
    request: UpdateReminderRequest,
    token: str = Depends(oauth2_scheme)
):
    """Update a reminder."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        reminder_data = {}
        if request.reminder_text is not None:
            reminder_data['reminder_text'] = request.reminder_text
        if request.event_time is not None:
            reminder_data['event_time'] = request.event_time.isoformat()
        if request.done is not None:
            reminder_data['done'] = request.done

        # Convert reminder_times to dict list if provided
        if request.reminder_times is not None:
            reminder_data['reminder_times'] = [
                {'reminder_time': rt.reminder_time.isoformat()}
                for rt in request.reminder_times
            ]

        updated_reminder = reminder_client.update_reminder(
            reminder_id=reminder_id,
            reminder_data=reminder_data,
            service_client=supabase_client,
            replace_times=True
        )

        return updated_reminder

    except ValueError as e:
        logfire.error(f"Validation error updating reminder: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logfire.error(f"Error updating reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{reminder_id}/update-with-tags", response_model=dict)
async def update_reminder_with_tags(
    reminder_id: int,
    request: UpdateReminderWithTagsRequest,
    token: str = Depends(oauth2_scheme)
):
    """Update reminder with tag synchronization (orchestrated)."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        reminder_data = {}
        if request.reminder_text is not None:
            reminder_data['reminder_text'] = request.reminder_text
        if request.event_time is not None:
            reminder_data['event_time'] = request.event_time.isoformat()
        if request.done is not None:
            reminder_data['done'] = request.done

        # Convert reminder_times to dict list if provided
        if request.reminder_times is not None:
            reminder_data['reminder_times'] = [
                {'reminder_time': rt.reminder_time.isoformat()}
                for rt in request.reminder_times
            ]

        # Use orchestration service
        updated_reminder = parent_reminder_service.update_reminder_with_tags(
            reminder_id=reminder_id,
            reminder_data=reminder_data,
            tag_ids=request.tag_ids,
            service_client=supabase_client
        )

        return updated_reminder

    except ValueError as e:
        logfire.error(f"Validation error updating reminder with tags: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logfire.error(f"Error updating reminder with tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{reminder_id}/toggle-done", response_model=dict)
async def toggle_reminder_done(
    reminder_id: int,
    done: bool = Query(..., description="New done status"),
    token: str = Depends(oauth2_scheme)
):
    """Toggle the done status of a reminder."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        updated_reminder = reminder_client.toggle_reminder_done(
            reminder_id=reminder_id,
            done=done,
            service_client=supabase_client
        )

        return updated_reminder

    except ValueError as e:
        logfire.error(f"Validation error toggling reminder done: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logfire.error(f"Error toggling reminder done: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{reminder_id}", response_model=dict)
async def delete_reminder(
    reminder_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Delete a reminder and associated reminder_times."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        reminder_client.delete_reminder(reminder_id, supabase_client)

        return {"message": "Reminder deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))
