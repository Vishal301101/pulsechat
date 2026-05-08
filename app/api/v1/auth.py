# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    RegisterRequest, LoginRequest,
    RefreshRequest, TokenResponse, UserResponse,
)
from app.services.auth import auth_service
from app.core.dependancies import get_current_user
from app.core.security import decode_token, create_access_token
from app.models.user import User
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create a new account and receive tokens."""
    try:
        user, tokens = await auth_service.register(session, data)
        return tokens
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_db),
):
    """Login and receive tokens."""
    try:
        user, tokens = await auth_service.login(session, data)
        return tokens
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest):
    """Exchange a refresh token for a new access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        payload = decode_token(data.refresh_token)

        # Must be a refresh token — not an access token
        if payload.get("type") != "refresh":
            raise credentials_exception

        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception

        # Issue a fresh access token only
        # Refresh token stays the same until it expires
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=data.refresh_token,
        )
    except JWTError:
        raise credentials_exception


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Returns the currently authenticated user.
    The Depends(get_current_user) handles all auth validation.
    If no valid token → 401 before this function even runs.
    """
    return current_user