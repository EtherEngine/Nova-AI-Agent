"""Shared FastAPI dependencies for API routers."""

from __future__ import annotations

from fastapi import Request
from openai import AsyncOpenAI

from app.config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_openai_client(request: Request) -> AsyncOpenAI:
    return request.app.state.openai_client
