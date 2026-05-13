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
            parent = await session,get(Message,data.parent_id)
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
            id = uuid.UUID,
            channel_id = channel_id,
            sender_id = sender.id,
            content = data.content,
            seq_num = seq_num,
            parent_id = data.parent_id
        )
        session.add(message)
        await session.flush()

        # 5. Reload with relationships for the response
        await session.refresh(message)
        return message
    
    async def get_message(
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
        

        


    

        

