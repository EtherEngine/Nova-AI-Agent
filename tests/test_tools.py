"""Tests for locally executed tools."""

from __future__ import annotations

import pytest

from app.tools import execute_tool


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        ("add", 12, 4, 16),
        ("subtract", 12, 4, 8),
        ("multiply", 12, 4, 48),
        ("divide", 145, 5, 29),
    ],
)
def test_calculate_operations(operation: str, a: float, b: float, expected: float) -> None:
    result = execute_tool("calculate", {"operation": operation, "a": a, "b": b})
    assert result == {"ok": True, "data": {"result": expected}}


def test_calculate_divide_by_zero() -> None:
    result = execute_tool("calculate", {"operation": "divide", "a": 1, "b": 0})
    assert result["ok"] is False
    assert "null" in result["error"].lower()


def test_calculate_invalid_operation() -> None:
    result = execute_tool("calculate", {"operation": "power", "a": 2, "b": 3})
    assert result["ok"] is False
    assert "operation" in result["error"].lower()


def test_calculate_non_finite_result() -> None:
    huge = 1e308
    result = execute_tool("calculate", {"operation": "multiply", "a": huge, "b": huge})
    assert result["ok"] is False


def test_unknown_tool() -> None:
    result = execute_tool("delete_everything", {})
    assert result["ok"] is False
    assert "unbekanntes tool" in result["error"].lower()


def test_get_current_time_valid() -> None:
    result = execute_tool("get_current_time", {"timezone": "Europe/Berlin"})
    assert result["ok"] is True
    data = result["data"]
    assert data["timezone"] == "Europe/Berlin"
    assert set(data) == {"date", "time", "timezone", "iso"}


def test_get_current_time_invalid() -> None:
    result = execute_tool("get_current_time", {"timezone": "Mars/Olympus"})
    assert result["ok"] is False
    assert "zeitzone" in result["error"].lower()
