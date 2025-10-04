import os

import logfire
import requests


VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "not_set")
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "not_set")

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
