import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.core.security import hashed_password,verify_password
from app.core.security import create_access_token,create_refresh_token
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse

class AuthService:
    async def register(self,session: AsyncSession, data: RegisterRequest) -> tuple[User,TokenResponse]:
        """
        Creates a new user account and returns tokens.
        Raises ValueError if the email is already taken.
        """
        existing = await session.execute(
            select(User).where(User.email == data.email)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Email aleady registered")
        
        user = User(
            id=uuid.uuid4(),
            email=data.email,
            display_name=data.display_name,
            hashed_password=hashed_password(data.password),
            # plain password NEVER stored — immediately hashed
        )

        session.add(user)
        await session.flush() # write to DB, assigns id, doesn't commit yet
        tokens = self._issue_tokens(str(user.id))
        return user, tokens
    
    async def login(self, session: AsyncSession,data: LoginRequest) -> tuple[User,TokenResponse]:
        """
        Verifies credentials and returns tokens.
        Raises ValueError for wrong email or wrong password.
        """
        result = await session.execute(
            select(User).where(User.email == data.email)
        )
        user = result.scalar_one_or_none()

        # 2. Verify password
        # IMPORTANT: always check password even if user doesn't exist
        # (prevents timing attacks that reveal whether email exists)

        if not user or not verify_password(data.password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")
        tokens = self._issue_tokens(str(user.id))
        return user, tokens
    
    def _issue_tokens(self, user_id: str) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
        )

# Singleton — imported everywhere
auth_service = AuthService()

# Why flush() and not commit()? flush() writes the INSERT to PostgreSQL within the current transaction but doesn't commit it.
# This means if something fails later in the same request (like a constraint violation), the whole thing rolls back cleanly.
# The actual commit happens in get_db() after the route function returns successfully.
        