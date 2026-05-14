from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic import ConfigDict

class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1,max_length=4000)
    parent_id: uuid.UUID | None = None

class EditMessageRequest(BaseModel):
    content: str = Field(min_length=1,max_length=4000)

class AddReactionRequest(BaseModel):
    emoji: str = Field(min_length=1,max_length=10)

class ReactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    user_id: uuid.UUID
    emoji: str
    created_at: datetime

class MessageSenderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    avatar_url: str | None

class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel_id: uuid.UUID
    sender_id: uuid.UUID | None
    content: str
    seq_num: int
    parent_id: uuid.UUID | None
    is_edited: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None = None    # ← make optional
    reactions: list[ReactionResponse] = []
class PaginatedMessagesResponse(BaseModel):
    messages: list[MessageResponse]
    has_more: bool          
    next_cursor: int | None

