"""Chat history CRUD endpoints (require a configured database)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import optional_current_user
from app.db.models import Chat, User
from app.db.session import get_session
from app.schemas import (
    ChatCreate,
    ChatDetail,
    ChatSummary,
    ChatUpdate,
    MessageRead,
    ToolInvocation,
)
from app.services import chats as chat_service

router = APIRouter(prefix="/chats", tags=["chats"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat nicht gefunden.")


def _user_id(user: User | None) -> uuid.UUID | None:
    return user.id if user is not None else None


def _to_detail(chat: Chat) -> ChatDetail:
    messages = [
        MessageRead(
            id=message.id,
            role=message.role,
            content=message.content,
            sequence=message.sequence,
            created_at=message.created_at,
            tools=[
                ToolInvocation(name=tc.name, arguments=tc.arguments, result=tc.result)
                for tc in message.tool_calls
            ],
        )
        for message in chat.messages
    ]
    return ChatDetail(
        id=chat.id,
        title=chat.title,
        archived=chat.archived,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=messages,
    )


@router.post("", response_model=ChatSummary, status_code=status.HTTP_201_CREATED)
async def create_chat(
    payload: ChatCreate,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
) -> Chat:
    return await chat_service.create_chat(
        session, title=payload.title, user_id=_user_id(user)
    )


@router.get("", response_model=list[ChatSummary])
async def list_chats(
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
) -> list[Chat]:
    return list(
        await chat_service.list_chats(
            session, user_id=_user_id(user), include_archived=include_archived
        )
    )


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(
    chat_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
) -> ChatDetail:
    chat = await chat_service.get_chat(session, chat_id, user_id=_user_id(user))
    if chat is None:
        raise _NOT_FOUND
    return _to_detail(chat)


@router.patch("/{chat_id}", response_model=ChatSummary)
async def update_chat(
    chat_id: uuid.UUID,
    payload: ChatUpdate,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
) -> Chat:
    chat = await chat_service.update_chat(
        session,
        chat_id,
        title=payload.title,
        archived=payload.archived,
        user_id=_user_id(user),
    )
    if chat is None:
        raise _NOT_FOUND
    return chat


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
) -> None:
    if not await chat_service.delete_chat(session, chat_id, user_id=_user_id(user)):
        raise _NOT_FOUND
