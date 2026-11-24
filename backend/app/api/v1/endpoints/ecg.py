"""
app/api/v1/endpoints/ecg.py
ECG session and recording retrieval, timeline reconstruction, raw/filtered signal views,
CSV export, and PNG waveform generation.
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.doctor import DoctorUser
from app.schemas.ecg import (
    ECGBatchPublic,
    ECGRecordingPublic,
    ECGSamplesResponse,
    ECGSessionPublic,
)
from app.security.auth import get_current_active_doctor
from app.services.ecg_service import (
    complete_ecg_session,
    generate_csv_bytes,
    generate_png_bytes,
    get_all_ecg_sessions,
    get_ecg_session,
    reconstruct_ecg_timeline,
)

router = APIRouter(tags=["ECG"])


class PaginatedSessions(BaseModel):
    items: List[ECGSessionPublic]
    total: int
    page: int
    size: int


# ---------------------------------------------------------------------------
# Sessions Endpoints
# ---------------------------------------------------------------------------

@router.get("/ecg/sessions", response_model=PaginatedSessions)
async def list_ecg_sessions(
    patient_id: Optional[int] = Query(None, description="Filter by patient database ID"),
    status: Optional[str] = Query(None, description="Filter by session status (Recording, Completed, Interrupted, Incomplete)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> PaginatedSessions:
    """List paginated ECG monitoring sessions."""
    skip = (page - 1) * size
    sessions, total = await get_all_ecg_sessions(
        db, patient_id=patient_id, status=status, skip=skip, limit=size
    )
    return PaginatedSessions(
        items=[ECGSessionPublic.model_validate(s) for s in sessions],
        total=total,
        page=page,
        size=size,
    )


@router.get("/ecg/sessions/{session_id}", response_model=ECGSessionPublic)
async def get_session_details(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> ECGSessionPublic:
    """Retrieve full metadata for an ECG session."""
    session = await get_ecg_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ECG session {session_id!r} not found.",
        )
    return ECGSessionPublic.model_validate(session)


@router.post("/ecg/sessions/{session_id}/complete", response_model=ECGSessionPublic)
async def mark_session_completed(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> ECGSessionPublic:
    """Mark an ongoing ECG session as finished and check for missing batches."""
    session = await get_ecg_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ECG session {session_id!r} not found.",
        )
    completed = await complete_ecg_session(db, session)
    return ECGSessionPublic.model_validate(completed)


# ---------------------------------------------------------------------------
# Reconstructed Samples & Timeline Endpoints (Dual routes for backwards compat)
# ---------------------------------------------------------------------------

@router.get("/ecg/sessions/{session_id}/samples", response_model=ECGSamplesResponse)
@router.get("/ecg-recordings/{session_id}/samples", response_model=ECGSamplesResponse)
async def get_session_samples(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> ECGSamplesResponse:
    """
    Retrieve chronologically reconstructed numerical ECG samples across all batches.
    - Missing batch sequences are detected and represented as None gaps.
    - Zero-phase digital bandpass-filtered samples (0.5 - 40 Hz) are provided alongside raw ADC counts.
    - Raw ADC samples are strictly preserved.
    """
    session = await get_ecg_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ECG session or recording {session_id!r} not found.",
        )

    raw_samples, filtered_samples, time_axis, missing_seqs, has_gaps = await reconstruct_ecg_timeline(db, session)
    valid_count = sum(1 for s in raw_samples if s is not None)
    duration = valid_count / session.sampling_rate_hz if session.sampling_rate_hz > 0 else 0.0

    batch_meta = [
        ECGBatchPublic(
            batch_id=b.batch_id,
            sequence_number=b.sequence_number,
            sample_count=b.sample_count,
            recorded_at=b.recorded_at,
            received_at=b.received_at,
            signal_quality=b.signal_quality,
            lead_off=b.lead_off,
        )
        for b in session.batches
    ]

    return ECGSamplesResponse(
        recording_id=session.session_id,
        session_id=session.session_id,
        status=session.status,
        sampling_rate_hz=session.sampling_rate_hz,
        ecg_unit=session.unit,
        samples=raw_samples,
        filtered_samples=filtered_samples,
        time_axis=time_axis,
        sample_count=valid_count,
        duration_seconds=round(duration, 4),
        recorded_at=session.started_at,
        is_simulated=session.is_simulated,
        has_gaps=has_gaps,
        missing_sequences=missing_seqs,
        batches=batch_meta,
    )


# ---------------------------------------------------------------------------
# Metadata Retrieval (Backwards-compatible recording endpoint)
# ---------------------------------------------------------------------------

@router.get("/ecg-recordings/{recording_id}", response_model=ECGRecordingPublic)
async def get_recording_metadata(
    recording_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> ECGRecordingPublic:
    """Retrieve metadata of a specific ECG recording/session."""
    session = await get_ecg_session(db, recording_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ECG recording {recording_id!r} not found.",
        )
    return ECGRecordingPublic(
        recording_id=session.session_id,
        patient_id=session.patient_id,
        device_id=session.device_id,
        batch_id=session.session_id,
        recorded_at=session.started_at,
        sampling_rate_hz=session.sampling_rate_hz,
        sample_count=session.total_samples,
        ecg_unit=session.unit,
        status=session.status,
        is_simulated=session.is_simulated,
        lead_off=session.lead_off,
        signal_quality=session.signal_quality,
        ai_analysis_status=session.ai_analysis_status,
        ai_classification=session.ai_classification,
        ai_confidence=session.ai_confidence,
        notes=session.notes,
        created_at=session.created_at,
    )


# ---------------------------------------------------------------------------
# CSV & PNG Export Endpoints
# ---------------------------------------------------------------------------

@router.get("/ecg/sessions/{session_id}/export.csv")
@router.get("/ecg-recordings/{session_id}/export.csv")
async def export_recording_csv(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> Response:
    """Export reconstructed ECG recording to an RFC 4180 CSV file with raw and filtered tracks."""
    session = await get_ecg_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ECG session {session_id!r} not found.",
        )
    raw_samples, filtered_samples, _, _, _ = await reconstruct_ecg_timeline(db, session)
    csv_bytes = generate_csv_bytes(session, raw_samples, filtered_samples)

    filename = f"ecg_{session_id[:8]}_{session.started_at.strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/ecg/sessions/{session_id}/plot.png")
@router.get("/ecg-recordings/{session_id}/plot.png")
async def export_recording_png(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> Response:
    """Generate and return a rendered PNG image of the ECG waveform strip."""
    session = await get_ecg_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ECG session {session_id!r} not found.",
        )
    raw_samples, filtered_samples, _, _, _ = await reconstruct_ecg_timeline(db, session)
    png_bytes = generate_png_bytes(session, raw_samples, filtered_samples)

    filename = f"ecg_{session_id[:8]}_{session.started_at.strftime('%Y%m%d_%H%M%S')}.png"
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
