"""Authentication package: JWT auth, password hashing, user scoping."""

from __future__ import annotations

from .dependencies import get_current_user, optional_current_user
from .router import router
from .security import create_token, decode_token, hash_password, verify_password

__all__ = [
    "create_token",
    "decode_token",
    "get_current_user",
    "hash_password",
    "optional_current_user",
    "router",
    "verify_password",
]
