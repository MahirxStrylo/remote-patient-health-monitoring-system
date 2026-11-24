"""
app/services/prescription_service.py
Business logic for managing prescriptions and IoT device message exchange.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditEvent
from app.models.device import Device
from app.models.doctor import DoctorUser
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.schemas.prescription import (
    DeviceAcknowledgeResponse,
    DeviceInboxMessage,
    DeviceInboxResponse,
    PrescriptionCreate,
    PrescriptionPublic,
)

logger = logging.getLogger(__name__)


def _to_public_prescription(rx: Prescription) -> PrescriptionPublic:
    """Format ORM Prescription into PrescriptionPublic with resolved metadata."""
    return PrescriptionPublic(
        id=rx.id,
        patient_id=rx.patient_id,
        patient_code=rx.patient.patient_id if rx.patient else None,
        patient_name=rx.patient.full_name if rx.patient else None,
        device_id=rx.device_id,
        device_code=rx.device.device_id if rx.device else None,
        doctor_id=rx.doctor_id,
        doctor_name=rx.doctor.full_name if rx.doctor else (rx.doctor.username if rx.doctor else None),
        assessment=rx.assessment,
        medication=rx.medication,
        dosage=rx.dosage,
        frequency=rx.frequency,
        duration=rx.duration,
        instructions=rx.instructions,
        follow_up_date=rx.follow_up_date,
        status=rx.status,
        created_at=rx.created_at,
        delivered_at=rx.delivered_at,
        acknowledged_at=rx.acknowledged_at,
    )


async def create_prescription(
    db: AsyncSession,
    patient: Patient,
    doctor: DoctorUser,
    data: PrescriptionCreate,
) -> PrescriptionPublic:
    """Create a new prescription for a patient and route it to their assigned device."""
    target_device_id = data.device_id

    # Auto-resolve target device if not explicitly provided
    if target_device_id is None:
        stmt = select(Device).where(Device.patient_id == patient.id, Device.is_active.is_(True))
        res = await db.execute(stmt)
        dev = res.scalars().first()
        if dev:
            target_device_id = dev.id

    rx = Prescription(
        patient_id=patient.id,
        device_id=target_device_id,
        doctor_id=doctor.id,
        assessment=data.assessment.strip(),
        medication=data.medication.strip(),
        dosage=data.dosage.strip(),
        frequency=data.frequency.strip(),
        duration=data.duration.strip(),
        instructions=data.instructions.strip() if data.instructions else None,
        follow_up_date=data.follow_up_date.strip() if data.follow_up_date else None,
        status="Pending",
    )
    db.add(rx)
    await db.flush()

    audit = AuditEvent(
        event_type="prescription_created",
        actor_type="doctor",
        actor_id=doctor.username,
        detail=(
            f"Prescription #{rx.id} authored for Patient {patient.patient_id} "
            f"({data.medication} {data.dosage}, {data.frequency} for {data.duration})."
        ),
    )
    db.add(audit)
    await db.commit()

    # Re-fetch with relationships loaded
    stmt = (
        select(Prescription)
        .where(Prescription.id == rx.id)
        .options(
            selectinload(Prescription.patient),
            selectinload(Prescription.device),
            selectinload(Prescription.doctor),
        )
    )
    res = await db.execute(stmt)
    full_rx = res.scalar_one()

    logger.info(
        "Prescription #%d created by doctor %s for patient %s (device_id=%s)",
        full_rx.id,
        doctor.username,
        patient.patient_id,
        target_device_id,
    )
    return _to_public_prescription(full_rx)


async def get_prescriptions(
    db: AsyncSession,
    patient_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[PrescriptionPublic], int]:
    """Retrieve filtered, paginated prescriptions."""
    query = (
        select(Prescription)
        .join(Prescription.patient)
        .options(
            selectinload(Prescription.patient),
            selectinload(Prescription.device),
            selectinload(Prescription.doctor),
        )
    )

    if patient_id is not None:
        query = query.where(Prescription.patient_id == patient_id)
    if status:
        query = query.where(Prescription.status == status)
    if search:
        search_filter = f"%{search.strip()}%"
        query = query.where(
            (Prescription.medication.ilike(search_filter))
            | (Prescription.assessment.ilike(search_filter))
            | (Patient.patient_id.ilike(search_filter))
            | (Patient.full_name.ilike(search_filter))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    # Paginate and order by newest first
    query = query.order_by(Prescription.created_at.desc()).offset(skip).limit(limit)
    res = await db.execute(query)
    rows = res.scalars().all()

    return [_to_public_prescription(r) for r in rows], total


async def get_patient_prescriptions(
    db: AsyncSession,
    patient_id: int,
) -> List[PrescriptionPublic]:
    """Retrieve all prescriptions for a specific patient."""
    query = (
        select(Prescription)
        .where(Prescription.patient_id == patient_id)
        .options(
            selectinload(Prescription.patient),
            selectinload(Prescription.device),
            selectinload(Prescription.doctor),
        )
        .order_by(Prescription.created_at.desc())
    )
    res = await db.execute(query)
    rows = res.scalars().all()
    return [_to_public_prescription(r) for r in rows]


async def get_device_inbox(
    db: AsyncSession,
    device_id_str: str,
) -> DeviceInboxResponse:
    """
    Fetch unacknowledged prescriptions directed to this device.
    Transitions 'Pending' messages to 'Delivered' upon fetch.
    """
    stmt = select(Device).where(Device.device_id == device_id_str)
    res = await db.execute(stmt)
    device = res.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id_str!r} not found in registry.",
        )

    # Retrieve unacknowledged messages assigned to this device or its patient
    stmt = (
        select(Prescription)
        .where(
            (Prescription.device_id == device.id)
            | ((Prescription.device_id.is_(None)) & (Prescription.patient_id == device.patient_id)),
            Prescription.status.in_(["Pending", "Delivered"]),
        )
        .order_by(Prescription.created_at.asc())
    )
    res = await db.execute(stmt)
    prescriptions = res.scalars().all()

    messages: List[DeviceInboxMessage] = []
    now_utc = datetime.now(timezone.utc)
    updated = False

    for rx in prescriptions:
        messages.append(
            DeviceInboxMessage(
                id=rx.id,
                assessment=rx.assessment,
                medication=rx.medication,
                dosage=rx.dosage,
                frequency=rx.frequency,
                duration=rx.duration,
                instructions=rx.instructions or "",
                follow_up_date=rx.follow_up_date or "",
            )
        )
        # Transition from Pending -> Delivered
        if rx.status == "Pending":
            rx.status = "Delivered"
            rx.delivered_at = now_utc
            updated = True

    if updated:
        await db.commit()
        logger.info(
            "Delivered %d pending prescription(s) to device %s",
            len(messages),
            device_id_str,
        )

    return DeviceInboxResponse(messages=messages)


async def acknowledge_prescription(
    db: AsyncSession,
    device_id_str: str,
    message_id: int,
) -> DeviceAcknowledgeResponse:
    """Record receipt confirmation from patient pressing CONFIRM on hardware / Wokwi."""
    stmt = select(Device).where(Device.device_id == device_id_str)
    res = await db.execute(stmt)
    device = res.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id_str!r} not found.",
        )

    stmt = select(Prescription).where(Prescription.id == message_id)
    res = await db.execute(stmt)
    rx = res.scalar_one_or_none()

    if not rx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prescription #{message_id} not found.",
        )

    # Verify device match
    if rx.device_id and rx.device_id != device.id and rx.patient_id != device.patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Prescription #{message_id} is not targeted for device {device_id_str!r}.",
        )

    now_utc = datetime.now(timezone.utc)
    rx.status = "Acknowledged"
    rx.acknowledged_at = now_utc

    audit = AuditEvent(
        event_type="prescription_acknowledged",
        actor_type="device",
        actor_id=device_id_str,
        detail=f"Patient confirmed receipt of Prescription #{rx.id} on device {device_id_str}.",
    )
    db.add(audit)
    await db.commit()

    logger.info(
        "Prescription #%d confirmed and acknowledged by device %s",
        message_id,
        device_id_str,
    )
    return DeviceAcknowledgeResponse(
        status="success",
        message_id=rx.id,
        acknowledged_at=now_utc,
    )
