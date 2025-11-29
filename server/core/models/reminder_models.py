"""Pydantic models for Reminder, Tag, and Task entities."""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ReminderTimeModel(BaseModel):
    """Model for reminder notification times."""
    id: Optional[int] = None
    reminder_id: Optional[int] = None
    reminder_time: datetime
    created_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ReminderTagModel(BaseModel):
    """Model for reminder tags."""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    name: Optional[str] = None
    color: Optional[str] = None
    user_id: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ReminderModel(BaseModel):
    """Model for reminders with nested times and tags."""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    event_time: Optional[datetime] = None
    reminder_text: Optional[str] = None
    user_id: Optional[str] = None
    done: bool = False
    reminder_times: List[ReminderTimeModel] = []
    tags: List[ReminderTagModel] = []

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ReminderTagConnectionModel(BaseModel):
    """Model for reminder-tag junction table."""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    reminder_id: int
    tag_id: int

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ReminderTagSharedModel(BaseModel):
    """Model for shared tags between users."""
    uuid: Optional[str] = None
    created_at: Optional[datetime] = None
    tag_id: Optional[int] = None
    user_shared_with: Optional[str] = None
    user_shares: Optional[str] = None
    share_accepted: Optional[bool] = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TagFilterModel(BaseModel):
    """Model for user tag filter preferences."""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    tag_id: int
    user_id: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ReturnTaskModel(BaseModel):
    """Model for return request tasks."""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    type: Optional[str] = None
    text: Optional[str] = None
    return_request_id: Optional[int] = None
    answer: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Request/Response models for API endpoints

class CreateReminderRequest(BaseModel):
    """Request model for creating a reminder."""
    reminder_text: Optional[str] = None
    event_time: Optional[datetime] = None
    user_id: str
    done: bool = False
    reminder_times: List[ReminderTimeModel] = []


class CreateReminderWithTagsRequest(BaseModel):
    """Request model for creating a reminder with tags."""
    reminder_text: Optional[str] = None
    event_time: Optional[datetime] = None
    user_id: str
    done: bool = False
    reminder_times: List[ReminderTimeModel] = []
    tag_ids: List[int] = []


class UpdateReminderRequest(BaseModel):
    """Request model for updating a reminder."""
    reminder_text: Optional[str] = None
    event_time: Optional[datetime] = None
    done: Optional[bool] = None
    reminder_times: Optional[List[ReminderTimeModel]] = None


class UpdateReminderWithTagsRequest(BaseModel):
    """Request model for updating a reminder with tags."""
    reminder_text: Optional[str] = None
    event_time: Optional[datetime] = None
    done: Optional[bool] = None
    reminder_times: Optional[List[ReminderTimeModel]] = None
    tag_ids: Optional[List[int]] = None


class CreateTagRequest(BaseModel):
    """Request model for creating a tag."""
    name: str
    color: Optional[str] = None
    user_id: str


class UpdateTagRequest(BaseModel):
    """Request model for updating a tag."""
    name: Optional[str] = None
    color: Optional[str] = None


class CreateTagConnectionRequest(BaseModel):
    """Request model for creating a tag connection."""
    reminder_id: int
    tag_id: int


class CreateSharedTagRequest(BaseModel):
    """Request model for creating a shared tag."""
    tag_id: int
    user_shared_with: str
    user_shares: str


class ClaimSharedTagRequest(BaseModel):
    """Request model for claiming a shared tag."""
    share_id: str
    user_id: str


class CreateTagFilterRequest(BaseModel):
    """Request model for creating a tag filter."""
    tag_id: int
    user_id: str


class ReplaceTagFiltersRequest(BaseModel):
    """Request model for replacing all user tag filters."""
    tag_ids: List[int]


class CreateTaskRequest(BaseModel):
    """Request model for creating a task."""
    type: Optional[str] = None
    text: Optional[str] = None
    return_request_id: Optional[int] = None
    answer: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    """Request model for updating a task."""
    type: Optional[str] = None
    text: Optional[str] = None
    answer: Optional[str] = None
