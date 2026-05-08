# app/core/dependencies.py
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

# Tells FastAPI to expect "Authorization: Bearer <token>" header
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Injectable dependency. Validates JWT and returns the current user.
    Use: async def my_route(user: User = Depends(get_current_user))
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 1. Decode and verify the JWT
        payload = decode_token(credentials.credentials)

        # 2. Make sure it's an access token (not a refresh token)
        if payload.get("type") != "access":
            raise credentials_exception

        # 3. Extract user_id from the token
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # 4. Load the user from the database
    result = await session.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise credentials_exception

    return user

# Why load the user from DB on every request? Because the token is valid for 30 minutes. 
# If a user is deactivated at minute 5, they'd still have a valid token for 25 more minutes if you only read from the token.
# Loading from DB catches deactivated accounts in real time.
# Why Depends(bearer_scheme)? FastAPI's HTTPBearer() automatically extracts the token from the Authorization: Bearer xyz header and raises a 401 if the header is missing. 
# You don't parse headers manually.