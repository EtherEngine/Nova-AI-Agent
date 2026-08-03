"""Service layer for chat history persistence (async SQLAlchemy)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Chat, Message, ToolCall
from app.schemas import ToolInvocation


async def create_chat(
    session: AsyncSession,
    *,
    title: str = "Neuer Chat",
    user_id: uuid.UUID | None = None,
) -> Chat:
    chat = Chat(title=title, user_id=user_id)
    session.add(chat)
    await session.flush()
    await session.refresh(chat)
    return chat


async def list_chats(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    include_archived: bool = False,
) -> Sequence[Chat]:
    owner = Chat.user_id.is_(None) if user_id is None else Chat.user_id == user_id
    stmt = select(Chat).where(owner).order_by(Chat.updated_at.desc())
    if not include_archived:
        stmt = stmt.where(Chat.archived.is_(False))
    return (await session.execute(stmt)).scalars().all()


async def get_chat(
    session: AsyncSession, chat_id: uuid.UUID, *, user_id: uuid.UUID | None = None
) -> Chat | None:
    stmt = (
        select(Chat)
        .where(Chat.id == chat_id)
        .options(selectinload(Chat.messages).selectinload(Message.tool_calls))
    )
    chat = (await session.execute(stmt)).scalar_one_or_none()
    if chat is not None and user_id is not None and chat.user_id != user_id:
        return None
    return chat


async def update_chat(
    session: AsyncSession,
    chat_id: uuid.UUID,
    *,
    title: str | None = None,
    archived: bool | None = None,
    user_id: uuid.UUID | None = None,
) -> Chat | None:
    chat = await session.get(Chat, chat_id)
    if chat is None or (user_id is not None and chat.user_id != user_id):
        return None
    if title is not None:
        chat.title = title
    if archived is not None:
        chat.archived = archived
    await session.flush()
    await session.refresh(chat)
    return chat


async def delete_chat(
    session: AsyncSession, chat_id: uuid.UUID, *, user_id: uuid.UUID | None = None
) -> bool:
    chat = await session.get(Chat, chat_id)
    if chat is None or (user_id is not None and chat.user_id != user_id):
        return False
    await session.delete(chat)
    return True


async def _next_sequence(session: AsyncSession, chat_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.max(Message.sequence), -1)).where(
        Message.chat_id == chat_id
    )
    return int((await session.execute(stmt)).scalar_one()) + 1


async def persist_turn(
    session: AsyncSession,
    chat_id: uuid.UUID,
    *,
    user_text: str,
    answer: str,
    tools: Sequence[ToolInvocation],
) -> bool:
    """Append a user message and the assistant reply (with tool calls).

    Returns ``False`` if the chat does not exist. Auto-titles a fresh chat from
    the first user message.
    """
    chat = await session.get(Chat, chat_id)
    if chat is None:
        return False

    sequence = await _next_sequence(session, chat_id)
    session.add(
        Message(chat_id=chat_id, role="user", content=user_text, sequence=sequence)
    )
    assistant = Message(
        chat_id=chat_id, role="assistant", content=answer, sequence=sequence + 1
    )
    for tool in tools:
        assistant.tool_calls.append(
            ToolCall(name=tool.name, arguments=tool.arguments, result=tool.result)
        )
    session.add(assistant)

    if chat.title == "Neuer Chat" and user_text.strip():
        chat.title = user_text.strip()[:200]

    await session.flush()
    return True
