"""
app/schemas/ecg.py
Pydantic v2 schemas for ECG sessions, sequential batches, timeline reconstruction, and filtering.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ECGBatchPublic(BaseModel):
    """Metadata for a single chronological telemetry batch."""

    model_config = {"from_attributes": True}

    batch_id: str
    sequence_number: int
    sample_count: int
    recorded_at: datetime
    received_at: datetime
    signal_quality: Optional[str] = None
    lead_off: bool = False

    # Backwards compatibility alias
    @property
    def batch_sequence(self) -> int:
        return self.sequence_number


class ECGSessionPublic(BaseModel):
    """Metadata for a full continuous ECG recording session."""

    model_config = {"from_attributes": True}

    id: int
    session_id: str
    patient_id: int
    device_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    sampling_rate_hz: int
    unit: str = "adc_counts"
    status: str = "Recording"  # Recording | Completed | Interrupted | Incomplete
    total_samples: int
    total_batches: int
    is_simulated: bool
    lead_off: bool = False
    signal_quality: Optional[str] = None
    ai_analysis_status: str = "not_configured"
    ai_classification: Optional[str] = None
    ai_confidence: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime

    # Backwards compatibility properties for endpoints expecting ECGRecordingPublic
    @property
    def recording_id(self) -> str:
        return self.session_id

    @property
    def batch_id(self) -> str:
        return self.session_id

    @property
    def sample_count(self) -> int:
        return self.total_samples

    @property
    def ecg_unit(self) -> str:
        return self.unit

    @property
    def recorded_at(self) -> datetime:
        return self.started_at


class ECGRecordingPublic(BaseModel):
    """Backwards-compatible view of an ECG recording session."""

    model_config = {"from_attributes": True}

    recording_id: str
    patient_id: int
    device_id: int
    batch_id: str
    recorded_at: datetime
    sampling_rate_hz: int
    sample_count: int
    ecg_unit: str = "adc_counts"
    status: str = "Completed"
    is_simulated: bool = False
    lead_off: bool = False
    signal_quality: Optional[str] = None
    ai_analysis_status: str = "not_configured"
    ai_classification: Optional[str] = None
    ai_confidence: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime


class ECGSamplesResponse(BaseModel):
    """Reconstructed waveform sample data with time axis and gap indicators."""

    recording_id: str
    session_id: Optional[str] = None
    status: str = "Recording"
    sampling_rate_hz: int
    ecg_unit: str
    samples: List[Optional[int]] = Field(
        ...,
        description="Reconstructed samples. None values represent detected missing batch gaps.",
    )
    filtered_samples: Optional[List[Optional[float]]] = Field(
        None,
        description="Digital zero-phase bandpass-filtered samples (0.5 - 40 Hz). Raw data is never overwritten.",
    )
    time_axis: Optional[List[float]] = Field(
        None,
        description="Reconstructed time axis in seconds taking exact batch durations and missing gaps into account.",
    )
    timestamps: Optional[List[str]] = Field(
        None,
        description="ISO 8601 UTC timestamps corresponding to each sample in the timeline.",
    )
    sample_count: int
    duration_seconds: float
    recorded_at: datetime
    is_simulated: bool
    has_gaps: bool = False
    missing_sequences: List[int] = Field(
        default_factory=list,
        description="List of detected missing batch sequence indices.",
    )
    batches: List[ECGBatchPublic] = []
