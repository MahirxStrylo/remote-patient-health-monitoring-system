"""
app/models/patient.py
Patient ORM model.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.audit import DoctorNote
    from app.models.device import Device
    from app.models.ecg import ECGSession
    from app.models.prescription import Prescription
    from app.models.vitals import VitalReading


class Patient(TimestampMixin, Base):
    """Represents a monitored patient."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    devices: Mapped[List["Device"]] = relationship(
        "Device",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    vital_readings: Mapped[List["VitalReading"]] = relationship(
        "VitalReading",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    ecg_sessions: Mapped[List["ECGSession"]] = relationship(
        "ECGSession",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    doctor_notes: Mapped[List["DoctorNote"]] = relationship(
        "DoctorNote",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    prescriptions: Mapped[List["Prescription"]] = relationship(
        "Prescription",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Backwards compatibility property
    @property
    def ecg_recordings(self) -> List["ECGSession"]:
        return self.ecg_sessions

    def __repr__(self) -> str:
        return f"<Patient id={self.id} patient_id={self.patient_id!r}>"
