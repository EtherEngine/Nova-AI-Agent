"""Tool registry package.

Importing this package registers all built-in tools as a side effect, so the
agent can simply call :func:`get_tool_definitions` / :func:`execute_tool`.
"""

from __future__ import annotations

from . import builtin as _builtin  # noqa: F401  (side effect: registers tools)
from .registry import (
    Permission,
    Tool,
    ToolCategory,
    ToolError,
    ToolRegistry,
    execute_tool,
    get_tool_definitions,
    registry,
)

__all__ = [
    "Permission",
    "Tool",
    "ToolCategory",
    "ToolError",
    "ToolRegistry",
    "execute_tool",
    "get_tool_definitions",
    "registry",
]
