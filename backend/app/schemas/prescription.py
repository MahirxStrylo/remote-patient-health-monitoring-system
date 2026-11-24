"""
app/schemas/prescription.py
Pydantic schemas for prescriptions and doctor-to-device communication.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PrescriptionCreate(BaseModel):
    """Payload submitted by a doctor to create a new prescription."""

    assessment: str = Field(..., min_length=1, max_length=255, description="Assessment or diagnosis")
    medication: str = Field(..., min_length=1, max_length=255, description="Medication name")
    dosage: str = Field(..., min_length=1, max_length=128, description="Dosage (e.g. 1 tablet)")
    frequency: str = Field(..., min_length=1, max_length=128, description="Frequency (e.g. Twice daily)")
    duration: str = Field(..., min_length=1, max_length=128, description="Duration (e.g. 5 days)")
    instructions: Optional[str] = Field(None, description="Additional patient directives")
    follow_up_date: Optional[str] = Field(None, max_length=64, description="Follow-up timeframe or date")
    device_id: Optional[int] = Field(None, description="Optional target device ID (auto-resolved if omitted)")


class PrescriptionPublic(BaseModel):
    """Detailed prescription representation for the doctor dashboard."""

    model_config = {"from_attributes": True}

    id: int
    patient_id: int
    patient_code: Optional[str] = None
    patient_name: Optional[str] = None
    device_id: Optional[int] = None
    device_code: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None

    assessment: str
    medication: str
    dosage: str
    frequency: str
    duration: str
    instructions: Optional[str] = None
    follow_up_date: Optional[str] = None

    status: str  # Pending | Delivered | Acknowledged
    created_at: datetime
    delivered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None


class PaginatedPrescriptions(BaseModel):
    """Paginated list of prescriptions."""

    items: List[PrescriptionPublic]
    total: int
    page: int
    size: int


class DeviceInboxMessage(BaseModel):
    """Minimal, compact structure tailored for microcontrollers (ESP32 / LCD)."""

    id: int
    assessment: str
    medication: str
    dosage: str
    frequency: str
    duration: str
    instructions: Optional[str] = ""
    follow_up_date: Optional[str] = ""


class DeviceInboxResponse(BaseModel):
    """Payload returned when an ESP32 queries its pending inbox."""

    messages: List[DeviceInboxMessage]


class DeviceAcknowledgeRequest(BaseModel):
    """Payload sent by ESP32 when the patient presses CONFIRM."""

    message_id: int = Field(..., description="ID of the acknowledged prescription")


class DeviceAcknowledgeResponse(BaseModel):
    """Acknowledgement receipt returned to the device."""

    status: str = "success"
    message_id: int
    acknowledged_at: datetime
