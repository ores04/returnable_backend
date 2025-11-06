"""This file provides API endpoints for creating to-do items."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import logfire

from server.core.ai.ai_clients.openai_client import OpenAIClient
from server.core.service.supabase_connectors.supabase_client import get_supabase_client
from server.core.service.whatsapp_service.whatsapp_parent_todo_remidner_service import extract_and_create_items

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class AudioProcessRequest(BaseModel):
    """Request model for audio processing with optional tags."""
    possible_tags: Optional[List[str]] = None


@router.post("/handle-audio-message")
async def handle_audio_message(
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
    possible_tags: Optional[str] = None
):
    """
    Endpoint to process audio files and extract todos/reminders.

    Args:
        file: The uploaded audio file (supports mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg)
        token: OAuth2 authentication token
        possible_tags: Optional comma-separated list of possible tags

    Returns:
        Dictionary containing created items and confirmation messages
    """
    try:
        # Get user from token
        supabase_client = get_supabase_client(jwt_token=token)
        user = supabase_client.auth.get_user(token)

        if not user or not user.user:
            logfire.error("Invalid token or unable to get user")
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        uuid = user.user.id

        # Read audio file
        try:
            audio_data = await file.read()
        except Exception as e:
            logfire.error(f"Failed to read audio file: {str(e)}")
            raise HTTPException(status_code=400, detail="Failed to read audio file")

        # Transcribe audio using OpenAI
        openai_client = OpenAIClient()
        try:
            transcribed_text = openai_client.get_text_from_audio(audio_data,file_name="audio.m4a",file_type="audio/m4a")

            if not transcribed_text:
                logfire.warning("Audio transcription returned empty text")
                return {
                    "status": "error",
                    "message": "Could not transcribe audio - no text detected",
                    "items": [],
                    "messages": []
                }
        except Exception as e:
            logfire.error(f"Audio transcription failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Audio transcription failed: {str(e)}")

        logfire.info(f"Transcribed text: {transcribed_text}")

        # Parse possible_tags if provided
        tags_list = None
        if possible_tags:
            # Parse comma-separated tags into a list
            # Note: This is a simplified version - in production you might want to
            # validate these against the ReminderTag model
            tags_list = [tag.strip() for tag in possible_tags.split(",") if tag.strip()]

        # Extract and create todos/reminders
        try:
            result = await extract_and_create_items(
                text=transcribed_text,
                phone_number=None,
                uuid=uuid,
                possible_tags=tags_list
            )

            return {
                "status": "success",
                "transcribed_text": transcribed_text,
                "items": result["items"],
                "messages": result["messages"]
            }
        except Exception as e:
            logfire.error(f"Failed to extract and create items: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to process todos/reminders: {str(e)}")

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logfire.error(f"Unexpected error in handle_audio_message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
