"""
app/api/v1/endpoints/ingest.py
High-throughput telemetry ingestion endpoint for ESP32 / SIM800L devices.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.models.audit import AuditEvent
from app.schemas.ingest import IngestPayload, IngestResponse
from app.security.device_auth import get_device_from_api_key
from app.services.ingest_service import process_ingest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Data Ingestion"])


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest sensor telemetry from IoT device",
)
async def ingest_telemetry(
    payload: IngestPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_device_api_key: str = Header(
        ...,
        alias="X-Device-API-Key",
        description="Device API key issued at registration.",
    ),
) -> IngestResponse:
    """
    Primary ingestion endpoint for ESP32/SIM800L GPRS devices.
    
    Accepts:
    - Numerical raw ECG ADC sample array (up to MAX_ECG_SAMPLES_PER_BATCH).
    - Vital readings (heart rate, SpO2, temperature).
    - Batch and hardware metadata.
    
    Returns:
    - 200 OK with accepted batch ID and recording UUID.
    - 200 OK with status='duplicate' on retry of an existing batch.
    - 401 Unauthorized on invalid API key.
    - 413 Payload Too Large if sample count exceeds limit.
    - 422 Unprocessable Entity if patient does not exist or payload violates schema.
    """
    # 1. Enforce sample count limit
    if len(payload.ecg_samples) > settings.MAX_ECG_SAMPLES_PER_BATCH:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Sample count {len(payload.ecg_samples)} exceeds maximum allowed batch size "
                f"of {settings.MAX_ECG_SAMPLES_PER_BATCH}."
            ),
        )

    # 2. Authenticate device via API key
    device = await get_device_from_api_key(x_device_api_key, db)
    if not device:
        client_ip = request.client.host if request.client else None
        audit = AuditEvent(
            event_type="auth_failed",
            actor_type="device",
            actor_id=payload.device_id,
            detail="Failed ingestion attempt: invalid or unrecognized X-Device-API-Key.",
            ip_address=client_ip,
        )
        db.add(audit)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device API key.",
        )

    # 3. Verify device ID consistency
    if device.device_id != payload.device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Device identity mismatch: API key belongs to {device.device_id!r}, "
                f"but payload reported {payload.device_id!r}."
            ),
        )

    # 4. Check device active status
    if not device.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device {device.device_id!r} is marked inactive/disabled.",
        )

    # 5. Process through ingestion pipeline
    device_label = device.device_id
    try:
        response = await process_ingest(db, payload, device)
        return response
    except HTTPException:
        raise
    except ValueError as val_err:
        audit = AuditEvent(
            event_type="ingest_error",
            actor_type="device",
            actor_id=device_label,
            detail=str(val_err),
        )
        db.add(audit)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.exception("Unexpected error in ingestion for device %s: %s", device_label, exc)
        audit = AuditEvent(
            event_type="ingest_error",
            actor_type="device",
            actor_id=device_label,
            detail=f"Internal server error: {exc}",
        )
        db.add(audit)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing ingestion payload.",
        )
