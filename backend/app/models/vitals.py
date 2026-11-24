"""
app/models/vitals.py
VitalReading and DeviceUpload ORM models.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

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


class VitalReading(Base):
    """
    One snapshot of physiological measurements from a device.
    Heart rate, SpO2, and temperature may each be absent if the sensor
    was not streaming that modality at the time.
    """

    __tablename__ = "vital_readings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(String(128), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    heart_rate_bpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spo2_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="vital_readings",
        lazy="selectin",
    )
    device: Mapped["Device"] = relationship(
        "Device",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<VitalReading id={self.id} patient_id={self.patient_id}"
            f" hr={self.heart_rate_bpm} spo2={self.spo2_percent}>"
        )


class DeviceUpload(Base):
    """
    Audit-style record of every ingest payload received from a device.
    Duplicates are scoped per device for idempotent retransmissions.
    """

    __tablename__ = "device_uploads"
    __table_args__ = (
        UniqueConstraint("device_id", "batch_id", name="uq_device_batch"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="accepted"
    )  # accepted | error | duplicate
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    device: Mapped["Device"] = relationship(
        "Device",
        back_populates="uploads",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceUpload id={self.id} batch_id={self.batch_id!r}"
            f" status={self.status!r}>"
        )
