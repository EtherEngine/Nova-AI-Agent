"""FastAPI dependencies for authentication."""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import User
from app.db.session import get_session

from .security import decode_token
from .service import get_user_by_id

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Ungültige oder fehlende Anmeldedaten.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header or not header.startswith("Bearer "):
        return None
    return header[len("Bearer ") :].strip()


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    """Resolve the authenticated user or raise 401/503."""
    settings = _settings(request)
    if not settings.jwt_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentifizierung ist nicht konfiguriert.",
        )

    token = _bearer_token(request)
    if token is None:
        raise _CREDENTIALS_EXC

    try:
        payload = decode_token(
            token, secret=settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
    except jwt.PyJWTError as exc:
        raise _CREDENTIALS_EXC from exc

    if payload.get("type") != "access":
        raise _CREDENTIALS_EXC

    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise _CREDENTIALS_EXC from exc

    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXC
    return user


async def optional_current_user(request: Request) -> User | None:
    """Return the user if a valid token is present, else ``None`` (never raises).

    Used to scope resources by user when authenticated while still supporting
    anonymous access when authentication or the database is unavailable.
    """
    settings = getattr(request.app.state, "settings", None)
    database = getattr(request.app.state, "database", None)
    if settings is None or not settings.jwt_secret_key or database is None:
        return None

    token = _bearer_token(request)
    if token is None:
        return None

    try:
        payload = decode_token(
            token, secret=settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        if payload.get("type") != "access":
            return None
        user_id = uuid.UUID(str(payload.get("sub")))
        async with database.sessionmaker() as session:
            return await get_user_by_id(session, user_id)
    except (jwt.PyJWTError, ValueError):
        return None
