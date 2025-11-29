"""Tag Sharing API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional
import logfire

from server.core.service.supabase_connectors.supabase_client import get_supabase_client
from server.core.service.supabase_connectors import tag_shared_service
from server.core.models.reminder_models import (
    ReminderTagSharedModel,
    CreateSharedTagRequest,
    ClaimSharedTagRequest
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
router = APIRouter()


@router.post("/create", response_model=dict)
async def create_shared_tag(
    request: CreateSharedTagRequest,
    token: str = Depends(oauth2_scheme)
):
    """Create a tag share between users."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only share their own tags
        if str(user.user.id) != request.user_shares:
            raise HTTPException(status_code=403, detail="You can only share your own tags")

        share_data = {
            'tag_id': request.tag_id,
            'user_shared_with': request.user_shared_with,
            'user_shares': request.user_shares
        }

        share_uuid = tag_shared_service.create_shared_tag(share_data, supabase_client)

        return {"uuid": share_uuid, "message": "Tag shared successfully"}

    except ValueError as e:
        logfire.error(f"Validation error creating shared tag: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error creating shared tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-tag/{tag_id}", response_model=List[ReminderTagSharedModel])
async def get_shares_by_tag(
    tag_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Get all shares for a tag."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        shares = tag_shared_service.find_by_tag_id(tag_id, supabase_client)

        return shares

    except Exception as e:
        logfire.error(f"Error fetching shares by tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-with/{user_id}", response_model=List[ReminderTagSharedModel])
async def get_tags_shared_with_user(
    user_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Get tags shared with a user."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own shares
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        shares = tag_shared_service.find_shared_with_user(user_id, supabase_client)

        return shares

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching tags shared with user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-by/{user_id}", response_model=List[ReminderTagSharedModel])
async def get_tags_shared_by_user(
    user_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Get tags shared by a user."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own shares
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        shares = tag_shared_service.find_shared_by_user(user_id, supabase_client)

        return shares

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching tags shared by user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-with-or-by/{user_id}", response_model=List[ReminderTagSharedModel])
async def get_tags_shared_with_or_by_user(
    user_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Get tags shared with or by a user (bidirectional OR query)."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only access their own shares
        if str(user.user.id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        shares = tag_shared_service.find_shared_with_user_or_shared_by(user_id, supabase_client)

        return shares

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching bidirectional shares: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{uuid}", response_model=ReminderTagSharedModel)
async def get_share_by_uuid(
    uuid: str,
    token: str = Depends(oauth2_scheme)
):
    """Get a share by its UUID."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        share = tag_shared_service.find_by_uuid(uuid, supabase_client)

        if not share:
            raise HTTPException(status_code=404, detail="Share not found")

        return share

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching share by UUID: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/claim", response_model=dict)
async def claim_shared_tag(
    request: ClaimSharedTagRequest,
    token: str = Depends(oauth2_scheme)
):
    """Claim a shared tag (calls RPC function).

    This endpoint calls the Supabase RPC function 'claim_shared_tag' which
    handles the complex logic of accepting a tag share.
    """
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        # Verify user can only claim shares for themselves
        if str(user.user.id) != request.user_id:
            raise HTTPException(status_code=403, detail="You can only claim shares for yourself")

        tag_shared_service.claim_shared_tag(request.share_id, request.user_id, supabase_client)

        return {"message": "Tag claimed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error claiming shared tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{uuid}", response_model=dict)
async def delete_shared_tag(
    uuid: str,
    token: str = Depends(oauth2_scheme)
):
    """Delete a share by UUID."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_shared_service.delete_shared_tag(uuid, supabase_client)

        return {"message": "Shared tag deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting shared tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/by-tag-user", response_model=dict)
async def delete_share_by_tag_and_user(
    tag_id: int = Query(..., description="Tag ID"),
    user_shared_with: str = Query(..., description="User UUID the tag is shared with"),
    token: str = Depends(oauth2_scheme)
):
    """Delete a specific share between tag and user."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_shared_service.delete_by_tag_and_user(tag_id, user_shared_with, supabase_client)

        return {"message": f"Share for tag {tag_id} with user {user_shared_with} deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/by-tag/{tag_id}", response_model=dict)
async def delete_all_shares_by_tag(
    tag_id: int,
    token: str = Depends(oauth2_scheme)
):
    """Delete all shares for a tag."""
    try:
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        tag_shared_service.delete_all_by_tag_id(tag_id, supabase_client)

        return {"message": f"All shares for tag {tag_id} deleted successfully"}

    except Exception as e:
        logfire.error(f"Error deleting shares by tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))
