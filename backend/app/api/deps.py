"""
app/api/deps.py
Centralised FastAPI dependency re-exports.

Import your dependencies from here rather than from the individual security /
database modules so that call sites remain stable if the implementation moves.
"""
from __future__ import annotations

# Re-export database dependency
from app.database.session import get_db as get_db  # noqa: F401

# Re-export doctor/JWT authentication dependencies
from app.security.auth import (  # noqa: F401
    get_current_active_doctor,
    get_current_doctor,
    require_admin,
)

# Re-export device API-key dependency
from app.security.device_auth import get_device_from_api_key as get_device_from_api_key  # noqa: F401

__all__ = [
    "get_db",
    "get_current_doctor",
    "get_current_active_doctor",
    "require_admin",
    "get_device_from_api_key",
]
