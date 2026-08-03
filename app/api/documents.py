"""Document upload, listing, deletion, and semantic search endpoints."""

from __future__ import annotations

import os
import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_openai_client
from app.auth.dependencies import optional_current_user
from app.config import Settings
from app.db.models import User
from app.db.rag_models import Document, DocumentChunk
from app.db.session import get_session
from app.schemas import (
    DocumentRead,
    SearchHitRead,
    SearchRequest,
    SearchResponse,
)
from app.services import rag
from app.services.extraction import ALLOWED_EXTENSIONS, ExtractionError

router = APIRouter(prefix="/documents", tags=["documents"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Dokument nicht gefunden."
)


def _user_id(user: User | None) -> uuid.UUID | None:
    return user.id if user is not None else None


def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _safe_name(filename: str | None) -> str:
    # Strip any directory components to prevent path traversal.
    base = os.path.basename(filename or "upload").replace("\\", "_").strip()
    return base or "upload"


async def _read_limited(file: UploadFile, max_mb: int) -> bytes:
    limit = max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Datei ist größer als {max_mb} MB.",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Datei ist leer."
        )
    return data


async def _chunk_count(session: AsyncSession, document_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(DocumentChunk).where(
        DocumentChunk.document_id == document_id
    )
    return int((await session.execute(stmt)).scalar_one())


def _to_read(document: Document, chunk_count: int) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        chunk_count=chunk_count,
        created_at=document.created_at,
    )


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    request: Request,
    session: AsyncSession = Depends(get_session),
    client: AsyncOpenAI = Depends(get_openai_client),
    user: User | None = Depends(optional_current_user),
) -> DocumentRead:
    settings: Settings = request.app.state.settings
    filename = _safe_name(file.filename)
    if _extension(filename) not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Nur PDF-, Markdown- und TXT-Dateien werden unterstützt.",
        )

    data = await _read_limited(file, settings.max_upload_mb)
    try:
        document = await rag.ingest_document(
            session,
            client,
            settings,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            data=data,
            user_id=_user_id(user),
        )
    except ExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return _to_read(document, await _chunk_count(session, document.id))


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
) -> list[DocumentRead]:
    documents = await rag.list_documents(session, user_id=_user_id(user))
    return [_to_read(document, len(document.chunks)) for document in documents]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
) -> None:
    if not await rag.delete_document(session, document_id, user_id=_user_id(user)):
        raise _NOT_FOUND


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    payload: SearchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    client: AsyncOpenAI = Depends(get_openai_client),
    user: User | None = Depends(optional_current_user),
) -> SearchResponse:
    settings: Settings = request.app.state.settings
    hits = await rag.search(
        session,
        client,
        settings,
        query=payload.query,
        user_id=_user_id(user),
        top_k=payload.top_k,
    )
    return SearchResponse(
        query=payload.query,
        hits=[
            SearchHitRead(
                document_id=hit.document_id,
                filename=hit.filename,
                chunk_index=hit.chunk_index,
                content=hit.content,
                score=hit.score,
            )
            for hit in hits
        ],
    )
