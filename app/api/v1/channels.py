import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependancies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.channel import (ChannelCreate, ChannelResponse, ChannelMemberResponse)
from app.services.channel import channel_service

router = APIRouter(tags=["Channels"])

@router.post("/workspaces/{workspace_id}/channels",response_model=ChannelResponse,status_code=status.HTTP_201_CREATED)
async def create_channel(
    workspace_id: uuid.UUID,
    data: ChannelCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """ Create channel inside a workspace """
    try:
        channel = await channel_service.create_channel(
            session,workspace_id, user,data
        )
        return channel
    except ValueError as e:
        raise HTTPException(status_code=400,detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403,detail=str(e))
    
@router.get(
    "/workspaces/{workspace_id}/channels",
    response_model=list[ChannelResponse],
)
async def list_channels(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List channels in a workspace the user can see."""
    try:
        channels = await channel_service.list_channels(
            session, workspace_id, user
        )
        return channels
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get a specific channel."""
    try:
        channel = await channel_service.get_channel(session, channel_id, user)
        return channel
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
@router.post(
    "/channels/{channel_id}/join",
    response_model=ChannelMemberResponse,
)
async def join_channel(
    channel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Join a public channel."""
    try:
        membership = await channel_service.join_channel(
            session, channel_id, user
        )
        return membership
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.delete(
    "/channels/{channel_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave_channel(
    channel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Leave a channel."""
    try:
        await channel_service.leave_channel(session, channel_id, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


