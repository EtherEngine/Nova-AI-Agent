"""Agent orchestration using the OpenAI Responses API with tool calling.

The agent is stateless: every call builds its own conversation input list so
that concurrent ``/chat`` requests never share mutable state.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from .config import Settings
from .schemas import ToolInvocation
from .tools import execute_tool, get_tool_definitions

logger = logging.getLogger("simple_ai_agent.agent")

_SYSTEM_INSTRUCTIONS = (
    "Du bist ein hilfreicher Assistent. Verwende die bereitgestellten Tools, "
    "wenn eine Berechnung oder die aktuelle Uhrzeit benötigt wird. "
    "Antworte dem Nutzer immer in klarem, natürlichem Deutsch."
)


class AgentError(Exception):
    """Raised for agent-level failures that should map to a safe client error."""

    def __init__(self, detail: str, status_code: int = 502) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _extract_function_calls(response: Any) -> list[Any]:
    return [
        item
        for item in getattr(response, "output", []) or []
        if getattr(item, "type", None) == "function_call"
    ]


def _run_tool_call(call: Any) -> ToolInvocation:
    """Validate + execute a single streamed/non-streamed function call."""
    arguments = _parse_arguments(call.arguments)
    if arguments is None:
        result = {"ok": False, "error": "Ungültiges JSON in den Tool-Argumenten."}
        arguments = {}
    else:
        result = execute_tool(call.name, arguments)
    return ToolInvocation(name=call.name, arguments=arguments, result=result)


def _tool_io_items(call: Any, invocation: ToolInvocation) -> list[dict[str, Any]]:
    """Build the function_call + function_call_output items for the next round."""
    return [
        {
            "type": "function_call",
            "call_id": call.call_id,
            "name": call.name,
            "arguments": call.arguments,
        },
        {
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": json.dumps(invocation.result, ensure_ascii=False),
        },
    ]


async def run_agent(
    client: AsyncOpenAI,
    settings: Settings,
    message: str,
) -> tuple[str, list[ToolInvocation]]:
    """Run one full agent turn and return the final answer and tool history."""
    input_items: list[dict[str, Any]] = [{"role": "user", "content": message}]
    tool_definitions = get_tool_definitions()
    tools_used: list[ToolInvocation] = []

    for _ in range(settings.max_tool_rounds):
        response = await client.responses.create(
            model=settings.openai_model,
            instructions=_SYSTEM_INSTRUCTIONS,
            input=input_items,
            tools=tool_definitions,
            tool_choice="auto",
            parallel_tool_calls=False,
        )

        function_calls = _extract_function_calls(response)

        if not function_calls:
            answer = (response.output_text or "").strip()
            if not answer:
                raise AgentError("Das Modell lieferte eine leere Antwort.")
            return answer, tools_used

        for call in function_calls:
            invocation = _run_tool_call(call)
            tools_used.append(invocation)
            input_items.extend(_tool_io_items(call, invocation))

    raise AgentError(
        "Die maximale Anzahl an Tool-Runden wurde überschritten.",
        status_code=502,
    )


@dataclass(slots=True)
class TokenEvent:
    """A chunk of assistant text produced during streaming."""

    delta: str


@dataclass(slots=True)
class ToolEvent:
    """A completed tool invocation emitted mid-stream."""

    tool: ToolInvocation


@dataclass(slots=True)
class DoneEvent:
    """Terminal event carrying the full answer and all tool invocations."""

    answer: str
    tools: list[ToolInvocation]


AgentStreamEvent = TokenEvent | ToolEvent | DoneEvent


async def stream_agent(
    client: AsyncOpenAI,
    settings: Settings,
    message: str,
) -> AsyncIterator[AgentStreamEvent]:
    """Run the agent, yielding token deltas, tool events, and a final DoneEvent.

    Mirrors :func:`run_agent` but streams output. Client disconnects surface as
    a cancellation that propagates out of the generator (never swallowed here).
    """
    input_items: list[dict[str, Any]] = [{"role": "user", "content": message}]
    tool_definitions = get_tool_definitions()
    tools_used: list[ToolInvocation] = []
    answer_parts: list[str] = []

    for _ in range(settings.max_tool_rounds):
        stream = await client.responses.create(
            model=settings.openai_model,
            instructions=_SYSTEM_INSTRUCTIONS,
            input=input_items,
            tools=tool_definitions,
            tool_choice="auto",
            parallel_tool_calls=False,
            stream=True,
        )

        final_response: Any = None
        async for event in stream:
            event_type = getattr(event, "type", "")
            if event_type == "response.output_text.delta":
                answer_parts.append(event.delta)
                yield TokenEvent(delta=event.delta)
            elif event_type == "response.completed":
                final_response = event.response

        if final_response is None:
            raise AgentError("Das Modell lieferte eine leere Antwort.")

        function_calls = _extract_function_calls(final_response)

        if not function_calls:
            answer = "".join(answer_parts).strip()
            if not answer:
                answer = (final_response.output_text or "").strip()
            if not answer:
                raise AgentError("Das Modell lieferte eine leere Antwort.")
            yield DoneEvent(answer=answer, tools=tools_used)
            return

        for call in function_calls:
            invocation = _run_tool_call(call)
            tools_used.append(invocation)
            yield ToolEvent(tool=invocation)
            input_items.extend(_tool_io_items(call, invocation))

    raise AgentError(
        "Die maximale Anzahl an Tool-Runden wurde überschritten.",
        status_code=502,
    )


def _parse_arguments(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
