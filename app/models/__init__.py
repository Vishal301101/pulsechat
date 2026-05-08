from app.models.base import TimestampMixin
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.channel import Channel, ChannelMember
from app.models.message import Message, Reaction

__all__ = [
    "TimestampMixin",
    "User",
    "Workspace",
    "WorkspaceMember",
    "Channel",
    "ChannelMember",
    "Message",
    "Reaction",
]

#All the relationships in PulseChat — in plain English
#One workspace contains zero or many channels
#One user sends zero or many messages
#One channel holds zero or many messages
#One message receives zero or many reactions
#One message has zero or many replies (pointing back to itself)
#One user joins zero or many workspaces (via workspace_members)
#One user joins zero or many channels (via channel_members)