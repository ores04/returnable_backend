import base64
import os
from datetime import time
from io import BytesIO
import logfire

import requests
from PIL import Image
from fastapi import HTTPException

from server.core.ai.agents.invoice_image_processing_using_llm import LLMImageProcessor
from server.core.ai.ai_clients.mistal_ai_client import MistralAiClient
from server.core.service.document_service.file_input_pipeline import process_text_input
from server.core.service.supabase_connectors.bucket_client import SupabaseBucketClientFactory
from server.core.service.supabase_connectors.supabase_client import get_supabase_service_role_client

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "not_set")
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "not_set")
API_VERSION = "v22.0"  # Update as needed
DEBUG = os.getenv("DEBUG", "false")
SHOULD_SAVE_LOCALLY = False

if VERIFY_TOKEN == "not_set" or ACCESS_TOKEN == "not_set":
    logfire.warning("Warning: WhatsApp tokens are not set. Please set the environment variables WHATSAPP_VERIFY_TOKEN and WHATSAPP_ACSESS_TOKEN.")


def handle_media_message(media_id, mime_type, phone_number, filename=None, to=None, phone_number_id=None):
    """
    Downloads media from WhatsApp and calls a processing function.
    """
    try:
        # 1. Get Media URL
        url_get_media = f"https://graph.facebook.com/{API_VERSION}/{media_id}"
        headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}

        response = requests.get(url_get_media, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        media_info = response.json()
        media_url = media_info['url']

        # 2. Download the actual file
        media_response = requests.get(media_url, headers=headers)
        media_response.raise_for_status()

        # 3. Save and Process the file
        if not filename:
            # Generate a filename if not provided (e.g., from image messages)
            extension = mime_type.split('/')[1]
            filename = f"{media_id}.{extension}"

        if DEBUG and SHOULD_SAVE_LOCALLY:
            save_path = write_file_to_disk(filename, media_response)
            logfire.info(f"Successfully downloaded and saved: {save_path}")

        # save file to supabase
        current_date = time().strftime(format="%Y_%m_%d")
        filename = f"{current_date}_{filename}"
        subabase_bucket_client = SupabaseBucketClientFactory.create_from_service_level_client(phone_number)
        subabase_bucket_client.add_document_to_bucket(media_response.content, filename, "user_files") # TODO check

        if mime_type == "application/pdf":
            b64_encoded_pdf = base64.b64encode(media_response.content)
            process_document(b64_encoded_pdf, filename, None, uuid=subabase_bucket_client.uuid)
        elif mime_type.startswith("image/"):
            b64_encoded_image = base64.b64encode(media_response.content)
            process_document(b64_encoded_image, filename, None, uuid=subabase_bucket_client.uuid)

        else:
            logfire.warning(f"Unsupported media type: {mime_type}")
            return

        if to is not None and phone_number_id is not None:
            message = f"Your document {filename} has been successfully processed and added to your account."
            send_message(to, message, phone_number_id)


    except requests.exceptions.RequestException as e:
        logfire.error(f"Error handling media message: {e}")

def process_document(contents, doc_title, token, uuid):
    mistal_client = MistralAiClient()
    llm_image_processor = LLMImageProcessor(mistal_client)
    text = llm_image_processor.process_image(image_base64=contents, is_pdf=False)
    if uuid is not None:
        client = get_supabase_service_role_client()
    else:
        client = None
    doc_id = process_text_input(text=text, title=doc_title, jwt_token=token, supabase_client=client, uuid=uuid)
    if doc_id is None:
        raise HTTPException(status_code=400, detail="Document not added")
    return doc_id

def write_file_to_disk(filename, media_response):
    # current dir
    current_dir = os.path.dirname(os.path.abspath(__file__))
    save_dir = os.path.join(current_dir, 'downloads')
    # check that the directory exists
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, filename)
    try:
        with open(save_path, 'xb') as f:
            f.write(media_response.content)
    except FileExistsError:
        logfire.info(f"File {save_path} already exists. Overwriting.")
        with open(save_path, 'wb') as f:
            f.write(media_response.content)
    return save_path

def send_message(to, message, phone_number_id):
    """Send a WhatsApp message using the WhatsApp Business API.

        to: the whatsapp id to send the message to
        message: The message text to send.
        phone_number_id: The ID of the WhatsApp Business phone number to send the message from

    """
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