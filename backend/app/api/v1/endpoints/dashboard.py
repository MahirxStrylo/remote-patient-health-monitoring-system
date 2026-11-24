"""
app/api/v1/endpoints/dashboard.py
Main dashboard statistics and system event feed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.audit import AuditEvent
from app.models.device import Device
from app.models.doctor import DoctorUser
from app.models.ecg import ECGRecording
from app.models.patient import Patient
from app.models.vitals import DeviceUpload
from app.schemas.dashboard import DashboardStats, RecentEvent
from app.security.auth import get_current_active_doctor

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_statistics(
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> DashboardStats:
    """
    Compute real-time dashboard statistics strictly from database state.
    Calculates active devices (last seen within 10 minutes), 24h upload volume,
    and recent system events.
    """
    now = datetime.now(timezone.utc)
    active_cutoff = now - timedelta(minutes=10)
    cutoff_24h = now - timedelta(hours=24)

    # 1. Total non-archived patients
    patient_count_res = await db.execute(
        select(func.count()).select_from(Patient).where(Patient.is_archived.is_(False))
    )
    total_patients: int = patient_count_res.scalar_one()

    # 2. Total registered devices
    device_count_res = await db.execute(select(func.count()).select_from(Device))
    total_devices: int = device_count_res.scalar_one()

    # 3. Devices reporting within last 10 minutes
    active_devices_res = await db.execute(
        select(func.count())
        .select_from(Device)
        .where(Device.last_seen >= active_cutoff)
    )
    active_devices: int = active_devices_res.scalar_one()

    # 4. Total uploads in the last 24 hours
    uploads_24h_res = await db.execute(
        select(func.count())
        .select_from(DeviceUpload)
        .where(DeviceUpload.received_at >= cutoff_24h)
    )
    latest_uploads_count: int = uploads_24h_res.scalar_one()

    # 5. ECG recordings captured in last 24 hours
    ecg_24h_res = await db.execute(
        select(func.count())
        .select_from(ECGRecording)
        .where(ECGRecording.started_at >= cutoff_24h)
    )
    recent_ecg_count: int = ecg_24h_res.scalar_one()

    # 6. Ingestion errors in last 24 hours
    errors_res = await db.execute(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.event_type.in_(["ingest_error", "auth_failed"]),
            AuditEvent.created_at >= cutoff_24h,
        )
    )
    ingestion_errors: int = errors_res.scalar_one()

    # 7. Recent 20 audit events
    events_res = await db.execute(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(20)
    )
    audit_rows = events_res.scalars().all()

    recent_events = [
        RecentEvent(
            event_type=e.event_type,
            actor_type=e.actor_type,
            actor_id=e.actor_id,
            detail=e.detail,
            created_at=e.created_at,
        )
        for e in audit_rows
    ]

    return DashboardStats(
        total_patients=total_patients,
        total_devices=total_devices,
        active_devices=active_devices,
        latest_uploads_count=latest_uploads_count,
        recent_ecg_count=recent_ecg_count,
        recent_events=recent_events,
        ingestion_errors=ingestion_errors,
    )
