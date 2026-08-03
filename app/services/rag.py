"""RAG pipeline: ingest documents and run semantic search.

Pipeline: extract text -> chunk -> embed -> store chunks (pgvector on Postgres).
Search embeds the query and ranks chunks by cosine similarity. Retrieval is
computed in Python so it works identically on SQLite (tests) and PostgreSQL;
the pgvector column + HNSW index (see migration) enable the operator-based
retrieval path for large production datasets.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from pathlib import Path

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.rag_models import Document, DocumentChunk

from .chunking import chunk_text
from .embeddings import embed_query, embed_texts
from .extraction import extract_text


@dataclass(slots=True)
class SearchHit:
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    content: str
    score: float


def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _store_file(settings: Settings, data: bytes, filename: str) -> str:
    """Persist the raw upload under a random, path-traversal-safe name."""
    directory = Path(settings.upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{_extension(filename)}"
    path = directory / safe_name
    path.write_bytes(data)
    return str(path)


async def ingest_document(
    session: AsyncSession,
    client: AsyncOpenAI,
    settings: Settings,
    *,
    filename: str,
    content_type: str,
    data: bytes,
    user_id: uuid.UUID | None = None,
) -> Document:
    """Extract, chunk, embed, and persist a document with its chunks."""
    text = extract_text(filename, content_type, data)
    chunks = chunk_text(text)
    embeddings = await embed_texts(client, settings.embedding_model, chunks)

    storage_path = _store_file(settings, data, filename)
    document = Document(
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        storage_path=storage_path,
    )
    for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
        document.chunks.append(
            DocumentChunk(chunk_index=index, content=chunk, embedding=embedding)
        )
    session.add(document)
    await session.flush()
    await session.refresh(document)
    return document


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def search(
    session: AsyncSession,
    client: AsyncOpenAI,
    settings: Settings,
    *,
    query: str,
    user_id: uuid.UUID | None = None,
    top_k: int | None = None,
) -> list[SearchHit]:
    """Embed the query and return the most similar chunks with their sources."""
    k = top_k or settings.rag_top_k
    query_embedding = await embed_query(client, settings.embedding_model, query)

    owner = (
        Document.user_id.is_(None) if user_id is None else Document.user_id == user_id
    )
    stmt = (
        select(DocumentChunk)
        .join(Document)
        .where(owner)
        .options(selectinload(DocumentChunk.document))
    )
    chunks = (await session.execute(stmt)).scalars().all()

    scored = [
        SearchHit(
            document_id=chunk.document_id,
            filename=chunk.document.filename,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=_cosine_similarity(query_embedding, chunk.embedding),
        )
        for chunk in chunks
    ]
    scored.sort(key=lambda hit: hit.score, reverse=True)
    return scored[:k]


async def list_documents(
    session: AsyncSession, *, user_id: uuid.UUID | None = None
) -> list[Document]:
    owner = (
        Document.user_id.is_(None) if user_id is None else Document.user_id == user_id
    )
    stmt = (
        select(Document)
        .where(owner)
        .order_by(Document.created_at.desc())
        .options(selectinload(Document.chunks))
    )
    return list((await session.execute(stmt)).scalars().all())


async def delete_document(
    session: AsyncSession, document_id: uuid.UUID, *, user_id: uuid.UUID | None = None
) -> bool:
    document = await session.get(Document, document_id)
    if document is None or (user_id is not None and document.user_id != user_id):
        return False
    if document.storage_path:
        Path(document.storage_path).unlink(missing_ok=True)
    await session.delete(document)
    return True
