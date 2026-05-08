# app/models/message.py
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, BigInteger, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.channel import Channel


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    __table_args__ = (
        Index("ix_messages_channel_seq", "channel_id", "seq_num"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(  # ← | None added
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seq_num: Mapped[int] = mapped_column(BigInteger, nullable=False)

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="messages")

    sender: Mapped["User | None"] = relationship(  # ← | None added
        back_populates="sent_messages",
        foreign_keys=[sender_id],        # ← explicitly tell SQLAlchemy which FK
    )

    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )

    replies: Mapped[list["Message"]] = relationship(
        foreign_keys="Message.parent_id",   # ← string form fixes self-ref ambiguity
        primaryjoin="Message.parent_id == Message.id",
        back_populates="parent",
    )

    parent: Mapped["Message | None"] = relationship(  # ← other side of replies
        foreign_keys="Message.parent_id",
        primaryjoin="Message.parent_id == Message.id",
        back_populates="replies",
        remote_side="Message.id",           # ← tells SQLAlchemy which side is "one"
    )

    def __repr__(self) -> str:
        return f"<Message {self.id}>"


class Reaction(Base, TimestampMixin):
    __tablename__ = "reactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    emoji: Mapped[str] = mapped_column(String(10), nullable=False)

    message: Mapped["Message"] = relationship(back_populates="reactions")