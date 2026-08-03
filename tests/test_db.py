"""Database model tests using an in-memory async SQLite database.

These verify the ORM models, relationships, and cascade behaviour without
requiring a running PostgreSQL instance.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, Chat, Message, ToolCall, User


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
    await engine.dispose()


async def test_create_chat_with_messages_and_tools(session: AsyncSession) -> None:
    user = User(email="tester@example.com")
    chat = Chat(title="Rechenchat", user=user)
    user_msg = Message(role="user", content="145 / 5?", sequence=0)
    assistant_msg = Message(role="assistant", content="29", sequence=1)
    assistant_msg.tool_calls.append(
        ToolCall(
            name="calculate",
            arguments={"operation": "divide", "a": 145, "b": 5},
            result={"ok": True, "data": {"result": 29}},
        )
    )
    chat.messages.extend([user_msg, assistant_msg])
    session.add(chat)
    await session.commit()

    loaded = (await session.execute(select(Chat))).scalar_one()
    assert loaded.title == "Rechenchat"
    assert loaded.user is not None and loaded.user.email == "tester@example.com"
    assert [message.role for message in loaded.messages] == ["user", "assistant"]
    assert loaded.messages[1].tool_calls[0].name == "calculate"
    assert loaded.messages[1].tool_calls[0].result["data"]["result"] == 29


async def test_cascade_delete_removes_children(session: AsyncSession) -> None:
    chat = Chat(title="Temp")
    message = Message(role="user", content="hi", sequence=0)
    message.tool_calls.append(ToolCall(name="calculate", arguments={}, result={}))
    chat.messages.append(message)
    session.add(chat)
    await session.commit()

    await session.delete(chat)
    await session.commit()

    assert (await session.execute(select(Message))).first() is None
    assert (await session.execute(select(ToolCall))).first() is None
