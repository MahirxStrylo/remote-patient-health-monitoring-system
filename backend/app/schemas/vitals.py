"""
app/schemas/vitals.py
Pydantic v2 schemas for vital-sign reading endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VitalReadingPublic(BaseModel):
    """Vital sign reading returned to API consumers."""

    model_config = {"from_attributes": True}

    id: int
    patient_id: int
    device_id: int
    batch_id: str
    recorded_at: datetime
    heart_rate_bpm: Optional[float] = None
    spo2_percent: Optional[float] = None
    temperature_c: Optional[float] = None
    is_simulated: bool
    created_at: datetime
