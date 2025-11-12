import base64
import datetime
import os
from datetime import time
from functools import reduce

import logfire
import pytz

import requests
from fastapi import HTTPException

from server.core.ai.ai_clients.openai_client import OpenAIClient
from server.core.service.supabase_connectors.supabase_client import get_supabase_service_role_client, \
    get_uuid_from_phone_number
from server.core.service.supabase_connectors.supabase_tag_service import get_all_user_accessible_tags
from server.core.service.whatsapp_service.whatsapp_parent_todo_remidner_service import \
    handle_todo_or_reminder_extraction


from server.core.config.whatsapp_config import WhatsAppConfig

ACCESS_TOKEN = WhatsAppConfig.ACCESS_TOKEN
API_VERSION = "v22.0"  # Update as needed
DEBUG = os.getenv("DEBUG", "false")
SHOULD_SAVE_LOCALLY = False


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

async def handle_audio_message(media_id, mime_type, phone_number, filename=None, to=None, phone_number_id=None):
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
    await handle_text_message(text, phone_number, to, phone_number_id)





async def handle_text_message(text: str, phone_number, to=None, phone_number_id=None):
    uuid = get_uuid_from_phone_number(phone_number)
    possible_tags = None
    if any(keyword in text.lower() for keyword in
           ["tag", "kategorie", "category", "tags", "kategorien", "label", "labels"]):
        logfire.info(f"Received request with possible tags {phone_number}: {text}")
        client = get_supabase_service_role_client()
        possible_tags = get_all_user_accessible_tags(uuid, client)

    await handle_todo_or_reminder_extraction(text, phone_number, to, phone_number_id,uuid=uuid,possible_tags=possible_tags)
