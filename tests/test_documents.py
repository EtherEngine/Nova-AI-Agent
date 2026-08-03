"""RAG tests: extraction, chunking, and the documents API (mocked embeddings)."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.services.chunking import chunk_text
from app.services.extraction import ExtractionError, extract_text


def _fake_vector(text: str) -> list[float]:
    # Deterministic 2-D "embedding": distinguishes the two test topics.
    lowered = text.lower()
    return [1.0, 0.0] if "apfel" in lowered else [0.0, 1.0]


def _embeddings(*, model: str, input: list[str]) -> SimpleNamespace:  # noqa: A002
    return SimpleNamespace(
        data=[SimpleNamespace(embedding=_fake_vector(text)) for text in input]
    )


def _install_embeddings(client: TestClient) -> None:
    client.app.state.openai_client = SimpleNamespace(
        embeddings=SimpleNamespace(create=AsyncMock(side_effect=_embeddings)),
        close=AsyncMock(),
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
def docs_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[TestClient]:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'docs.db').as_posix()}"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    _init_schema(url)
    from app.main import app

    with TestClient(app) as client:
        _install_embeddings(client)
        yield client


@pytest.fixture
def nodb_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.main import app

    with TestClient(app) as client:
        yield client


def test_extract_text_from_txt() -> None:
    assert extract_text("a.txt", "text/plain", b"Hallo Welt") == "Hallo Welt"


def test_extract_unsupported_type() -> None:
    with pytest.raises(ExtractionError):
        extract_text("a.bin", "application/octet-stream", b"\x00\x01")


def test_chunking_overlap() -> None:
    text = "\n\n".join(f"Absatz {i} " + "x" * 300 for i in range(5))
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)


def _upload(client: TestClient, name: str, data: bytes, ctype: str):
    return client.post("/api/v1/documents", files={"file": (name, data, ctype)})


def test_upload_and_search(docs_client: TestClient) -> None:
    apple = _upload(docs_client, "apfel.txt", b"Der Apfel ist rot und suess.", "text/plain")
    pear = _upload(docs_client, "birne.md", b"# Birne\nDie Birne ist gruen.", "text/markdown")
    assert apple.status_code == 201 and apple.json()["chunk_count"] >= 1
    assert pear.status_code == 201

    listing = docs_client.get("/api/v1/documents")
    assert {d["filename"] for d in listing.json()} == {"apfel.txt", "birne.md"}

    result = docs_client.post("/api/v1/documents/search", json={"query": "Apfel"})
    assert result.status_code == 200
    hits = result.json()["hits"]
    assert hits and hits[0]["filename"] == "apfel.txt"
    assert hits[0]["score"] == pytest.approx(1.0)


def test_upload_unsupported_type_rejected(docs_client: TestClient) -> None:
    response = _upload(docs_client, "evil.exe", b"MZ...", "application/octet-stream")
    assert response.status_code == 415


def test_upload_empty_rejected(docs_client: TestClient) -> None:
    response = _upload(docs_client, "empty.txt", b"", "text/plain")
    assert response.status_code == 400


def test_upload_too_large_rejected(docs_client: TestClient) -> None:
    payload = b"a" * (2 * 1024 * 1024)  # 2 MB > 1 MB limit
    response = _upload(docs_client, "big.txt", payload, "text/plain")
    assert response.status_code == 413


def test_delete_document(docs_client: TestClient) -> None:
    doc_id = _upload(docs_client, "apfel.txt", b"Apfelkuchen Rezept.", "text/plain").json()["id"]
    assert docs_client.delete(f"/api/v1/documents/{doc_id}").status_code == 204
    assert docs_client.get("/api/v1/documents").json() == []


def test_documents_require_database(nodb_client: TestClient) -> None:
    assert nodb_client.get("/api/v1/documents").status_code == 503
