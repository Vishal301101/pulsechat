# app/api/v1/messages.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependancies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.message import (
    SendMessageRequest, EditMessageRequest,
    AddReactionRequest, MessageResponse,
    PaginatedMessagesResponse, ReactionResponse,
)
from app.services.message import message_service

router = APIRouter(tags=["Messages"])


@router.post(
    "/channels/{channel_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    channel_id: uuid.UUID,
    data: SendMessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Send a message to a channel."""
    try:
        message = await message_service.send_message(
            session, channel_id, user, data
        )
        return message
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/channels/{channel_id}/messages",
    response_model=PaginatedMessagesResponse,
)
async def get_messages(
    channel_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before_seq: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get paginated message history for a channel.
    Use before_seq as cursor for older messages.
    """
    try:
        messages, has_more = await message_service.get_messages(
            session, channel_id, user, limit, before_seq
        )
        next_cursor = messages[0].seq_num if has_more and messages else None
        return PaginatedMessagesResponse(
            messages=messages,
            has_more=has_more,
            next_cursor=next_cursor,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def edit_message(
    message_id: uuid.UUID,
    data: EditMessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Edit your own message."""
    try:
        message = await message_service.edit_message(
            session, message_id, user, data
        )
        return message
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/messages/{message_id}",
    response_model=MessageResponse,
)
async def delete_message(
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Soft delete a message."""
    try:
        message = await message_service.delete_message(
            session, message_id, user
        )
        return message
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/messages/{message_id}/reactions",
    response_model=ReactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_reaction(
    message_id: uuid.UUID,
    data: AddReactionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Add an emoji reaction to a message."""
    try:
        reaction = await message_service.add_reaction(
            session, message_id, user, data
        )
        return reaction
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/messages/{message_id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_reaction(
    message_id: uuid.UUID,
    emoji: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Remove your reaction from a message."""
    try:
        await message_service.remove_reaction(
            session, message_id, user, emoji
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/channels/{channel_id}/messages/search",
    response_model=list[MessageResponse],
)
async def search_messages(
    channel_id: uuid.UUID,
    q: str = Query(min_length=2),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Search messages in a channel."""
    try:
        messages = await message_service.search_messages(
            session, channel_id, user, q, limit
        )
        return messages
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))