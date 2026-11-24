"""
app/schemas/device.py
Pydantic v2 schemas for device management endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    """Fields required when registering a new device."""

    device_id: str = Field(..., min_length=1, max_length=128, description="Unique hardware identifier (e.g. 'ESP32-001').")
    description: Optional[str] = Field(None, max_length=255)
    patient_id: Optional[int] = Field(None, description="Database PK of the patient to assign this device to.")


class DeviceUpdate(BaseModel):
    """All fields are optional – only provided fields are changed."""

    description: Optional[str] = Field(None, max_length=255)
    patient_id: Optional[int] = None
    is_active: Optional[bool] = None


class DevicePublic(BaseModel):
    """Device representation returned to API consumers (no secrets)."""

    model_config = {"from_attributes": True}

    id: int
    device_id: str
    description: Optional[str] = None
    patient_id: Optional[int] = None
    is_active: bool
    api_key_prefix: Optional[str] = None
    api_key_revoked_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    last_batch_id: Optional[str] = None
    firmware_version: Optional[str] = None
    created_at: datetime


class DeviceRegisterResponse(DevicePublic):
    """
    Extended response returned *only* at device creation time.
    ``plain_api_key`` is shown once and never again – the application stores
    only the bcrypt hash.
    """

    plain_api_key: str = Field(..., description="Raw API key – store this securely; it will not be shown again.")


class DeviceKeyRotateResponse(BaseModel):
    """Returned when an API key is rotated."""

    device_id: str
    api_key_prefix: str
    plain_api_key: str = Field(..., description="New rotated API key – store this securely; it will not be shown again.")
    rotated_at: datetime


class DeviceKeyRevokeResponse(BaseModel):
    """Returned when an API key is revoked."""

    device_id: str
    is_revoked: bool
    revoked_at: datetime
    message: str
