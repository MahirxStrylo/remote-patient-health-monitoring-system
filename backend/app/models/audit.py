"""
app/models/audit.py
AuditEvent and DoctorNote ORM models.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.doctor import DoctorUser
    from app.models.patient import Patient


class AuditEvent(Base):
    """
    Immutable event log for security- and compliance-relevant actions.
    Rows are only ever inserted, never updated or deleted.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # e.g. login, logout, patient_created, device_registered, ecg_uploaded, error
    actor_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # doctor | device | system
    actor_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEvent id={self.id} type={self.event_type!r}"
            f" actor={self.actor_type}/{self.actor_id}>"
        )


class DoctorNote(TimestampMixin, Base):
    """
    A clinical note written by a doctor for a specific patient.
    """

    __tablename__ = "doctor_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doctor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("doctor_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="doctor_notes",
        lazy="selectin",
    )
    doctor: Mapped["DoctorUser"] = relationship(
        "DoctorUser",
        back_populates="notes",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<DoctorNote id={self.id} patient_id={self.patient_id}"
            f" doctor_id={self.doctor_id}>"
        )
