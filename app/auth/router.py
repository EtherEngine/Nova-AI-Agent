"""Authentication endpoints: register, login, refresh, me, logout."""

from __future__ import annotations

import uuid
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import User
from app.db.session import get_session

from .dependencies import get_current_user
from .schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from .security import create_token, decode_token
from .service import authenticate_user, create_user, get_user_by_email, get_user_by_id

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_auth(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    if not settings.jwt_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentifizierung ist nicht konfiguriert.",
        )
    return settings


def _issue_tokens(user: User, settings: Settings) -> TokenResponse:
    access = create_token(
        user.id,
        secret=settings.jwt_secret_key or "",
        algorithm=settings.jwt_algorithm,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        token_type="access",
    )
    refresh = create_token(
        user.id,
        secret=settings.jwt_secret_key or "",
        algorithm=settings.jwt_algorithm,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        token_type="refresh",
    )
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    _require_auth(request)
    if await get_user_by_email(session, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-Mail ist bereits registriert.",
        )
    return await create_user(session, payload.email, payload.password)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    settings = _require_auth(request)
    user = await authenticate_user(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültige Anmeldedaten.",
        )
    return _issue_tokens(user, settings)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    settings = _require_auth(request)
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültiger Refresh-Token."
    )
    try:
        data = decode_token(
            payload.refresh_token,
            secret=settings.jwt_secret_key or "",
            algorithm=settings.jwt_algorithm,
        )
    except jwt.PyJWTError as exc:
        raise invalid from exc
    if data.get("type") != "refresh":
        raise invalid

    try:
        user_id = uuid.UUID(str(data.get("sub")))
    except ValueError as exc:
        raise invalid from exc

    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise invalid
    return _issue_tokens(user, settings)


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    """Stateless JWT logout: the client discards its tokens.

    Server-side revocation (token denylist) is prepared for the Redis-backed
    deployment and will be added there.
    """
    return None
