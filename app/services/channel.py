# app/services/channel.py
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel, ChannelMember, ChannelRole
from app.models.user import User
from app.models.workspace import WorkspaceMember, WorkspaceRole
from app.schemas.channel import ChannelCreate


class ChannelService:

    async def create_channel(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        creator: User,
        data: ChannelCreate,
    ) -> Channel:
        """
        Creates a channel inside a workspace.
        Creator must be a workspace member.
        Creator is automatically added as channel admin.
        """
        # 1. Verify creator is a workspace member
        ws_member = await self._get_ws_membership(
            session, workspace_id, creator.id
        )
        if not ws_member:
            raise ValueError("You are not a member of this workspace")

        # 2. Check channel name is unique within workspace
        existing = await session.execute(
            select(Channel).where(
                Channel.workspace_id == workspace_id,
                Channel.name == data.name,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(
                f"Channel #{data.name} already exists in this workspace"
            )

        # 3. Create the channel
        channel = Channel(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            name=data.name.lower().replace(" ", "-"),  # normalize name
            description=data.description,
            is_private=data.is_private,
            created_by=creator.id,
        )
        session.add(channel)
        await session.flush()  # need channel.id for membership

        # 4. Add creator as channel admin automatically
        membership = ChannelMember(
            channel_id=channel.id,
            user_id=creator.id,
            role=ChannelRole.ADMIN,
        )
        session.add(membership)
        await session.flush()

        return channel

    async def list_channels(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user: User,
    ) -> list[Channel]:
        """
        Returns channels the user can see:
        - All public channels in the workspace
        - Private channels only if user is a member
        """
        # Get all public channels
        public_result = await session.execute(
            select(Channel).where(
                Channel.workspace_id == workspace_id,
                Channel.is_private == False,
                Channel.is_archived == False,
            )
        )
        public_channels = list(public_result.scalars().all())

        # Get private channels user is a member of
        private_result = await session.execute(
            select(Channel)
            .join(ChannelMember, ChannelMember.channel_id == Channel.id)
            .where(
                Channel.workspace_id == workspace_id,
                Channel.is_private == True,
                Channel.is_archived == False,
                ChannelMember.user_id == user.id,
            )
        )
        private_channels = list(private_result.scalars().all())

        # Merge and deduplicate
        seen = set()
        result = []
        for ch in public_channels + private_channels:
            if ch.id not in seen:
                seen.add(ch.id)
                result.append(ch)

        return sorted(result, key=lambda c: c.created_at)

    async def join_channel(
        self,
        session: AsyncSession,
        channel_id: uuid.UUID,
        user: User,
    ) -> ChannelMember:
        """
        User joins a public channel.
        Cannot join private channels this way — need an invite.
        """
        channel = await session.get(Channel, channel_id)
        if not channel:
            raise ValueError("Channel not found")

        if channel.is_private:
            raise PermissionError(
                "Cannot join a private channel — ask an admin to invite you"
            )

        if channel.is_archived:
            raise ValueError("Cannot join an archived channel")

        # Check not already a member
        existing = await self._get_ch_membership(session, channel_id, user.id)
        if existing:
            raise ValueError("You are already a member of this channel")

        # Verify user is a workspace member
        ws_member = await self._get_ws_membership(
            session, channel.workspace_id, user.id
        )
        if not ws_member:
            raise ValueError("You must be a workspace member to join channels")

        membership = ChannelMember(
            channel_id=channel_id,
            user_id=user.id,
            role=ChannelRole.MEMBER,
        )
        session.add(membership)
        await session.flush()

        return membership

    async def leave_channel(
        self,
        session: AsyncSession,
        channel_id: uuid.UUID,
        user: User,
    ) -> None:
        """Removes user from a channel."""
        membership = await self._get_ch_membership(session, channel_id, user.id)
        if not membership:
            raise ValueError("You are not a member of this channel")

        await session.delete(membership)
        await session.flush()

    async def get_channel(
        self,
        session: AsyncSession,
        channel_id: uuid.UUID,
        user: User,
    ) -> Channel:
        """Returns a channel if user has access."""
        channel = await session.get(Channel, channel_id)
        if not channel:
            raise ValueError("Channel not found")

        if channel.is_private:
            membership = await self._get_ch_membership(
                session, channel_id, user.id
            )
            if not membership:
                raise PermissionError("You are not a member of this channel")

        return channel

    # ─── Internal helpers ─────────────────────────────────────────

    async def _get_ws_membership(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceMember | None:
        result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_ch_membership(
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


channel_service = ChannelService()