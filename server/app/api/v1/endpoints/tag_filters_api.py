"""Tag Filter API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional
import logfire

from core.service.supabase_connectors.supabase_client import get_supabase_client
from core.service.supabase_connectors import tag_filter_service
from core.models.reminder_models import (
    TagFilterModel,
    CreateTagFilterRequest,
    ReplaceTagFiltersRequest
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
router = APIRouter()


@router.post("/create", response_model=dict)
async def create_tag_filter(
    request: CreateTagFilterRequest,
    token: str = Depends(oauth2_scheme)
):
    """Create a new tag filter."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        filter_data = {
            'tag_id': request.tag_id,
            'user_id': request.user_id
        }

        filter_id = tag_filter_service.create_tag_filter(filter_data, supabase_client)

        return {"id": filter_id, "message": "Tag filter created successfully"}

    except ValueError as e:
        logfire.error(f"Validation error creating tag filter: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logfire.error(f"Error creating tag filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{filter_id}", response_model=TagFilterModel)
async def get_tag_filter(
    filter_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Get a tag filter by ID."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_filter = tag_filter_service.find_by_id(filter_id, supabase_client)

        if not tag_filter:
            raise HTTPException(status_code=404, detail="Tag filter not found")

        return tag_filter

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching tag filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}", response_model=List[TagFilterModel])
async def get_user_tag_filters(
    user_id: str,
    limit: Optional[int] = None,
    token: str = Depends(oauth2_scheme)
):
    """Get all tag filters for a user."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own filters
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        filters = tag_filter_service.find_all_tag_filters(user_id, limit, supabase_client)

        return filters

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching user tag filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/active-ids", response_model=List[int])
async def get_active_tag_ids(
    user_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Get active tag IDs for a user."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own filters
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        tag_ids = tag_filter_service.get_active_tag_ids(user_id, supabase_client)

        return tag_ids

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching active tag IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{filter_id}", response_model=TagFilterModel)
async def update_tag_filter(
    filter_id: int,
    tag_id: Optional[int] = None,
    token: str = Depends(oauth2_scheme)
):
    """Update a tag filter."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        filter_data = {}
        if tag_id is not None:
            filter_data['tag_id'] = tag_id

        updated_filter = tag_filter_service.update_tag_filter(filter_id, filter_data, supabase_client)

        return updated_filter

    except ValueError as e:
        logfire.error(f"Validation error updating tag filter: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logfire.error(f"Error updating tag filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/user/{user_id}/replace", response_model=dict)
async def replace_user_tag_filters(
    user_id: str,
    request: ReplaceTagFiltersRequest,
    token: str = Depends(oauth2_scheme)
):
    """Replace all tag filters for a user (delete all + insert new)."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only modify their own filters
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        tag_filter_service.replace_user_tag_filters(user_id, request.tag_ids, supabase_client)

        return {"message": f"Replaced tag filters with {len(request.tag_ids)} tags"}

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error replacing tag filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{filter_id}", response_model=dict)
async def delete_tag_filter(
    filter_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Delete a tag filter."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_filter_service.delete_tag_filter(filter_id, supabase_client)

        return {"message": "Tag filter deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting tag filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/by-tag/{tag_id}", response_model=dict)
async def delete_filters_by_tag(
    tag_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Delete all filters for a tag."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_filter_service.delete_by_tag_id(tag_id, supabase_client)

        return {"message": f"All filters for tag {tag_id} deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting filters by tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))
