from __future__ import annotations
import uuid
from sqlalchemy import text,select,func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.channel import ChannelMember
from app.models.message import Message,Reaction
from app.models.user import User
from app.schemas.message import (SendMessageRequest,EditMessageRequest,AddReactionRequest)


async def _get_next_seq_num(
        session: AsyncSession,
        channel_id: uuid.UUID
        ) -> int:
    """
    Gets the next sequence number for a channel.
    Uses PostgreSQL's atomic increment — safe under concurrent inserts.
    Two users sending simultaneously CANNOT get the same seq_num.
    """
    seq_name = f"channel_seq_{str(channel_id).replace('-','_')}"
    await session.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1"))
    
    result = await session.execute(text(f"SELECT nextval('{seq_name}')"))
    return result.scalar()

class MessageService:

    async def send_message(
            self, 
            session: AsyncSession, 
            channel_id: uuid.UUID, 
            sender: User, 
            data: SendMessageRequest) -> Message :
        """
        sends a message to a channel
        Validates:
         - sender is a channel member
         - if reply , parent message exists in same channel
        """
        # 1. Verify sender is a channel member
        member = await self._get_membership(session,channel_id,sender.id)
        if not member:
            raise PermissionError("You are not a member of this channel")
        
        # 2. Validate parent message if this is a reply
        if data.parent_id:
            parent = await session.get(Message,data.parent_id)
            if not parent:
                raise ValueError("Parent message not found")
            if parent.channel_id != channel_id:
                raise ValueError("Cannot reply to a message in a different channel")
            if parent.parent_id is not None:
                raise ValueError("Cannot reply to a reply — one level threads only")
            
        # 3. Get next sequence number atomically    
        seq_num = await _get_next_seq_num(session,channel_id)

        # 4. Create and save the message
        message = Message(
            id = uuid.uuid4(),
            channel_id = channel_id,
            sender_id = sender.id,
            content = data.content,
            seq_num = seq_num,
            parent_id = data.parent_id
        )
        session.add(message)
        await session.flush()

        # Reload message with all relationships explicitly loaded
        # Can't use session.refresh() for relationships in async — use a fresh select
        result = await session.execute(
            select(Message)
            .where(Message.id == message.id)
            .options(selectinload(Message.reactions))
        )
        message = result.scalar_one()
        return message
    
    async def get_messages(
            self,
            session: AsyncSession,
            channel_id: uuid.UUID,
            user: User,
            limit: int = 50,
            before_seq: int | None = None,
    ) -> tuple[list[Message], bool]:
        
        """
        Returns paginated messages for a channel.
        before_seq = cursor — returns messages older than this seq_num.
        Returns (messages, has_more).
        """

        member = await self._get_membership(session, channel_id, user.id)
        if not member:
            raise ValueError("You are not member of this channel")
        
        query = (
            select(Message)
            .where(Message.channel_id == channel_id)
            .options(selectinload(Message.reactions))
            .order_by(Message.seq_num.desc())
            .limit(limit+1)
        )

        if before_seq is not None:
            query = query.where(Message.seq_num < before_seq)
        
        result = await session.execute(query)
        messages = list(result.scalars().all())

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit] # remove the extra row

        # Return in chronological order (oldest first)
        messages.reverse()
        return messages, has_more
    
    async def edit_message(
            self,
            session: AsyncSession,
            message_id: uuid.UUID,
            user: User,
            data: EditMessageRequest
    ) -> Message:
        """
        Edits a message. Only the original sender can edit.
        Cannot edit deleted messages.
        """
        message = await session.get(Message,message_id)
        if not message:
            raise ValueError("Message not found")
        if message.sender_id != user.id:
            raise PermissionError("You can only edit your own message")
        if message.is_deleted:
            raise ValueError("Cannot edit a deleted message")
        
        message.content = data.content
        message.is_edited = True
        await session.flush()
        return message
    
    async def delete_message(
            self,
            session: AsyncSession,
            message_id: uuid.UUID,
            user: User
    ) -> Message:
        """
        Soft deletes a message.
        Sender can delete their own. Channel admin can delete any.
        Content is cleared, is_deleted flag set.
        """

        message = await session.get(Message,message_id)
        if not message:
            raise ValueError("Message not found")

        # Check permission — sender or channel admin
        is_sender = message.sender_id == user.id
        is_admin = await self._is_channel_admin(
            session, message.channel_id, user.id
        )         
        if not is_sender and not is_admin:
            raise PermissionError(
                "You can only delete your own messages"
            )
        if message.is_deleted:
            raise ValueError("Message is already deleted")
        message.content = "This message was deleted"
        message.is_deleted = True
        await session.flush()

        return message
    
    async def add_reaction(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        user: User,
        data: AddReactionRequest,
    ) -> Reaction:
        """Adds an emoji reaction to a message."""
        message = await session.get(Message, message_id)
        if not message:
            raise ValueError("Message not found")

        if message.is_deleted:
            raise ValueError("Cannot react to a deleted message")

        # Check not already reacted with same emoji
        existing = await session.execute(
            select(Reaction).where(
                Reaction.message_id == message_id,
                Reaction.user_id == user.id,
                Reaction.emoji == data.emoji,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("You already reacted with this emoji")

        reaction = Reaction(
            id=uuid.uuid4(),
            message_id=message_id,
            user_id=user.id,
            emoji=data.emoji,
        )
        session.add(reaction)
        await session.flush()

        return reaction

    async def remove_reaction(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        user: User,
        emoji: str,
    ) -> None:
        """Removes an emoji reaction from a message."""
        result = await session.execute(
            select(Reaction).where(
                Reaction.message_id == message_id,
                Reaction.user_id == user.id,
                Reaction.emoji == emoji,
            )
        )
        reaction = result.scalar_one_or_none()
        if not reaction:
            raise ValueError("Reaction not found")

        await session.delete(reaction)
        await session.flush()

    async def search_messages(
            self,
            session: AsyncSession,
            channel_id: uuid.UUID,
            user: User,
            query: str,
            limit: int = 20
    ) -> Message:
        """
        Full-text search within a channel.
        Uses PostgreSQL ILIKE for simple case-insensitive search.
        (We'll upgrade to tsvector in a later optimization pass)
        """
        member = await self._get_membership(session, channel_id, user.id)
        if not member:
            raise PermissionError("You are not a member of this channel")
        
        result = await session.execute(
            select(Message)
            .where(
                Message.channel_id == channel_id,
                Message.is_deleted == False,
                Message.content.ilike(f"%{query}%"),
            )
            .options(selectinload(Message.reactions))
            .order_by(Message.seq_num.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def _get_membership(
        self,
        session: AsyncSession,
        channel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ChannelMember | None:
        result = await session.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _is_channel_admin(
        self,
        session: AsyncSession,
        channel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        result = await session.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
                ChannelMember.role == "ADMIN",
            )
        )
        return result.scalar_one_or_none() is not None
    
message_service = MessageService()


        
    


    

        

