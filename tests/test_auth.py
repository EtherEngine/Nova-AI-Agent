"""Authentication tests: hashing, tokens, and the auth API (async SQLite)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth.security import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)


def _init_schema(url: str) -> None:
    import asyncio

    from sqlalchemy.ext.asyncio import create_async_engine

    from app.db import Base

    async def _run() -> None:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_run())


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[TestClient]:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'auth.db').as_posix()}"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret")
    _init_schema(url)
    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def nosecret_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[TestClient]:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'auth2.db').as_posix()}"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    _init_schema(url)
    from app.main import app

    with TestClient(app) as client:
        yield client


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("super-secret-123")
    assert hashed != "super-secret-123"
    assert verify_password("super-secret-123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_token(
        user_id,
        secret="s",
        algorithm="HS256",
        expires_delta=timedelta(minutes=5),
        token_type="access",
    )
    payload = decode_token(token, secret="s", algorithm="HS256")
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def _register(client: TestClient, email: str = "user@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "hunter2hunter"}
    )
    assert response.status_code == 201


def test_register_login_me_flow(auth_client: TestClient) -> None:
    _register(auth_client)

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "hunter2hunter"},
    )
    assert login.status_code == 200
    tokens = login.json()
    access = tokens["access_token"]

    me = auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_duplicate_registration_rejected(auth_client: TestClient) -> None:
    _register(auth_client)
    again = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "hunter2hunter"},
    )
    assert again.status_code == 400


def test_login_wrong_password(auth_client: TestClient) -> None:
    _register(auth_client)
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "wrongwrong"},
    )
    assert login.status_code == 401


def test_me_requires_valid_token(auth_client: TestClient) -> None:
    assert auth_client.get("/api/v1/auth/me").status_code == 401
    bad = auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}
    )
    assert bad.status_code == 401


def test_refresh_flow(auth_client: TestClient) -> None:
    _register(auth_client)
    tokens = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "hunter2hunter"},
    ).json()

    refreshed = auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()

    # An access token must not be accepted as a refresh token.
    reused = auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert reused.status_code == 401


def test_auth_disabled_without_secret(nosecret_client: TestClient) -> None:
    response = nosecret_client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "hunter2hunter"},
    )
    assert response.status_code == 503
