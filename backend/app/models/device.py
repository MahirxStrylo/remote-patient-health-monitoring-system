"""
app/models/device.py
Device ORM model with scalable prefixed API key support, revocation, and rotation.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.prescription import Prescription
    from app.models.vitals import DeviceUpload


class Device(TimestampMixin, Base):
    """Represents a physical IoT monitoring device (e.g. an ESP32 node)."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Scalable API-key architecture
    # Full key format: rhm_<api_key_id>_<secret>
    # api_key_id is non-secret, indexed for O(1) lookup
    api_key_id: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    api_key_prefix: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_batch_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    firmware_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationships
    patient: Mapped[Optional["Patient"]] = relationship(
        "Patient",
        back_populates="devices",
        lazy="selectin",
    )
    uploads: Mapped[List["DeviceUpload"]] = relationship(
        "DeviceUpload",
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    prescriptions: Mapped[List["Prescription"]] = relationship(
        "Prescription",
        back_populates="device",
        lazy="selectin",
    )

    @property
    def is_key_valid(self) -> bool:
        """Check if device is active and key is not revoked."""
        return self.is_active and (self.api_key_revoked_at is None)

    def __repr__(self) -> str:
        return f"<Device id={self.id} device_id={self.device_id!r}>"
