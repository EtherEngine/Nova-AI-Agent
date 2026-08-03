"""API and agent tests with a mocked OpenAI client (no network calls)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")


def _make_function_call(name: str, arguments: dict[str, Any], call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=json.dumps(arguments),
        call_id=call_id,
    )


def _make_text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(output=[], output_text=text)


def _make_tool_response(call: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(output=[call], output_text="")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    _set_env(monkeypatch)
    # Import inside the fixture so env vars are picked up on startup.
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _install_mock(client: TestClient, responses: list[SimpleNamespace]) -> AsyncMock:
    create = AsyncMock(side_effect=responses)
    client.app.state.openai_client = SimpleNamespace(
        responses=SimpleNamespace(create=create),
        close=AsyncMock(),
    )
    return create


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model": "test-model"}


def test_chat_without_tool(client: TestClient) -> None:
    _install_mock(client, [_make_text_response("Hallo, wie kann ich helfen?")])

    response = client.post("/chat", json={"message": "Hallo"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Hallo, wie kann ich helfen?"
    assert body["tools"] == []


def test_chat_with_tool_call(client: TestClient) -> None:
    call = _make_function_call("calculate", {"operation": "divide", "a": 145, "b": 5}, "call_1")
    _install_mock(
        client,
        [
            _make_tool_response(call),
            _make_text_response("145 geteilt durch 5 ergibt 29."),
        ],
    )

    response = client.post("/chat", json={"message": "Was ist 145 geteilt durch 5?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "145 geteilt durch 5 ergibt 29."
    assert body["tools"] == [
        {
            "name": "calculate",
            "arguments": {"operation": "divide", "a": 145, "b": 5},
            "result": {"ok": True, "data": {"result": 29}},
        }
    ]


def test_chat_empty_message_rejected(client: TestClient) -> None:
    response = client.post("/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_whitespace_message_rejected(client: TestClient) -> None:
    _install_mock(client, [_make_text_response("unused")])
    response = client.post("/chat", json={"message": "   "})
    assert response.status_code == 422


def test_chat_unknown_field_rejected(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "Hallo", "role": "admin"})
    assert response.status_code == 422


def test_chat_message_too_long_rejected(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "x" * 5000})
    assert response.status_code == 422


# --- Streaming (SSE) ----------------------------------------------------------


class _FakeStream:
    """Async-iterable stand-in for the OpenAI streaming response."""

    def __init__(self, events: list[SimpleNamespace]) -> None:
        self._events = events

    def __aiter__(self) -> _FakeStream:
        self._iter = iter(self._events)
        return self

    async def __anext__(self) -> SimpleNamespace:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _delta(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="response.output_text.delta", delta=text)


def _completed(response: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(type="response.completed", response=response)


def _install_stream_mock(
    client: TestClient, rounds: list[list[SimpleNamespace]]
) -> AsyncMock:
    create = AsyncMock(side_effect=[_FakeStream(events) for events in rounds])
    client.app.state.openai_client = SimpleNamespace(
        responses=SimpleNamespace(create=create),
        close=AsyncMock(),
    )
    return create


def _parse_sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    frames: list[tuple[str, dict[str, Any]]] = []
    for block in text.strip().split("\n\n"):
        event = ""
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        if event:
            frames.append((event, json.loads(data)))
    return frames


def test_chat_stream_without_tool(client: TestClient) -> None:
    _install_stream_mock(
        client,
        [[_delta("Hallo "), _delta("Welt"), _completed(_make_text_response("Hallo Welt"))]],
    )

    response = client.post("/chat/stream", json={"message": "Hallo"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = _parse_sse(response.text)
    tokens = "".join(data["delta"] for event, data in frames if event == "token")
    done = [data for event, data in frames if event == "done"]
    assert tokens == "Hallo Welt"
    assert done and done[0]["answer"] == "Hallo Welt"
    assert done[0]["tools"] == []


def test_chat_stream_with_tool(client: TestClient) -> None:
    call = _make_function_call("calculate", {"operation": "divide", "a": 145, "b": 5}, "call_1")
    _install_stream_mock(
        client,
        [
            [_completed(_make_tool_response(call))],
            [_delta("29"), _completed(_make_text_response("29"))],
        ],
    )

    response = client.post("/chat/stream", json={"message": "145 / 5?"})

    assert response.status_code == 200
    frames = _parse_sse(response.text)
    tools = [data for event, data in frames if event == "tool"]
    done = [data for event, data in frames if event == "done"]
    assert len(tools) == 1
    assert tools[0]["name"] == "calculate"
    assert tools[0]["result"] == {"ok": True, "data": {"result": 29}}
    assert done and done[0]["tools"][0]["name"] == "calculate"


def test_chat_stream_whitespace_message_emits_error(client: TestClient) -> None:
    response = client.post("/chat/stream", json={"message": "   "})
    assert response.status_code == 200
    frames = _parse_sse(response.text)
    assert any(event == "error" for event, _ in frames)


# --- API versioning + security headers ----------------------------------------


def test_api_v1_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model": "test-model"}


def test_api_v1_chat_without_tool(client: TestClient) -> None:
    _install_mock(client, [_make_text_response("Antwort")])
    response = client.post("/api/v1/chat", json={"message": "Hallo"})
    assert response.status_code == 200
    assert response.json()["answer"] == "Antwort"


def test_legacy_health_still_available(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Permissions-Policy" in response.headers


