"""Tests for the central tool registry."""

from __future__ import annotations

import pytest

from app.tools import Permission, ToolCategory, execute_tool, get_tool_definitions
from app.tools.registry import Tool, ToolRegistry


def test_builtin_tools_registered() -> None:
    definitions = get_tool_definitions()
    names = {definition["name"] for definition in definitions}
    assert {"calculate", "get_current_time"} <= names


def test_definitions_are_strict() -> None:
    for definition in get_tool_definitions():
        assert definition["type"] == "function"
        assert definition["strict"] is True
        assert definition["parameters"]["additionalProperties"] is False


def test_categories_and_permissions() -> None:
    from app.tools import registry

    calculate = registry.get("calculate")
    time_tool = registry.get("get_current_time")
    assert calculate is not None and calculate.category is ToolCategory.MATH
    assert time_tool is not None and time_tool.category is ToolCategory.TIME
    assert Permission.PUBLIC in calculate.permissions


def test_permission_filtering() -> None:
    from app.tools import registry

    # Built-ins are public only, so an admin-only filter yields nothing.
    assert registry.definitions(permission=Permission.ADMIN) == []
    assert len(registry.definitions(permission=Permission.PUBLIC)) >= 2


def test_duplicate_registration_raises() -> None:
    local = ToolRegistry()
    from app.tools.builtin import CalculateArgs

    tool = Tool(
        name="dup",
        description="d",
        category=ToolCategory.GENERAL,
        permissions=(Permission.PUBLIC,),
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        args_model=CalculateArgs,
        handler=lambda args: {"ok": True},
    )
    local.register(tool)
    with pytest.raises(ValueError, match="bereits registriert"):
        local.register(tool)


def test_execute_unknown_tool() -> None:
    result = execute_tool("does_not_exist", {})
    assert result["ok"] is False
