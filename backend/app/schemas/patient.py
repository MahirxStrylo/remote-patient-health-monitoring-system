"""
app/schemas/patient.py
Pydantic v2 schemas for patient management endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.device import DevicePublic


class PatientCreate(BaseModel):
    """Fields required when registering a new patient."""

    patient_id: str = Field(..., min_length=1, max_length=64, description="Human-readable patient identifier (e.g. 'P001').")
    full_name: str = Field(..., min_length=1, max_length=255)
    age: Optional[int] = Field(None, ge=0, le=150)
    notes: Optional[str] = None


class PatientUpdate(BaseModel):
    """All fields are optional – only provided fields are changed."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    age: Optional[int] = Field(None, ge=0, le=150)
    notes: Optional[str] = None
    is_archived: Optional[bool] = None


class PatientPublic(BaseModel):
    """Patient representation returned to API consumers."""

    model_config = {"from_attributes": True}

    id: int
    patient_id: str
    full_name: str
    age: Optional[int] = None
    notes: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class PatientWithDevice(PatientPublic):
    """Extended patient representation that includes assigned devices."""

    devices: List[DevicePublic] = []
