import hashlib
import hmac
import json
import os
import logfire
from io import BytesIO

import requests
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Query, Request, BackgroundTasks, Header
from fastapi.security import OAuth2PasswordBearer

from server.core.ai.agents.invoice_image_processing_using_llm import LLMImageProcessor
from server.core.ai.ai_clients.mistal_ai_client import MistralAiClient
from server.core.service.document_service.file_input_pipeline import process_text_input
from server.core.service.document_service.whatsapp_webhook_service import handle_media_message, process_document

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "not_set")
ACCESS_TOKEN = os.getenv("WHATSAPP_ACSESS_TOKEN", "not_set")
APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "not_set").encode("utf8")


if VERIFY_TOKEN == "not_set":
    logfire.warning("Warning: WhatsApp verify token is not set. Please set the environment variable WHATSAPP_VERIFY_TOKEN.")

@router.post("/add-document/{doc_title}")
async def add_document(file: UploadFile, doc_title:str ,token: str = Depends(oauth2_scheme)):
    """ Endpoint to add a document to the database."""

    # try to read the file
    try:
        contents = await file.read()
    except Exception as e:
        logfire.error(f"Failed to read file: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to read file at endpoint /add-document"
        }
    doc_id = await process_document(contents, doc_title, token)

    return doc_id





@router.get("/whatsapp/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Forbidden")

# Handle incoming messages
@router.post("/whatsapp/webhook")
async def handle_webhook(request: Request,background_tasks: BackgroundTasks,x_hub_signature_256: str = Header(None) ):
    # TODO parall await
    data = await request.json()
    raw_body = await request.body()

    verified_origin = await verifiy_post_header(raw_body, x_hub_signature_256)
    if not verified_origin:
        raise HTTPException(status_code=403, detail="Forbidden")

    background_tasks.add_task(handle_request, data)
    return {"status": "EVENT_RECEIVED"}

async def verifiy_post_header(raw_body, signature_header):

    if signature_header is None:
        # Reject requests without a signature
        logfire.warning("Request rejected: Missing X-Hub-Signature-256 header.")
        return False

    # The header is in the format "sha256=xxxxxxxx...", we need the hash part
    hmac_recieved = signature_header.removeprefix('sha256=')
    # 3. Compute the expected signature
    computed_hash = hmac.new(APP_SECRET, raw_body, hashlib.sha256).hexdigest()

    # 4. Compare the signatures using a constant-time comparison
    if not hmac.compare_digest(hmac_recieved, computed_hash):
        logfire.warning("Request rejected: Invalid signature.")
        return False
    logfire.info("Verification OK")
    return True


def handle_request(data: dict):
    """This function is used to handle the incoming request. It will be called in the background task."""
    #print("Received webhook:", json.dumps(data, indent=2))
    logfire.info("Processing incoming WhatsApp webhook...")
    # Check if it's a valid WhatsApp notification
    if 'object' in data and 'entry' in data and data['object'] == 'whatsapp_business_account':
        try:
            for entry in data['entry']:
                logfire.info("Start processing entry:", entry["id"])
                for change in entry['changes']:
                    if 'messages' in change['value']:
                        message = change['value']['messages'][0]
                        message_type = message['type']
                        phone_number = change['contacts']['wa_id']

                        if message_type == "image":
                            media_id = message['image']['id']
                            mime_type = message['image']['mime_type']
                            handle_media_message(media_id, mime_type, phone_number,None)

                        elif message_type == "document":
                            media_id = message['document']['id']
                            mime_type = message['document']['mime_type']
                            filename = message['document'].get('filename',
                                                               'downloaded_file')  # Use provided filename or a default
                            handle_media_message(media_id, mime_type,phone_number, filename)


                        # Add handlers for other types like 'audio', 'video', 'sticker' if needed
                logfire.info("Finished processing entry:", entry["id"])


        except (KeyError, IndexError) as e:
            logfire.error(f"Could not parse webhook payload: {e}")
            pass  # Not a message notification

def send_message(to, message, phone_number_id):
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message}
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        logfire.error(f"Failed to send message to {to}. Response: {response.status_code} {response.text}")
    else:
        logfire.info(f"Message sent to {to}.")



