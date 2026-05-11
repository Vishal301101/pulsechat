# app/schemas/workspace.py
from __future__ import annotations
import uuid
import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    slug: str | None = Field(default=None, min_length=2, max_length=50)

    @field_validator("slug", mode="before")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None:
            if not re.match(r'^[a-z0-9-]+$', v):
                raise ValueError(
                    "Slug can only contain lowercase letters, numbers, hyphens"
                )
        return v


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    owner_id: uuid.UUID
    created_at: datetime


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    workspace_id: uuid.UUID
    role: str
    created_at: datetime


class InviteMemberRequest(BaseModel):
    email: str
    role: str = Field(default="member", pattern="^(admin|member)$")

# Why a slug field? URLs like /workspaces/my-workspace are readable and shareable. UUIDs like /workspaces/a3f9b2c1-... are not. The slug is the human-friendly identifier. We auto-generate it from the name if the user doesn't provide one — "My   Workspace!!" → "my-workspace".
# Why @field_validator? Pydantic's Field(pattern=...) only works on strings that are provided. But slug is optional — it might be None. A validator lets you run custom logic: if slug is provided, validate its format; if not, leave it for the service to generate. You can't do this with Field() alone.
# Why pattern="^(admin|member)$" on role? This regex means the string must be exactly "admin" or "member" — nothing else. FastAPI + Pydantic validates this before your service code even runs. If someone sends "superuser", they get a 422 validation error automatically. Zero code needed in your service.