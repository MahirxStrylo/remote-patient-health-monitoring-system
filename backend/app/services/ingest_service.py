"""
app/services/ingest_service.py
Core pipeline for processing incoming IoT telemetry batches from devices.
Features:
- Session-based grouping of sequential telemetry batches
- Sequence tracking and missing batch detection
- Database-level duplicate batch protection with concurrent race-condition safety
- Scalable device-patient binding and physiological vitals verification
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.device import Device
from app.models.ecg import ECGBatch, ECGSession
from app.models.patient import Patient
from app.models.vitals import DeviceUpload, VitalReading
from app.schemas.ingest import IngestPayload, IngestResponse
from app.services.device_service import update_device_heartbeat
from app.services.ecg_service import get_or_create_ecg_session

logger = logging.getLogger(__name__)


async def process_ingest(
    db: AsyncSession, payload: IngestPayload, device: Device
) -> IngestResponse:
    """
    Ingest a batch of telemetry (ECG + Vitals) sent by an authenticated IoT device.
    
    Guarantees:
    - Idempotent duplicate protection: Database unique constraints prevent double-storage.
    - Concurrent safety: Gracefully handles simultaneous submissions via IntegrityError rollback.
    - Session continuity: Batches are linked to an ongoing ECGSession with sequence numbers.
    - Missing batch detection: Identifies sequence gaps across cellular dropouts.
    """
    # Determine session ID (default to batch_id for single-shot uploads if session_id omitted)
    session_id = payload.session_id or payload.batch_id
    device_pk = device.id
    device_identifier = device.device_id

    # 1. Validate patient existence
    patient_res = await db.execute(
        select(Patient).where(Patient.patient_id == payload.patient_id)
    )
    patient = patient_res.scalar_one_or_none()
    if not patient:
        logger.error(
            "Ingest rejected: Unknown patient_id %r from device %r",
            payload.patient_id,
            device.device_id,
        )
        raise ValueError(f"Patient with identifier {payload.patient_id!r} not found in database.")

    # 2. Check device-patient assignment consistency
    if device.patient_id is not None and device.patient_id != patient.id:
        logger.error(
            "Ingest rejected: Device %r assigned to patient ID %s, but payload reported patient %s",
            device.device_id,
            device.patient_id,
            patient.id,
        )
        raise ValueError(
            f"Device {device.device_id!r} is assigned to patient {device.patient_id}, "
            f"not {payload.patient_id!r}."
        )

    # Automatically associate device to patient if device was unassigned
    if device.patient_id is None:
        device.patient_id = patient.id

    # 3. Device-scoped duplicate check for batch_id
    existing_upload_res = await db.execute(
        select(DeviceUpload).where(
            DeviceUpload.device_id == device.id,
            DeviceUpload.batch_id == payload.batch_id,
        )
    )
    existing_upload: Optional[DeviceUpload] = existing_upload_res.scalar_one_or_none()

    if existing_upload is not None:
        if existing_upload.patient_id is not None and existing_upload.patient_id != patient.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Batch {payload.batch_id!r} retransmission patient mismatch.",
            )
        logger.warning(
            "Duplicate batch %r received from device %r. Idempotently acknowledging.",
            payload.batch_id,
            device.device_id,
        )
        await update_device_heartbeat(db, device, payload.batch_id, payload.firmware_version)
        return IngestResponse(
            batch_id=payload.batch_id,
            session_id=session_id,
            sequence_number=payload.sequence_number,
            recording_id=session_id,
            accepted_samples=0,
            status="duplicate",
            message="Duplicate batch already stored. Acknowledged without reprocessing.",
            missing_batches_detected=[],
        )

    # 4. Transactional persistence with concurrency race-condition handling
    try:
        # Resolve or create parent ECGSession with strict ownership and parameter checks
        session = await get_or_create_ecg_session(
            db=db,
            patient_id=patient.id,
            device_id=device.id,
            session_id=session_id,
            sampling_rate_hz=payload.ecg_sampling_rate_hz,
            unit=payload.ecg_unit,
            started_at=payload.recorded_at,
            is_simulated=payload.is_simulated,
        )

        # Check sequence conflict: sequence already exists under this session with a different batch_id
        existing_batch_seq_res = await db.execute(
            select(ECGBatch).where(
                ECGBatch.session_id == session.id,
                ECGBatch.sequence_number == payload.sequence_number,
            )
        )
        conflicting_batch = existing_batch_seq_res.scalar_one_or_none()
        if conflicting_batch is not None:
            if conflicting_batch.batch_id != payload.batch_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Sequence number {payload.sequence_number} in session {session_id} "
                        f"is already occupied by batch {conflicting_batch.batch_id!r}."
                    ),
                )
            # Same sequence and same batch_id -> duplicate
            return IngestResponse(
                batch_id=payload.batch_id,
                session_id=session_id,
                sequence_number=payload.sequence_number,
                recording_id=session_id,
                accepted_samples=0,
                status="duplicate",
                message="Duplicate batch already stored. Acknowledged without reprocessing.",
                missing_batches_detected=[],
            )

        # Query existing sequences for missing sequence detection
        existing_batches_res = await db.execute(
            select(ECGBatch.sequence_number).where(ECGBatch.session_id == session.id)
        )
        existing_sequences = set(existing_batches_res.scalars().all())
        existing_sequences.add(payload.sequence_number)
        max_seq = max(existing_sequences)

        missing_batches: List[int] = [
            seq for seq in range(1, max_seq + 1) if seq not in existing_sequences
        ]

        sample_count = len(payload.ecg_samples)

        # Create ECGBatch
        ecg_batch = ECGBatch(
            session_id=session.id,
            batch_id=payload.batch_id,
            sequence_number=payload.sequence_number,
            recorded_at=payload.recorded_at,
            samples_json=json.dumps(payload.ecg_samples),
            sample_count=sample_count,
            lead_off=payload.lead_off,
            signal_quality="lead_off" if payload.lead_off else "acceptable",
            is_duplicate=False,
        )
        db.add(ecg_batch)

        # Update session aggregate counters
        session.total_samples += sample_count
        session.total_batches += 1
        if payload.lead_off:
            session.lead_off_count += 1

        if payload.is_session_end:
            session.status = "Incomplete" if missing_batches else "Completed"
            session.ended_at = datetime.now(timezone.utc)
        elif session.status == "Incomplete":
            # Late-arriving batch: check if all gaps are now filled
            if not missing_batches:
                session.status = "Completed"
                db.add(AuditEvent(
                    event_type="session_reconciled",
                    actor_type="device",
                    actor_id=device.device_id,
                    resource_type="ecg_session",
                    resource_id=session_id,
                    detail=(
                        f"Session {session_id} reconciled: late batch {payload.batch_id} "
                        f"(seq {payload.sequence_number}) filled remaining gaps. Status changed to Completed."
                    ),
                ))
        else:
            session.status = "Recording"

        # Record vital reading if any physiological vital is present
        has_vitals = any(
            v is not None
            for v in [payload.heart_rate_bpm, payload.spo2_percent, payload.temperature_c]
        )
        if has_vitals:
            vital_reading = VitalReading(
                patient_id=patient.id,
                device_id=device.id,
                batch_id=payload.batch_id,
                recorded_at=payload.recorded_at,
                heart_rate_bpm=payload.heart_rate_bpm,
                spo2_percent=payload.spo2_percent,
                temperature_c=payload.temperature_c,
                is_simulated=payload.is_simulated,
            )
            db.add(vital_reading)

        # Record DeviceUpload audit
        approx_size = len(payload.model_dump_json().encode("utf-8"))
        upload = DeviceUpload(
            device_id=device.id,
            batch_id=payload.batch_id,
            patient_id=patient.id,
            payload_size_bytes=approx_size,
            status="accepted",
            is_duplicate=False,
        )
        db.add(upload)

        # Record AuditEvent
        sim_label = " [SIMULATED]" if payload.is_simulated else ""
        gap_label = f" (gaps: {missing_batches})" if missing_batches else ""
        audit = AuditEvent(
            event_type="ecg_uploaded",
            actor_type="device",
            actor_id=device.device_id,
            resource_type="ecg_session",
            resource_id=session_id,
            detail=(
                f"Session {session_id} seq {payload.sequence_number}: {sample_count} samples "
                f"({payload.ecg_sampling_rate_hz} Hz) for patient {payload.patient_id}{sim_label}{gap_label}."
            ),
        )
        db.add(audit)

        # Audit sensor fault conditions if detected
        for fault in payload.sensor_faults:
            db.add(AuditEvent(
                event_type="sensor_fault",
                actor_type="device",
                actor_id=device.device_id,
                resource_type="patient",
                resource_id=patient.patient_id,
                detail=f"Patient {patient.patient_id}: Hardware sensor fault detected from {device.device_id}: {fault}.",
            ))

        # Audit critical physiological flags (low SpO2 preserved, zero BPM flagged)
        if payload.heart_rate_bpm == 0:
            db.add(AuditEvent(
                event_type="vital_alert",
                actor_type="device",
                actor_id=device.device_id,
                resource_type="patient",
                resource_id=patient.patient_id,
                detail=f"Patient {patient.patient_id}: Zero heart rate reported by {device.device_id}. Classified as abnormal (No valid pulse detected / optical signal unavailable).",
            ))
        elif payload.spo2_percent is not None and payload.spo2_percent < 90:
            db.add(AuditEvent(
                event_type="vital_alert",
                actor_type="device",
                actor_id=device.device_id,
                resource_type="patient",
                resource_id=patient.patient_id,
                detail=f"Patient {patient.patient_id}: Critical low SpO2 {payload.spo2_percent}% reported by {device.device_id} (severe hypoxemia).",
            ))

        # Update device heartbeat
        await update_device_heartbeat(db, device, payload.batch_id, payload.firmware_version)

        # Atomic commit
        await db.commit()

        logger.info(
            "Ingested batch %s (seq %d, %d samples) for session %s (simulated=%s, gaps=%s)",
            payload.batch_id,
            payload.sequence_number,
            sample_count,
            session_id,
            payload.is_simulated,
            missing_batches,
        )

        return IngestResponse(
            batch_id=payload.batch_id,
            session_id=session_id,
            sequence_number=payload.sequence_number,
            recording_id=session_id,
            accepted_samples=sample_count,
            status="accepted",
            message=f"Batch accepted. {sample_count} ECG samples stored under session {session_id}.",
            missing_batches_detected=missing_batches,
        )

    except (IntegrityError, StaleDataError) as integ_err:
        await db.rollback()
        # Verify if this was a concurrent duplicate batch retransmission from the same device
        dupe_check = await db.execute(
            select(DeviceUpload).where(
                DeviceUpload.device_id == device_pk,
                DeviceUpload.batch_id == payload.batch_id,
            )
        )
        if dupe_check.scalar_one_or_none() is not None:
            logger.warning(
                "Concurrent duplicate detected for batch %r from device %s. Idempotently acknowledging.",
                payload.batch_id,
                device_identifier,
            )
            return IngestResponse(
                batch_id=payload.batch_id,
                session_id=session_id,
                sequence_number=payload.sequence_number,
                recording_id=session_id,
                accepted_samples=0,
                status="duplicate",
                message="Duplicate batch already stored. Acknowledged without reprocessing.",
                missing_batches_detected=[],
            )

        # Check if the collision was a sequence conflict under the session
        conflict_check = await db.execute(
            select(ECGBatch).join(ECGSession).where(
                ECGSession.session_id == session_id,
                ECGBatch.sequence_number == payload.sequence_number,
            )
        )
        conflicting_batch = conflict_check.scalar_one_or_none()
        if conflicting_batch is not None and conflicting_batch.batch_id != payload.batch_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Sequence number {payload.sequence_number} in session {session_id} "
                    f"is occupied by batch {conflicting_batch.batch_id!r}."
                ),
            )

        logger.warning(
            "Concurrent ingestion conflict for batch %r or session %s seq %d: %s",
            payload.batch_id,
            session_id,
            payload.sequence_number,
            integ_err,
        )
        return IngestResponse(
            batch_id=payload.batch_id,
            session_id=session_id,
            sequence_number=payload.sequence_number,
            recording_id=session_id,
            accepted_samples=0,
            status="duplicate",
            message="Duplicate batch or sequence already stored. Acknowledged without reprocessing.",
            missing_batches_detected=[],
        )
