from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    is_private: bool = Field(default=False)


class ChannelResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    is_private: bool
    is_archived: bool
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChannelMemberResponse(BaseModel):
    channel_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}