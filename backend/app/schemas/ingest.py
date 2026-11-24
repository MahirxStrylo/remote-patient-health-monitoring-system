"""
app/schemas/ingest.py
Pydantic v2 schemas for the device data-ingest endpoint supporting ECG sessions,
sequence tracking, physiological sensor validation, and duplicate reconciliation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class IngestPayload(BaseModel):
    """
    Payload sent by an IoT device (ESP32/SIM800L) uploading sensor readings.
    Supports continuous ECG recording sessions with ordered batch sequences.
    """

    device_id: str = Field(..., min_length=1, max_length=128, description="Hardware identifier (e.g. 'ESP32-001').")
    patient_id: str = Field(..., min_length=1, max_length=64, description="Target patient identifier (e.g. 'P001').")
    session_id: Optional[str] = Field(None, max_length=64, description="Parent ECG session UUID. Auto-assigned if omitted.")
    batch_id: str = Field(..., min_length=1, max_length=128, description="Globally unique batch identifier.")
    sequence_number: int = Field(1, ge=1, description="Strictly increasing 1-based sequence index within the session.")
    recorded_at: datetime = Field(..., description="Timestamp of first sample in this batch.")

    # ECG
    ecg_sampling_rate_hz: int = Field(250, ge=1, le=10_000, description="ADC sampling frequency in Hz.")
    ecg_unit: str = Field("adc_counts", max_length=32, description="Unit of ECG samples. Always 'adc_counts' for raw ADC.")
    ecg_samples: List[int] = Field(
        ...,
        max_length=10_000,
        description="Raw integer ADC samples ordered chronologically.",
    )

    # Vitals with physiological boundary validation
    heart_rate_bpm: Optional[float] = Field(None, ge=0, le=400, description="Heart rate (BPM). 0 is preserved as abnormal alert / probe detached.")
    spo2_percent: Optional[float] = Field(None, ge=0, le=100, description="Blood oxygen saturation (%). Low readings (<90%) are clinically preserved.")
    temperature_c: Optional[float] = Field(None, ge=-150, le=100, description="Temperature (°C). -127°C or 85°C flags DS18B20 disconnect.")

    # Hardware flags
    lead_off: bool = Field(False, description="True if AD8232 lead-off comparator tripped.")
    is_simulated: bool = Field(False, description="True if data is generated synthetically.")
    firmware_version: Optional[str] = Field(None, max_length=64, description="ESP32 firmware version.")
    is_session_end: bool = Field(False, description="If True, marks parent session as Completed.")
    sensor_faults: List[str] = Field(default_factory=list, description="Detected sensor hardware fault notices.")

    @model_validator(mode="before")
    @classmethod
    def detect_sensor_faults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            faults = []
            temp = data.get("temperature_c")
            if temp is not None:
                try:
                    ftemp = float(temp)
                    if ftemp <= -100:
                        faults.append("DS18B20 wire disconnect (-127°C)")
                    elif ftemp == 85.0:
                        faults.append("DS18B20 power-on reset state (85°C)")
                except (ValueError, TypeError):
                    pass
            hr = data.get("heart_rate_bpm")
            if hr is not None:
                try:
                    fhr = float(hr)
                    if fhr == 0:
                        faults.append("Zero BPM: No valid pulse detected / optical signal unavailable (probe detachment)")
                except (ValueError, TypeError):
                    pass
            data["sensor_faults"] = faults
        return data

    @field_validator("temperature_c", mode="before")
    @classmethod
    def sanitize_temperature(cls, v: Optional[float]) -> Optional[float]:
        """Flag or sanitize common DS18B20 disconnect codes (-127°C or 85°C reset)."""
        if v is not None:
            try:
                fv = float(v)
                if fv <= -100 or fv == 85.0:
                    # Known DS18B20 disconnect / reset codes
                    return None
                return fv
            except (ValueError, TypeError):
                return None
        return v


class IngestResponse(BaseModel):
    """Response returned to the IoT device after ingestion attempt."""

    batch_id: str
    session_id: str
    sequence_number: int
    recording_id: str  # Kept as alias to session_id for backwards compatibility
    accepted_samples: int
    status: str  # "accepted" | "duplicate" | "error"
    message: str
    missing_batches_detected: List[int] = Field(default_factory=list, description="List of sequence numbers missing between 1 and current.")
