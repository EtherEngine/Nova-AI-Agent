"""Chat history API + persistence tests (async SQLite, mocked OpenAI)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


def _make_text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(output=[], output_text=text)


def _install_openai_mock(client: TestClient, responses: list[SimpleNamespace]) -> None:
    client.app.state.openai_client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=responses)),
        close=AsyncMock(),
    )


@pytest.fixture
def db_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[TestClient]:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'chats.db').as_posix()}"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("DATABASE_URL", url)

    from sqlalchemy.ext.asyncio import create_async_engine

    from app.db import Base

    async def _init() -> None:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_init())

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def nodb_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_create_and_list_chat(db_client: TestClient) -> None:
    created = db_client.post("/api/v1/chats", json={"title": "Mein Chat"})
    assert created.status_code == 201
    chat_id = created.json()["id"]

    listing = db_client.get("/api/v1/chats")
    assert listing.status_code == 200
    assert any(chat["id"] == chat_id for chat in listing.json())


def test_get_missing_chat_returns_404(db_client: TestClient) -> None:
    response = db_client.get("/api/v1/chats/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_rename_and_archive(db_client: TestClient) -> None:
    chat_id = db_client.post("/api/v1/chats", json={"title": "Alt"}).json()["id"]

    renamed = db_client.patch(f"/api/v1/chats/{chat_id}", json={"title": "Neu"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Neu"

    archived = db_client.patch(f"/api/v1/chats/{chat_id}", json={"archived": True})
    assert archived.status_code == 200 and archived.json()["archived"] is True

    assert all(c["id"] != chat_id for c in db_client.get("/api/v1/chats").json())
    with_archived = db_client.get("/api/v1/chats", params={"include_archived": True})
    assert any(c["id"] == chat_id for c in with_archived.json())


def test_delete_chat(db_client: TestClient) -> None:
    chat_id = db_client.post("/api/v1/chats", json={"title": "Weg"}).json()["id"]
    assert db_client.delete(f"/api/v1/chats/{chat_id}").status_code == 204
    assert db_client.get(f"/api/v1/chats/{chat_id}").status_code == 404


def test_chat_turn_is_persisted(db_client: TestClient) -> None:
    chat_id = db_client.post("/api/v1/chats", json={"title": "Neuer Chat"}).json()["id"]
    _install_openai_mock(db_client, [_make_text_response("Antwort")])

    response = db_client.post(
        "/api/v1/chat", json={"message": "Hallo Nova", "chat_id": chat_id}
    )
    assert response.status_code == 200

    detail = db_client.get(f"/api/v1/chats/{chat_id}").json()
    roles = [message["role"] for message in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "Hallo Nova"
    assert detail["messages"][1]["content"] == "Antwort"
    # First user message auto-titles the chat.
    assert detail["title"] == "Hallo Nova"


def test_chats_require_database(nodb_client: TestClient) -> None:
    assert nodb_client.get("/api/v1/chats").status_code == 503
