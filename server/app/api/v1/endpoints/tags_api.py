"""Tags API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import List, Dict
import logfire

from core.service.supabase_connectors.supabase_client import get_supabase_client
from core.service.supabase_connectors import supabase_tag_service
from core.models.reminder_models import (
    ReminderTagModel,
    CreateTagRequest,
    UpdateTagRequest
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
router = APIRouter()


@router.post("/create", response_model=dict)
async def create_tag(
    request: CreateTagRequest,
    token: str = Depends(oauth2_scheme)
):
    """Create a new tag."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only create tags for themselves
        if str(user.user.id) != request.user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        tag_data = {
            'name': request.name,
            'color': request.color,
            'user_id': request.user_id
        }

        # Remove None values
        tag_data = {k: v for k, v in tag_data.items() if v is not None}

        tag_id = supabase_tag_service.create_tag(tag_data, supabase_client)

        return {"id": tag_id, "message": "Tag created successfully"}

    except ValueError as e:
        logfire.error(f"Validation error creating tag: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error creating tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tag_id}", response_model=ReminderTagModel)
async def get_tag(
    tag_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Get a tag by ID."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag = supabase_tag_service.find_tag_by_id(tag_id, supabase_client)

        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")

        return tag

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/owned", response_model=List[ReminderTagModel])
async def get_owned_tags(
    user_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Get tags owned by a user."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own tags
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        tags = supabase_tag_service.find_tags_owned_by_user(user_id, supabase_client)

        return tags

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching owned tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/accessible", response_model=List[ReminderTagModel])
async def get_accessible_tags(
    user_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Get all tags accessible to a user (owned + shared)."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own tags
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        tags = supabase_tag_service.find_tags_accessible_to_user(user_id, supabase_client)

        return tags

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching accessible tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-reminder-ids", response_model=Dict[int, List[ReminderTagModel]])
async def get_tags_by_reminder_ids(
    ids: str,  # Comma-separated list of IDs
    token: str = Depends(oauth2_scheme)
):
    """Get tags for multiple reminders.

    Returns a dictionary mapping reminder_id -> list of tags.

    Query parameter 'ids' should be comma-separated list, e.g., "1,2,3"
    """
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Parse comma-separated IDs
        reminder_ids = [int(id_str.strip()) for id_str in ids.split(',')]

        tags_by_reminder = supabase_tag_service.find_tags_by_reminder_id_list(
            reminder_ids,
            supabase_client
        )

        return tags_by_reminder

    except ValueError as e:
        logfire.error(f"Invalid ID format: {e}")
        raise HTTPException(status_code=400, detail="Invalid ID format. Use comma-separated integers.")
    except Exception as e:
        logfire.error(f"Error fetching tags by reminder IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{tag_id}", response_model=ReminderTagModel)
async def update_tag(
    tag_id: int,
    request: UpdateTagRequest,
    token: str = Depends(oauth2_scheme)
):
    """Update a tag."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_data = {}
        if request.name is not None:
            tag_data['name'] = request.name
        if request.color is not None:
            tag_data['color'] = request.color

        updated_tag = supabase_tag_service.update_tag(tag_id, tag_data, supabase_client)

        return updated_tag

    except ValueError as e:
        logfire.error(f"Validation error updating tag: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logfire.error(f"Error updating tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tag_id}", response_model=dict)
async def delete_tag(
    tag_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Delete a tag."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        supabase_tag_service.delete_tag(tag_id, supabase_client)

        return {"message": "Tag deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))
