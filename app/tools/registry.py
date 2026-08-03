"""Central tool registry.

Every tool is described by :class:`Tool` (name, description, JSON schema,
permissions, category, handler). Tools register themselves via the
:meth:`ToolRegistry.tool` decorator, so adding a tool never requires editing a
central list, and the agent never hardcodes tool definitions. Dynamically
discovered tools (e.g. from MCP servers) can be added at runtime via
:meth:`ToolRegistry.register`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ValidationError


class ToolError(Exception):
    """Raised by a handler when it cannot produce a valid result."""


class ToolCategory(StrEnum):
    """Coarse grouping used for UI filtering and organisation."""

    MATH = "math"
    TIME = "time"
    GENERAL = "general"
    RETRIEVAL = "retrieval"
    EXTERNAL = "external"


class Permission(StrEnum):
    """Access level required to expose/execute a tool."""

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    ADMIN = "admin"


ToolHandler = Callable[[Any], dict[str, Any]]

# Result envelope returned to the model for every tool execution.
ToolResult = dict[str, Any]


@dataclass(slots=True, frozen=True)
class Tool:
    """A single executable tool and all of its metadata."""

    name: str
    description: str
    category: ToolCategory
    permissions: tuple[Permission, ...]
    parameters: dict[str, Any]
    args_model: type[BaseModel]
    handler: ToolHandler

    def to_openai(self) -> dict[str, Any]:
        """Return the OpenAI Responses API function tool definition (strict)."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": True,
        }

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        """Validate arguments and execute the handler, never raising.

        Returns ``{"ok": True, "data": {...}}`` or ``{"ok": False, "error": ...}``.
        """
        try:
            parsed = self.args_model.model_validate(arguments)
        except ValidationError as exc:
            fields = ", ".join(str(err["loc"][0]) for err in exc.errors())
            return {"ok": False, "error": f"Ungültige Argumente für {fields}."}

        try:
            data = self.handler(parsed)
        except ToolError as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": True, "data": data}


class ToolRegistry:
    """Holds all known tools and exposes them to the agent."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        """Register a tool. Raises on duplicate names."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' ist bereits registriert.")
        self._tools[tool.name] = tool
        return tool

    def tool(
        self,
        *,
        name: str,
        description: str,
        category: ToolCategory,
        parameters: dict[str, Any],
        args_model: type[BaseModel],
        permissions: tuple[Permission, ...] = (Permission.PUBLIC,),
    ) -> Callable[[ToolHandler], ToolHandler]:
        """Decorator that registers the decorated function as a tool handler."""

        def decorator(handler: ToolHandler) -> ToolHandler:
            self.register(
                Tool(
                    name=name,
                    description=description,
                    category=category,
                    permissions=permissions,
                    parameters=parameters,
                    args_model=args_model,
                    handler=handler,
                )
            )
            return handler

        return decorator

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools)

    def definitions(self, permission: Permission | None = None) -> list[dict[str, Any]]:
        """OpenAI tool definitions, optionally filtered by required permission."""
        return [
            tool.to_openai()
            for tool in self._tools.values()
            if permission is None or permission in tool.permissions
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool by name against the registry (allowlist)."""
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"Unbekanntes Tool: {name!r}."}
        return tool.run(arguments)


# Global registry instance shared across the application.
registry = ToolRegistry()


def get_tool_definitions() -> list[dict[str, Any]]:
    """Backward-compatible accessor for the agent."""
    return registry.definitions()


def execute_tool(name: str, arguments: dict[str, Any]) -> ToolResult:
    """Backward-compatible accessor for the agent."""
    return registry.execute(name, arguments)
