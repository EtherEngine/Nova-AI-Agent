"""Pydantic request/response models for the public API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_LENGTH = 4000
MAX_TITLE_LENGTH = 200


class ChatRequest(BaseModel):
    """Incoming chat request. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    # Optional: persist this turn into an existing chat (requires a database).
    chat_id: uuid.UUID | None = None


class ToolInvocation(BaseModel):
    """A single tool call performed during a chat turn."""

    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class ChatResponse(BaseModel):
    """Successful chat response."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    tools: list[ToolInvocation] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response."""

    model_config = ConfigDict(extra="forbid")

    status: str
    model: str


class ErrorResponse(BaseModel):
    """Safe error payload returned to clients."""

    model_config = ConfigDict(extra="forbid")

    detail: str


# --- Chat history -------------------------------------------------------------


class ChatCreate(BaseModel):
    """Payload to create a new chat."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="Neuer Chat", min_length=1, max_length=MAX_TITLE_LENGTH)


class ChatUpdate(BaseModel):
    """Partial update: rename and/or (un)archive a chat."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE_LENGTH)
    archived: bool | None = None


class ChatSummary(BaseModel):
    """Chat list item (no messages)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    """A persisted message including its tool invocations."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    sequence: int
    created_at: datetime
    tools: list[ToolInvocation] = Field(default_factory=list)


class ChatDetail(ChatSummary):
    """A chat together with its ordered messages."""

    messages: list[MessageRead] = Field(default_factory=list)


# --- Documents / RAG ----------------------------------------------------------


class DocumentRead(BaseModel):
    """Metadata for an uploaded, embedded document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    chunk_count: int
    created_at: datetime


class SearchRequest(BaseModel):
    """A semantic search query over uploaded documents."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    top_k: int | None = Field(default=None, ge=1, le=50)


class SearchHitRead(BaseModel):
    """A single retrieved chunk with its source."""

    model_config = ConfigDict(extra="forbid")

    document_id: uuid.UUID
    filename: str
    chunk_index: int
    content: str
    score: float


class SearchResponse(BaseModel):
    """Semantic search results with the originating query."""

    model_config = ConfigDict(extra="forbid")

    query: str
    hits: list[SearchHitRead] = Field(default_factory=list)
