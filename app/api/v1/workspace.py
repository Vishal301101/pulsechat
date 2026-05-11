import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependancies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.workspace import (
    WorkspaceCreate, WorkspaceResponse,
    WorkspaceMemberResponse, InviteMemberRequest,
)
from app.services.workspace import workspace_service

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)

async def create_workspace(
    data: WorkspaceCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Create a new workspace. Caller becomes the owner."""
    try:
        workspace = await workspace_service.create_workspace(session, user, data)
        return workspace
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all workspaces the current user belongs to."""
    workspaces = await workspace_service.list_workspaces(session, user)
    return workspaces


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get a specific workspace. User must be a member."""
    try:
        workspace = await workspace_service.get_workspace(
            session, workspace_id, user
        )
        return workspace
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
@router.post("/{workspace_id}/invite", response_model=WorkspaceMemberResponse)
async def invite_member(
    workspace_id: uuid.UUID,
    data: InviteMemberRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Invite a user to the workspace by email. Admin/owner only."""
    try:
        membership = await workspace_service.invite_member(
            session, workspace_id, user, data
        )
        return membership
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
)
async def list_members(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all members of a workspace."""
    try:
        members = await workspace_service.list_members(
            session, workspace_id, user
        )
        return members
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))




