"""Pydantic models for WhatsApp webhook payloads."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class MessageType(str, Enum):
    """Types of WhatsApp messages."""
    IMAGE = "image"
    DOCUMENT = "document"
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    STICKER = "sticker"


class MediaMessage(BaseModel):
    """Base model for media messages."""
    id: str
    mime_type: str


class DocumentMessage(MediaMessage):
    """Document message with optional filename."""
    filename: Optional[str] = "downloaded_file"


class TextMessage(BaseModel):
    """Text message model."""
    body: str


class Contact(BaseModel):
    """WhatsApp contact information."""
    wa_id: str


class Metadata(BaseModel):
    """Metadata for the message."""
    phone_number_id: str


class Message(BaseModel):
    """WhatsApp message model."""
    from_: str = Field(..., alias="from")
    type: MessageType
    text: Optional[TextMessage] = None
    image: Optional[MediaMessage] = None
    document: Optional[DocumentMessage] = None
    audio: Optional[MediaMessage] = None


class Value(BaseModel):
    """Value object containing messages and metadata."""
    messages: Optional[List[Message]] = None
    contacts: Optional[List[Contact]] = None
    metadata: Metadata


class Change(BaseModel):
    """Change object in webhook payload."""
    value: Value


class Entry(BaseModel):
    """Entry object in webhook payload."""
    id: str
    changes: List[Change]


class WhatsAppWebhookPayload(BaseModel):
    """Complete WhatsApp webhook payload."""
    object: str
    entry: List[Entry]


class MessageContext:
    """Context object containing all necessary information to process a message."""

    def __init__(
        self,
        message: Message,
        phone_number: str,
        phone_number_id: str,
        message_from: str,
    ):
        self.message = message
        self.phone_number = phone_number
        self.phone_number_id = phone_number_id
        self.message_from = message_from
        self.message_type = message.type

    @property
    def is_image(self) -> bool:
        return self.message_type == MessageType.IMAGE

    @property
    def is_document(self) -> bool:
        return self.message_type == MessageType.DOCUMENT

    @property
    def is_text(self) -> bool:
        return self.message_type == MessageType.TEXT

    @property
    def is_audio(self) -> bool:
        return self.message_type == MessageType.AUDIO
