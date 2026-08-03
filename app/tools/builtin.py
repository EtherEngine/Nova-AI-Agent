"""Built-in, sandboxed tools.

Security notes:
- No dynamic code execution, no ``eval``/``exec``.
- Only tools registered here (or at runtime) can run.
- All arguments are strictly validated with Pydantic before execution.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict

from .registry import Permission, ToolCategory, ToolError, registry


class CalculateArgs(BaseModel):
    """Validated arguments for the ``calculate`` tool."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["add", "subtract", "multiply", "divide"]
    a: float
    b: float


class TimeArgs(BaseModel):
    """Validated arguments for the ``get_current_time`` tool."""

    model_config = ConfigDict(extra="forbid")

    timezone: str


_CALCULATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["add", "subtract", "multiply", "divide"],
            "description": "Die auszuführende arithmetische Operation.",
        },
        "a": {"type": "number", "description": "Der erste Operand."},
        "b": {"type": "number", "description": "Der zweite Operand."},
    },
    "required": ["operation", "a", "b"],
    "additionalProperties": False,
}

_TIME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "timezone": {
            "type": "string",
            "description": "Eine gültige IANA-Zeitzone, z. B. 'Europe/Berlin'.",
        },
    },
    "required": ["timezone"],
    "additionalProperties": False,
}


@registry.tool(
    name="calculate",
    description=(
        "Führt eine einfache arithmetische Operation "
        "(add, subtract, multiply, divide) mit zwei Zahlen aus."
    ),
    category=ToolCategory.MATH,
    parameters=_CALCULATE_SCHEMA,
    args_model=CalculateArgs,
    permissions=(Permission.PUBLIC,),
)
def calculate(args: CalculateArgs) -> dict[str, Any]:
    if args.operation == "add":
        result = args.a + args.b
    elif args.operation == "subtract":
        result = args.a - args.b
    elif args.operation == "multiply":
        result = args.a * args.b
    else:  # divide
        if args.b == 0:
            raise ToolError("Division durch null ist nicht erlaubt.")
        result = args.a / args.b

    if not math.isfinite(result):
        raise ToolError("Das Ergebnis ist keine endliche Zahl.")

    # Return whole numbers as int for cleaner output where possible.
    if result.is_integer():
        return {"result": int(result)}
    return {"result": result}


@registry.tool(
    name="get_current_time",
    description=(
        "Liefert das aktuelle Datum und die Uhrzeit für eine "
        "gültige IANA-Zeitzone."
    ),
    category=ToolCategory.TIME,
    parameters=_TIME_SCHEMA,
    args_model=TimeArgs,
    permissions=(Permission.PUBLIC,),
)
def get_current_time(args: TimeArgs) -> dict[str, Any]:
    try:
        tz = ZoneInfo(args.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ToolError(
            f"Ungültige Zeitzone: {args.timezone!r}. "
            "Es werden nur gültige IANA-Zeitzonen akzeptiert."
        ) from exc

    now = datetime.now(tz)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": args.timezone,
        "iso": now.isoformat(),
    }
