"""Portable embedding column type.

Uses pgvector's ``Vector`` on PostgreSQL (enabling native similarity search and
indexes) and falls back to ``JSON`` elsewhere (e.g. SQLite in tests). Values are
plain ``list[float]`` in Python on both dialects.
"""

from __future__ import annotations

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Dialect
from sqlalchemy.types import JSON, TypeDecorator


class EmbeddingType(TypeDecorator):
    """A vector column that degrades to JSON on non-PostgreSQL databases."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int) -> None:
        self.dim = dim
        super().__init__()

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_result_value(self, value: Any, dialect: Dialect) -> list[float] | None:
        if value is None:
            return None
        return [float(component) for component in value]
