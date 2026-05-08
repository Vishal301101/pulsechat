from __future__ import annotations

import uuid
from sqlalchemy import String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    workspace_memberships: Mapped[list[WorkspaceMember]] = relationship(
        "WorkspaceMember",
        back_populates="user",
    )
    sent_messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="sender",
        foreign_keys="Message.sender_id",
        primaryjoin="User.id == Message.sender_id",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


from app.models.workspace import WorkspaceMember  # noqa: E402
from app.models.message import Message            # noqa: E402