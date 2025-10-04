import os
import logfire

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Query, Request, BackgroundTasks, Header
from fastapi.security import OAuth2PasswordBearer

from server.core.service.supabase_connectors.supabase_client import get_uuid_from_phone_number, \
    is_premium_user_from_uuid
from server.core.service.whatsapp_service.whatsapp_utils import send_message
from server.core.service.whatsapp_service.whatsapp_webhook_service import handle_media_message, process_document, \
    handle_text_message, handle_audio_message

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "not_set")


@router.post("/send-welcome-message/{phone_number_id}")
def send_welcome_message(phone_number_id: str, token: str = Depends(oauth2_scheme)):
    """ Endpoint to send a welcome message to a new user."""

    if WHATSAPP_PHONE_ID == "not_set":
        logfire.error("WhatsApp phone ID is not set. Please set the environment variable WHATSAPP_PHONE_ID.")
        raise HTTPException(status_code=500, detail="WhatsApp phone ID is not set.")

    welcome_message = "Hi, sag mir wenn ich dich an etwas erinnern soll! Erinner mich... Wenn du Premium hast kannst du auch einfach eine Sprachmemo schicken!"
    send_message(phone_number_id, welcome_message, WHATSAPP_PHONE_ID)
    return {
        "status": "success",
        "message": f"Welcome message sent to {phone_number_id}"
    }


