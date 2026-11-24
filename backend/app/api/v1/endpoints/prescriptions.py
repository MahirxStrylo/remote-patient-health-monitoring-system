"""
app/api/v1/endpoints/prescriptions.py
Doctor-facing endpoints for viewing and managing prescriptions.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.doctor import DoctorUser
from app.schemas.prescription import PaginatedPrescriptions, PrescriptionPublic
from app.security.auth import get_current_active_doctor
from app.services.prescription_service import get_prescriptions

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


@router.get("", response_model=PaginatedPrescriptions)
async def list_all_prescriptions(
    patient_id: Optional[int] = Query(None, description="Filter by patient database ID"),
    status: Optional[str] = Query(None, description="Filter by status (Pending, Delivered, Acknowledged)"),
    search: Optional[str] = Query(None, description="Search by medication, assessment, or patient name/ID"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> PaginatedPrescriptions:
    """Retrieve paginated prescriptions across patients for the doctor dashboard."""
    skip = (page - 1) * size
    items, total = await get_prescriptions(
        db, patient_id=patient_id, status=status, search=search, skip=skip, limit=size
    )
    return PaginatedPrescriptions(
        items=items,
        total=total,
        page=page,
        size=size,
    )
