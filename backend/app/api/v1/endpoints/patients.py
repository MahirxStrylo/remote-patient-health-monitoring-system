"""
app/api/v1/endpoints/patients.py
Endpoints for managing patients, their vital signs, ECG recordings, and doctor notes.
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.audit import DoctorNote
from app.models.doctor import DoctorUser
from app.models.patient import Patient
from app.models.vitals import VitalReading
from app.schemas.ecg import ECGRecordingPublic
from app.schemas.prescription import PrescriptionCreate, PrescriptionPublic
from app.services.prescription_service import (
    create_prescription,
    get_patient_prescriptions,
)
from app.schemas.patient import PatientCreate, PatientPublic, PatientUpdate
from app.schemas.vitals import VitalReadingPublic
from app.security.auth import get_current_active_doctor
from app.services.ecg_service import get_patient_ecg_recordings
from app.services.patient_service import (
    create_patient,
    get_patient_by_pid,
    get_patients,
    update_patient,
)

router = APIRouter(prefix="/patients", tags=["Patients"])


class PaginatedPatients(BaseModel):
    items: List[PatientPublic]
    total: int
    page: int
    size: int


class NoteCreate(BaseModel):
    content: str


class NotePublic(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    doctor_name: Optional[str] = None
    content: str
    created_at: str
    updated_at: str


@router.get("", response_model=PaginatedPatients)
async def list_patients(
    search: Optional[str] = Query(None, description="Search by name or ID"),
    archived: bool = Query(False, description="Include archived patients"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> PaginatedPatients:
    """Retrieve paginated patients with optional filtering."""
    skip = (page - 1) * size
    patients, total = await get_patients(
        db, search=search, archived=archived, skip=skip, limit=size
    )
    return PaginatedPatients(
        items=[PatientPublic.model_validate(p) for p in patients],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=PatientPublic, status_code=status.HTTP_201_CREATED)
async def create_new_patient(
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    doctor: DoctorUser = Depends(get_current_active_doctor),
) -> Patient:
    """Register a new patient with unique patient_id."""
    existing = await get_patient_by_pid(db, data.patient_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Patient ID {data.patient_id!r} is already registered.",
        )
    return await create_patient(db, data, actor_id=doctor.username)


@router.get("/{patient_id}", response_model=PatientPublic)
async def get_single_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> Patient:
    """Retrieve patient record by patient_id string."""
    patient = await get_patient_by_pid(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id!r} not found.",
        )
    return patient


@router.patch("/{patient_id}", response_model=PatientPublic)
async def update_patient_info(
    patient_id: str,
    data: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    doctor: DoctorUser = Depends(get_current_active_doctor),
) -> Patient:
    """Update patient demographics, notes, or archive status."""
    patient = await get_patient_by_pid(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id!r} not found.",
        )
    return await update_patient(db, patient, data, actor_id=doctor.username)


@router.get("/{patient_id}/readings", response_model=List[VitalReadingPublic])
async def get_patient_vitals(
    patient_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> List[VitalReading]:
    """Retrieve historical vital sign measurements for a patient."""
    patient = await get_patient_by_pid(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id!r} not found.",
        )

    result = await db.execute(
        select(VitalReading)
        .where(VitalReading.patient_id == patient.id)
        .order_by(VitalReading.recorded_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{patient_id}/ecg-recordings", response_model=List[ECGRecordingPublic])
async def get_patient_ecg_list(
    patient_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> List[ECGRecordingPublic]:
    """Retrieve historical ECG recordings for a patient."""
    patient = await get_patient_by_pid(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id!r} not found.",
        )

    recordings = await get_patient_ecg_recordings(db, patient.id, limit=limit)
    return [ECGRecordingPublic(
        recording_id=r.session_id,
        patient_id=r.patient_id,
        device_id=r.device_id,
        batch_id=r.session_id,
        recorded_at=r.started_at,
        sampling_rate_hz=r.sampling_rate_hz,
        sample_count=r.total_samples,
        ecg_unit=r.unit,
        status=r.status,
        is_simulated=r.is_simulated,
        lead_off=r.lead_off,
        signal_quality=r.signal_quality,
        ai_analysis_status=r.ai_analysis_status,
        ai_classification=r.ai_classification,
        ai_confidence=r.ai_confidence,
        notes=r.notes,
        created_at=r.created_at,
    ) for r in recordings]


@router.get("/{patient_id}/ecg/sessions", response_model=List[ECGRecordingPublic])
async def get_patient_sessions_list(
    patient_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> List[ECGRecordingPublic]:
    """Retrieve historical ECG sessions for a patient."""
    return await get_patient_ecg_list(patient_id=patient_id, limit=limit, db=db, _=_)


@router.get("/{patient_id}/notes", response_model=List[NotePublic])
async def list_patient_notes(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> List[NotePublic]:
    """List clinical notes written for a patient."""
    patient = await get_patient_by_pid(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id!r} not found.")

    result = await db.execute(
        select(DoctorNote)
        .where(DoctorNote.patient_id == patient.id)
        .order_by(DoctorNote.created_at.desc())
    )
    notes = result.scalars().all()
    return [
        NotePublic(
            id=n.id,
            patient_id=n.patient_id,
            doctor_id=n.doctor_id,
            doctor_name=n.doctor.full_name or n.doctor.username if n.doctor else None,
            content=n.content,
            created_at=n.created_at.isoformat(),
            updated_at=n.updated_at.isoformat(),
        )
        for n in notes
    ]


@router.post("/{patient_id}/notes", response_model=NotePublic, status_code=status.HTTP_201_CREATED)
async def add_doctor_note(
    patient_id: str,
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    doctor: DoctorUser = Depends(get_current_active_doctor),
) -> NotePublic:
    """Add a clinical note to a patient record."""
    patient = await get_patient_by_pid(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id!r} not found.")

    note = DoctorNote(
        patient_id=patient.id,
        doctor_id=doctor.id,
        content=data.content,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return NotePublic(
        id=note.id,
        patient_id=note.patient_id,
        doctor_id=note.doctor_id,
        doctor_name=doctor.full_name or doctor.username,
        content=note.content,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Prescriptions
# ---------------------------------------------------------------------------

@router.post(
    "/{patient_id}/prescriptions",
    response_model=PrescriptionPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a prescription for a patient",
)
async def create_patient_prescription(
    patient_id: str,
    data: PrescriptionCreate,
    db: AsyncSession = Depends(get_db),
    doctor: DoctorUser = Depends(get_current_active_doctor),
) -> PrescriptionPublic:
    """Create a medical prescription/directive and route it to the patient's device."""
    stmt = select(Patient).where(
        (Patient.patient_id == patient_id) | (Patient.id == int(patient_id) if patient_id.isdigit() else False)
    )
    res = await db.execute(stmt)
    patient = res.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id!r} not found.",
        )

    return await create_prescription(db, patient, doctor, data)


@router.get(
    "/{patient_id}/prescriptions",
    response_model=List[PrescriptionPublic],
    summary="List all prescriptions for a patient",
)
async def list_patient_prescriptions(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> List[PrescriptionPublic]:
    """Retrieve all prescriptions previously written for this patient."""
    stmt = select(Patient).where(
        (Patient.patient_id == patient_id) | (Patient.id == int(patient_id) if patient_id.isdigit() else False)
    )
    res = await db.execute(stmt)
    patient = res.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id!r} not found.",
        )

    return await get_patient_prescriptions(db, patient.id)

