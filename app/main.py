"""FastAPI application exposing the agent over a small REST API."""

from __future__ import annotations

import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .agent import (
    AgentError,
    DoneEvent,
    TokenEvent,
    ToolEvent,
    run_agent,
    stream_agent,
)
from .api.chats import router as chats_router
from .api.documents import router as documents_router
from .auth import router as auth_router
from .config import ConfigError, Settings
from .db import create_database
from .schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    ToolInvocation,
)
from .services import chats as chat_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple_ai_agent")

# Client-safe upstream error messages (shared by /chat and /chat/stream).
MSG_AUTH = "Fehler bei der Authentifizierung gegenüber dem KI-Dienst."
MSG_RATE = "Der KI-Dienst ist derzeit ausgelastet. Bitte später erneut versuchen."
MSG_CONN = "Der KI-Dienst ist derzeit nicht erreichbar."
MSG_STATUS = "Der KI-Dienst hat einen Fehler zurückgegeben."

API_V1 = "/api/v1"

# Response headers applied to every response (streaming-safe, no body buffering).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class SecurityHeadersMiddleware:
    """Pure ASGI middleware that adds security headers without buffering bodies."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in SECURITY_HEADERS.items():
                    headers.setdefault(key, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _cors_origins_from_env() -> list[str]:
    """Allowed browser origins for the frontend (comma-separated env var)."""
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration and create the shared OpenAI client on startup."""
    try:
        settings = Settings.load()
    except ConfigError as exc:
        # Fail fast with a clear message; never expose secrets.
        logger.error("Konfigurationsfehler: %s", exc)
        raise SystemExit(1) from exc

    app.state.settings = settings
    app.state.openai_client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    app.state.database = create_database(settings.database_url)
    if app.state.database is not None:
        logger.info("Datenbank verbunden.")
    else:
        logger.info("Keine DATABASE_URL gesetzt – DB-Funktionen deaktiviert.")
    logger.info("Agent gestartet (Modell: %s).", settings.openai_model)
    try:
        yield
    finally:
        await app.state.openai_client.close()
        if app.state.database is not None:
            await app.state.database.dispose()


app = FastAPI(title="simple-ai-agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_from_env(),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

router = APIRouter()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_client(request: Request) -> AsyncOpenAI:
    return request.app.state.openai_client


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", model=settings.openai_model)


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def chat(
    payload: ChatRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    client: AsyncOpenAI = Depends(get_client),
) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        return JSONResponse(  # type: ignore[return-value]
            status_code=422,
            content=ErrorResponse(detail="Die Nachricht darf nicht leer sein.").model_dump(),
        )

    try:
        answer, tools = await run_agent(client, settings, message)
    except AgentError as exc:
        logger.warning("Agent-Fehler: %s", exc.detail)
        return _error(exc.status_code, exc.detail)
    except AuthenticationError:
        logger.error("OpenAI-Authentifizierung fehlgeschlagen.")
        return _error(502, MSG_AUTH)
    except RateLimitError:
        logger.warning("OpenAI Rate Limit erreicht.")
        return _error(429, MSG_RATE)
    except APIConnectionError:
        logger.error("Verbindungsfehler zum KI-Dienst.")
        return _error(503, MSG_CONN)
    except APIStatusError as exc:
        logger.error("OpenAI API-Statusfehler: %s", exc.status_code)
        return _error(502, MSG_STATUS)

    await _persist_turn(request.app, payload.chat_id, message, answer, tools)
    return ChatResponse(answer=answer, tools=tools)


def _sse(event: str, data: dict[str, object]) -> str:
    """Format a single Server-Sent-Events frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    client: AsyncOpenAI = Depends(get_client),
) -> StreamingResponse:
    """Stream the agent response as Server-Sent Events (token/tool/done/error)."""
    message = payload.message.strip()

    async def event_source() -> AsyncIterator[str]:
        if not message:
            yield _sse("error", {"detail": "Die Nachricht darf nicht leer sein."})
            return
        try:
            async for event in stream_agent(client, settings, message):
                if isinstance(event, TokenEvent):
                    yield _sse("token", {"delta": event.delta})
                elif isinstance(event, ToolEvent):
                    yield _sse("tool", event.tool.model_dump())
                elif isinstance(event, DoneEvent):
                    await _persist_turn(
                        request.app, payload.chat_id, message, event.answer, event.tools
                    )
                    yield _sse(
                        "done",
                        {
                            "answer": event.answer,
                            "tools": [tool.model_dump() for tool in event.tools],
                        },
                    )
        except AgentError as exc:
            logger.warning("Agent-Fehler (Stream): %s", exc.detail)
            yield _sse("error", {"detail": exc.detail})
        except AuthenticationError:
            logger.error("OpenAI-Authentifizierung fehlgeschlagen (Stream).")
            yield _sse("error", {"detail": MSG_AUTH})
        except RateLimitError:
            logger.warning("OpenAI Rate Limit erreicht (Stream).")
            yield _sse("error", {"detail": MSG_RATE})
        except APIConnectionError:
            logger.error("Verbindungsfehler zum KI-Dienst (Stream).")
            yield _sse("error", {"detail": MSG_CONN})
        except APIStatusError as exc:
            logger.error("OpenAI API-Statusfehler (Stream): %s", exc.status_code)
            yield _sse("error", {"detail": MSG_STATUS})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=detail).model_dump(),
    )


async def _persist_turn(
    app_: FastAPI,
    chat_id: uuid.UUID | None,
    user_text: str,
    answer: str,
    tools: list[ToolInvocation],
) -> None:
    """Best-effort persistence of a chat turn; never breaks the response."""
    database = getattr(app_.state, "database", None)
    if chat_id is None or database is None:
        return
    try:
        async with database.sessionmaker() as session:
            await chat_service.persist_turn(
                session, chat_id, user_text=user_text, answer=answer, tools=tools
            )
            await session.commit()
    except Exception:
        logger.exception("Persistieren des Chat-Turns fehlgeschlagen.")


# Primary versioned API; legacy unversioned paths kept as hidden aliases.
app.include_router(router, prefix=API_V1)
app.include_router(router, include_in_schema=False)
app.include_router(chats_router, prefix=API_V1)
app.include_router(auth_router, prefix=API_V1)
app.include_router(documents_router, prefix=API_V1)
