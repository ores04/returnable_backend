"""WhatsApp webhook message handler service."""
import logfire
from typing import Callable, Dict

from server.core.models.whatsapp_models import (
    WhatsAppWebhookPayload,
    MessageContext,
    MessageType,
)
from server.core.config.whatsapp_config import WhatsAppConfig
from server.core.service.supabase_connectors.supabase_client import (
    get_uuid_from_phone_number,
    is_premium_user_from_uuid,
)
from server.core.service.whatsapp_service.whatsapp_utils import send_message
from server.core.service.whatsapp_service.whatsapp_webhook_service import (
    handle_media_message,
    handle_text_message,
    handle_audio_message,
)


class WhatsAppWebhookHandler:
    """Handles processing of WhatsApp webhook payloads."""

    def __init__(self):
        """Initialize the webhook handler with message type handlers."""
        self.message_handlers: Dict[MessageType, Callable] = {
            MessageType.IMAGE: self._handle_image_message,
            MessageType.DOCUMENT: self._handle_document_message,
            MessageType.TEXT: self._handle_text_message,
            MessageType.AUDIO: self._handle_audio_message,
        }

    def process_webhook(self, data: dict) -> None:
        """
        Process incoming WhatsApp webhook data.

        Args:
            data: Raw webhook payload dictionary
        """
        logfire.info("Processing incoming WhatsApp webhook...")
        logfire.debug(f"Received WhatsApp request: {data}")

        # Validate webhook object type
        if not self._is_valid_webhook(data):
            logfire.warning(f"Invalid webhook object type: {data.get('object')}")
            return

        try:
            # Parse payload using Pydantic model
            payload = WhatsAppWebhookPayload(**data)

            for entry in payload.entry:
                logfire.info(f"Start processing entry: {entry.id}")
                self._process_entry(entry)
                logfire.info(f"Finished processing entry: {entry.id}")

        except Exception as e:
            logfire.error(f"Failed to process webhook payload: {e}")

    def _is_valid_webhook(self, data: dict) -> bool:
        """Check if the webhook payload is valid."""
        return (
            "object" in data
            and "entry" in data
            and data["object"] == WhatsAppConfig.WEBHOOK_OBJECT_TYPE
        )

    def _process_entry(self, entry) -> None:
        """
        Process a single webhook entry.

        Args:
            entry: Entry object from webhook payload
        """
        for change in entry.changes:
            # Ignore messages sent by self (no contacts field)
            if change.value.contacts is None or len(change.value.contacts) == 0:
                logfire.info("Ignoring message sent by myself.")
                continue

            # Process messages if present
            if change.value.messages:
                self._process_message(change)

    def _process_message(self, change) -> None:
        """
        Process a single message from a change object.

        Args:
            change: Change object containing message data
        """
        try:
            message = change.value.messages[0]
            phone_number = change.value.contacts[0].wa_id
            phone_number_id = change.value.metadata.phone_number_id
            message_from = message.from_

            # Create message context
            context = MessageContext(
                message=message,
                phone_number=phone_number,
                phone_number_id=phone_number_id,
                message_from=message_from,
            )

            # Dispatch to appropriate handler
            handler = self.message_handlers.get(context.message_type)
            if handler:
                handler(context)
            else:
                logfire.warning(f"No handler for message type: {context.message_type}")

        except (KeyError, IndexError) as e:
            logfire.error(f"Could not parse message: {e}")

    def _handle_image_message(self, context: MessageContext) -> None:
        """Handle image messages."""
        if not context.message.image:
            logfire.error("Image message missing image data")
            return

        handle_media_message(
            media_id=context.message.image.id,
            mime_type=context.message.image.mime_type,
            phone_number=context.phone_number,
            filename=None,
            to=context.message_from,
            phone_number_id=context.phone_number_id,
        )

    def _handle_document_message(self, context: MessageContext) -> None:
        """Handle document messages."""
        if not context.message.document:
            logfire.error("Document message missing document data")
            return

        handle_media_message(
            media_id=context.message.document.id,
            mime_type=context.message.document.mime_type,
            phone_number=context.phone_number,
            filename=context.message.document.filename or "downloaded_file",
            to=context.message_from,
            phone_number_id=context.phone_number_id,
        )

    def _handle_text_message(self, context: MessageContext) -> None:
        """Handle text messages."""
        if not context.message.text:
            logfire.error("Text message missing text data")
            return

        text = context.message.text.body
        logfire.info(f"Received text message from {context.phone_number}: {text}")

        handle_text_message(
            text=text,
            phone_number=context.phone_number,
            to=context.message_from,
            phone_number_id=context.phone_number_id,
        )

    def _handle_audio_message(self, context: MessageContext) -> None:
        """Handle audio messages (premium users only)."""
        if not context.message.audio:
            logfire.error("Audio message missing audio data")
            return

        # Check if user is premium
        if not self._is_user_premium(context.phone_number):
            logfire.info(f"User {context.phone_number} is not premium, sending upgrade message.")
            send_message(
                context.phone_number,
                "To use audio messages, please upgrade to premium.",
                context.phone_number_id,
            )
            return

        logfire.info(f"User {context.phone_number} is premium, processing audio message.")
        handle_audio_message(
            media_id=context.message.audio.id,
            mime_type=context.message.audio.mime_type,
            phone_number=context.phone_number,
            filename=None,
            to=context.message_from,
            phone_number_id=context.phone_number_id,
        )

    def _is_user_premium(self, phone_number: str) -> bool:
        """Check if the user is premium based on their phone number."""
        uuid = get_uuid_from_phone_number(phone_number)
        if uuid is None:
            return False
        return is_premium_user_from_uuid(uuid)
