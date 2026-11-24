"""
app/services/patient_service.py
Business logic for Patient entity management.
"""
from __future__ import annotations

from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate


async def get_patients(
    db: AsyncSession,
    search: Optional[str] = None,
    archived: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[Patient], int]:
    """Retrieve paginated patients with optional text search and archive filter."""
    q = select(Patient)
    if not archived:
        q = q.where(Patient.is_archived.is_(False))
    if search:
        search_pattern = f"%{search}%"
        q = q.where(
            Patient.full_name.ilike(search_pattern) | Patient.patient_id.ilike(search_pattern)
        )

    # Count total matching query
    count_q = select(func.count()).select_from(q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    # Get page
    result = await db.execute(q.order_by(Patient.created_at.desc()).offset(skip).limit(limit))
    patients = list(result.scalars().all())
    return patients, total


async def get_patient_by_pid(db: AsyncSession, patient_id: str) -> Optional[Patient]:
    """Look up a patient by their unique patient_id code (e.g. 'P001')."""
    result = await db.execute(select(Patient).where(Patient.patient_id == patient_id))
    return result.scalar_one_or_none()


async def get_patient_by_id(db: AsyncSession, id_: int) -> Optional[Patient]:
    """Look up a patient by their integer primary key."""
    result = await db.execute(select(Patient).where(Patient.id == id_))
    return result.scalar_one_or_none()


async def create_patient(db: AsyncSession, data: PatientCreate, actor_id: str) -> Patient:
    """Create a new patient record and write an audit event."""
    p = Patient(
        patient_id=data.patient_id,
        full_name=data.full_name,
        age=data.age,
        notes=data.notes,
        is_archived=False,
    )
    db.add(p)
    audit = AuditEvent(
        event_type="patient_created",
        actor_type="doctor",
        actor_id=actor_id,
        resource_type="patient",
        resource_id=data.patient_id,
        detail=f"Created patient {data.full_name} ({data.patient_id})",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(p)
    return p


async def update_patient(
    db: AsyncSession, patient: Patient, data: PatientUpdate, actor_id: str
) -> Patient:
    """Update mutable fields of a patient and log audit event."""
    update_data = data.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(patient, field, val)

    audit = AuditEvent(
        event_type="patient_updated",
        actor_type="doctor",
        actor_id=actor_id,
        resource_type="patient",
        resource_id=patient.patient_id,
        detail=f"Updated patient {patient.patient_id}: {list(update_data.keys())}",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(patient)
    return patient
