from __future__ import annotations

# By default, Python evaluates type hints immediately, which can cause errors if a type refers to a class that hasn't been defined yet.
# This import converts all type annotations into strings, avoiding immediate evaluation at import time.
import re
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel, ChannelMember
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.workspace import WorkspaceCreate, InviteMemberRequest

def _generate_slug(name: str) -> str:
    """
    Converts a workspace name to a URL-friendly slug.
    "My   Workspace!!" → "my-workspace"
    
    """
    slug = name.lower()                        # lowercase everything
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)  # remove special chars
    slug = re.sub(r'[\s]+', '-', slug)         # spaces → hyphens
    slug = re.sub(r'-+', '-', slug)            # multiple hyphens → one
    slug = slug.strip('-')                     # remove leading/trailing hyphens
    return slug

class WorkspaceService:
    async def create_workspace(
            self,
            session: AsyncSession,
            owner: User,
            data: WorkspaceCreate,
    ) -> Workspace:
         """
         Creates a workspace and automatically makes the creator the owner.
         Two things happen atomically:
          1. Insert workspace row
          2. Insert workspace_member row (owner)
          If either fails, both roll back.
         """
         slug = data.slug or _generate_slug(data.name)
         existing = await session.execute(select(Workspace).where(Workspace.slug == slug))
         if existing.scalar_one_or_none():
             slug = f"{slug}-{str(uuid.uuid4())[:8]}"

         workspace = Workspace(
            id=uuid.uuid4(),
            name=data.name,
            slug=slug,
            description=data.description,
            owner_id=owner.id,
         )

         session.add(workspace)
         await session.flush()
         # Automatically add creator as owner member
         # Why? Because the owner needs to be in workspace_members
         # to be found when listing members, checking permissions etc.
         membership = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner.id,
            role=WorkspaceRole.OWNER,
         )
         session.add(membership)
         await session.flush()

         return workspace
    
    async def get_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user: User,
    ) -> Workspace:
        """
        Returns a workspace only if the requesting user is a member.
        Raises ValueError if not found or not a member.
        """
        workspace = await session.get(Workspace, workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")

        # Check membership
        member = await self._get_membership(session, workspace_id, user.id)
        if not member:
            raise ValueError("You are not a member of this workspace")

        return workspace
    
    async def list_workspaces(self,session: AsyncSession,user: User) -> list[Workspace]:
        """
        Returns all workspaces the user belongs to.
        Joins workspace_members → workspaces to find them.
        """
        result = await session.execute(
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user.id)
            .order_by(Workspace.created_at.desc())
        )
        return list(result.scalars().all())
    

    async def invite_member(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        inviter: User,
        data: InviteMemberRequest,
    ) -> WorkspaceMember:
        """
        Invites a user to a workspace by their email.
        Only admins and owners can invite.
        """
        # 1. Check inviter has permission
        inviter_membership = await self._get_membership(
            session, workspace_id, inviter.id
        )
        if not inviter_membership:
            raise ValueError("You are not a member of this workspace")

        if inviter_membership.role not in (
            WorkspaceRole.OWNER, WorkspaceRole.ADMIN
        ):
            raise PermissionError("Only admins and owners can invite members")

        # 2. Find the user being invited
        result = await session.execute(
            select(User).where(User.email == data.email)
        )
        invitee = result.scalar_one_or_none()
        if not invitee:
            raise ValueError(f"No user found with email {data.email}")

        # 3. Check they're not already a member
        existing = await self._get_membership(session, workspace_id, invitee.id)
        if existing:
            raise ValueError("User is already a member of this workspace")

        # 4. Create membership
        membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=invitee.id,
            role=WorkspaceRole(data.role),
        )
        session.add(membership)
        await session.flush()

        return membership
    
    async def list_members(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user: User,
    ) -> list[WorkspaceMember]:
        """Returns all members of a workspace."""
        # Verify requester is a member
        if not await self._get_membership(session, workspace_id, user.id):
            raise ValueError("You are not a member of this workspace")

        result = await session.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
        )
        return list(result.scalars().all())

    async def _get_membership(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceMember | None:
        """
        Internal helper — checks if a user is a member of a workspace.
        Returns the membership row or None.
        Used everywhere we need permission checks.
        """
        result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


workspace_service = WorkspaceService()

# Why flush() instead of commit() after creating the workspace? flush() sends the INSERT to PostgreSQL and gets the auto-generated workspace.id back, but keeps the transaction open. You need that id to create the WorkspaceMember row in the same transaction. If you committed after the workspace, and then the membership insert failed, you'd have a workspace with no owner — a broken state. flush() keeps both writes in one atomic transaction. The commit happens in get_db() after the route succeeds.
# Why check membership in get_workspace? Because workspaces are private. User B should never be able to see User A's workspace just by guessing a UUID. Every read of workspace data must verify membership first. This is called "authorization" — not just "are you logged in" (authentication) but "are you allowed to see this specific thing."
# Why PermissionError and ValueError separately? ValueError means "the data is wrong" (workspace not found, user doesn't exist). PermissionError means "the data is fine but you're not allowed." The route layer maps these to different HTTP status codes — 400/404 for ValueError, 403 for PermissionError. Clear separation keeps your error handling predictable.

        
