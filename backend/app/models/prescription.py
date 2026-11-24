"""
app/models/prescription.py
Prescription and Doctor-to-Patient message ORM model.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.doctor import DoctorUser
    from app.models.patient import Patient


class Prescription(Base):
    """
    Represents a medical prescription or clinical directive authored by a doctor
    and transmitted down to a patient's IoT device (e.g. ESP32 LCD).
    """

    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    doctor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("doctor_users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    assessment: Mapped[str] = mapped_column(String(255), nullable=False)
    medication: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str] = mapped_column(String(128), nullable=False)
    frequency: Mapped[str] = mapped_column(String(128), nullable=False)
    duration: Mapped[str] = mapped_column(String(128), nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Status: 'Pending' | 'Delivered' | 'Acknowledged'
    status: Mapped[str] = mapped_column(
        String(32), default="Pending", nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="prescriptions",
        lazy="selectin",
    )
    device: Mapped[Optional["Device"]] = relationship(
        "Device",
        back_populates="prescriptions",
        lazy="selectin",
    )
    doctor: Mapped[Optional["DoctorUser"]] = relationship(
        "DoctorUser",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Prescription id={self.id} patient_id={self.patient_id} status={self.status!r}>"
