import base64
import datetime
import os
from datetime import time
from functools import reduce

import logfire
import pytz

import requests
from fastapi import HTTPException

from server.core.ai.agents.invoice_image_processing_using_llm import LLMImageProcessor
from server.core.ai.ai_clients.mistal_ai_client import MistralAiClient
from server.core.ai.ai_clients.openai_client import OpenAIClient
from server.core.service.document_service.file_input_pipeline import process_text_input
from server.core.service.supabase_connectors.bucket_client import SupabaseBucketClientFactory
from server.core.service.supabase_connectors.supabase_client import get_supabase_service_role_client, \
    get_uuid_from_phone_number
from server.core.service.supabase_connectors.supabase_tag_service import get_all_user_accessible_tags
from server.core.service.whatsapp_service.whatsapp_reminder_service import reminder_service, get_user_timezone
from server.core.service.whatsapp_service.whatsapp_todo_service import todo_service
from server.core.service.whatsapp_service.whatsapp_utils import send_message

from server.core.config.whatsapp_config import WhatsAppConfig

ACCESS_TOKEN = WhatsAppConfig.ACCESS_TOKEN
API_VERSION = "v22.0"  # Update as needed
DEBUG = os.getenv("DEBUG", "false")
SHOULD_SAVE_LOCALLY = False


def handle_media_message(media_id, mime_type, phone_number, filename=None, to=None, phone_number_id=None):
    """
    Downloads media from WhatsApp and calls a processing function.
    """
    try:
        # 1. Get Media URL
        media_response = download_media_file(media_id)

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


def download_media_file(media_id):
    url_get_media = f"https://graph.facebook.com/{API_VERSION}/{media_id}"
    headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
    response = requests.get(url_get_media, headers=headers)
    response.raise_for_status()  # Raise an exception for bad status codes
    media_info = response.json()
    media_url = media_info['url']
    # 2. Download the actual file
    media_response = requests.get(media_url, headers=headers)
    media_response.raise_for_status()
    return media_response


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

def handle_audio_message(media_id, mime_type, phone_number, filename=None, to=None, phone_number_id=None):
    logfire.info("Handling audio message")
    # download the audio file
    try:
        media_response = download_media_file(media_id)

        if not filename:
            extension = mime_type.split('/')[1]
            filename = f"{media_id}.{extension}"

        if DEBUG and SHOULD_SAVE_LOCALLY:
            save_path = write_file_to_disk(filename, media_response)
            logfire.info(f"Successfully downloaded and saved audio: {save_path}")
    except requests.exceptions.RequestException as e:
        logfire.error(f"Error handling audio message: {e}")
        return

    # transcribe the audio file
    openai_client = OpenAIClient()
    text = openai_client.get_text_from_audio(media_response.content)
    if text is None:
        logfire.error("Failed to transcribe audio")
        return

    logfire.info(f"Transcribed audio to text: {text}")
    handle_text_message(text, phone_number, to, phone_number_id)





def handle_text_message(text: str, phone_number, to=None, phone_number_id=None):

    if any(keyword in text.lower() for keyword in ["erinner", "erinnere", "remind me", "remind", "erinnerung"]):
        logfire.info(f"Received reminder request {phone_number}: {text}")

        uuid = get_uuid_from_phone_number(phone_number)
        possible_tags = None
        if any(keyword in text.lower() for keyword in ["tag", "kategorie", "category", "tags", "kategorien", "label", "labels"]):
            logfire.info(f"Received request with possible tags {phone_number}: {text}")
            client = get_supabase_service_role_client()
            possible_tags = get_all_user_accessible_tags(uuid, client)

        reminder = reminder_service(text, phone_number, uuid, possible_tags)
        tz_str = get_user_timezone(uuid)
        local_tz = pytz.timezone(tz_str)
        pretty_reminder_time_list = [datetime.datetime.fromisoformat(reminder_time).astimezone(
            local_tz).strftime("%d.%m.%Y %H:%M") for reminder_time in
                                     reminder.reminder_time]
        message = f"Du wirst am {reduce(lambda x,y: str(x) + "," + str(y), pretty_reminder_time_list, "") if len(pretty_reminder_time_list) > 1 else pretty_reminder_time_list[0]} erinnert. "
        send_message(to,message,  phone_number_id)

    # handle todo messages
    elif any(keyword in text.lower() for keyword in ["todo", "aufgabe", "task", "merk dir"]):
        logfire.info(f"Received todo request {phone_number}: {text}")

        uuid = get_uuid_from_phone_number(phone_number)
        possible_tags = None
        if any(keyword in text.lower() for keyword in ["tag", "kategorie", "category", "tags", "kategorien", "label", "labels"]):
            logfire.info(f"Received request with possible tags {phone_number}: {text}")
            client = get_supabase_service_role_client()
            possible_tags = get_all_user_accessible_tags(uuid, client)

        todo = todo_service(text, phone_number, uuid, possible_tags)
        tz_str = get_user_timezone(uuid)
        local_tz = pytz.timezone(tz_str)

        # Create confirmation message with to_do text
        if todo.event_time:
            pretty_event_time = datetime.datetime.fromisoformat(todo.event_time).astimezone(
                local_tz).strftime("%d.%m.%Y %H:%M")
            message = f"Todo erstellt: \"{todo.todo_text}\" (fällig am {pretty_event_time})"
        else:
            message = f"Todo erstellt: \"{todo.todo_text}\""

        send_message(to, message, phone_number_id)



