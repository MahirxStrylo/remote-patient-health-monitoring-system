"""
app/models/ecg.py
ECGSession and ECGBatch ORM models with strict constraints and session-based architecture.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.patient import Patient


class ECGSession(TimestampMixin, Base):
    """
    Parent recording session containing multiple sequential ECGBatch chunks.
    Represents an ongoing or completed continuous ECG monitoring event.
    """

    __tablename__ = "ecg_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sampling_rate_hz: Mapped[int] = mapped_column(
        Integer, nullable=False, default=250
    )
    unit: Mapped[str] = mapped_column(
        String(32), nullable=False, default="adc_counts"
    )
    # Recording status: Recording, Completed, Interrupted, Incomplete
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Recording", index=True
    )
    total_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_batches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_batches: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lead_off_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signal_quality: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # AI analysis fields
    ai_analysis_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_configured"
    )
    ai_model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ai_model_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ai_analysis_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ai_classification: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="ecg_sessions",
        lazy="selectin",
    )
    device: Mapped["Device"] = relationship(
        "Device",
        lazy="selectin",
    )
    batches: Mapped[List["ECGBatch"]] = relationship(
        "ECGBatch",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ECGBatch.sequence_number.asc()",
        lazy="selectin",
    )

    # Backwards compatibility properties matching earlier single-batch recordings
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

    @property
    def lead_off(self) -> bool:
        return self.lead_off_count > 0

    def __repr__(self) -> str:
        return (
            f"<ECGSession id={self.id} session_id={self.session_id!r} "
            f"status={self.status!r} batches={self.total_batches}>"
        )


class ECGBatch(Base):
    """
    Individual chronological telemetry batch belonging to an ECGSession.
    Enforces uniqueness across batch_id as well as (session_id, sequence_number).
    """

    __tablename__ = "ecg_batches"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number", name="uq_session_sequence"),
        UniqueConstraint("session_id", "batch_id", name="uq_session_batch"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    batch_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ecg_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    samples_json: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    signal_quality: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    lead_off: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    session: Mapped["ECGSession"] = relationship(
        "ECGSession",
        back_populates="batches",
        lazy="selectin",
    )

    # Backwards compatibility property
    @property
    def recording(self) -> "ECGSession":
        return self.session

    @property
    def batch_sequence(self) -> int:
        return self.sequence_number

    def __repr__(self) -> str:
        return (
            f"<ECGBatch id={self.id} batch_id={self.batch_id!r} "
            f"seq={self.sequence_number} count={self.sample_count}>"
        )


# Backwards compatibility alias for code that previously imported ECGRecording
ECGRecording = ECGSession
