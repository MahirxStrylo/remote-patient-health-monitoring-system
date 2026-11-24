"""
app/schemas/auth.py
Pydantic v2 schemas for authentication endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Credentials submitted via the login form or JSON body."""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT access token returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds.")


class DoctorUserPublic(BaseModel):
    """Public representation of a DoctorUser (no password hash)."""

    model_config = {"from_attributes": True}

    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    last_login: Optional[datetime] = None
    created_at: datetime
