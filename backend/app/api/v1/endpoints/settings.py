"""
app/api/v1/endpoints/settings.py
System settings and health diagnostics endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.models.device import Device
from app.models.doctor import DoctorUser
from app.models.ecg import ECGRecording
from app.models.patient import Patient
from app.models.vitals import VitalReading
from app.security.auth import get_current_active_doctor

router = APIRouter(prefix="/settings", tags=["Settings"])


class AppSettings(BaseModel):
    app_version: str
    stale_reading_threshold_minutes: int
    max_ecg_samples_per_batch: int
    database_url: str
    total_records: int
    server_time: str


@router.get("", response_model=AppSettings)
async def get_system_settings(
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> AppSettings:
    """Return runtime server configuration, database statistics, and limits."""
    # Count total core records
    np = (await db.execute(select(func.count()).select_from(Patient))).scalar_one()
    nd = (await db.execute(select(func.count()).select_from(Device))).scalar_one()
    ne = (await db.execute(select(func.count()).select_from(ECGRecording))).scalar_one()
    nv = (await db.execute(select(func.count()).select_from(VitalReading))).scalar_one()
    total_records = np + nd + ne + nv

    # Obfuscate sensitive credentials from database URI
    safe_db_url = settings.DATABASE_URL
    if "@" in safe_db_url:
        safe_db_url = safe_db_url.split("@")[-1]

    return AppSettings(
        app_version=settings.APP_VERSION,
        stale_reading_threshold_minutes=settings.STALE_READING_THRESHOLD_MINUTES,
        max_ecg_samples_per_batch=settings.MAX_ECG_SAMPLES_PER_BATCH,
        database_url=safe_db_url,
        total_records=total_records,
        server_time=datetime.now(timezone.utc).isoformat(),
    )
