# app/models/channel.py
import uuid
from sqlalchemy import String, Text, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.db.session import Base
from app.models.base import TimestampMixin


class ChannelRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="channels")
    members: Mapped[list["ChannelMember"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )


class ChannelMember(Base, TimestampMixin):
    __tablename__ = "channel_members"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[ChannelRole] = mapped_column(
        SAEnum(ChannelRole),
        default=ChannelRole.MEMBER,
        nullable=False,
    )

    channel: Mapped["Channel"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()