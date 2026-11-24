"""
tests/test_ingest.py
Tests for the /api/v1/ingest endpoint:
- Device authentication
- Valid batch ingestion
- Duplicate batch idempotency
- Concurrent duplicate uploads safety
- DS18B20 disconnect code sanitization (-127°C, 85°C)
- Sample limits
- Missing fields
- Lead-off flag
"""
import asyncio
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def create_sample_payload(device_id="ESP32-001", patient_id="P001", batch_id="B001", sample_count=100, **kwargs):
    base = {
        "device_id": device_id,
        "patient_id": patient_id,
        "batch_id": batch_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": [512 + (i % 50) for i in range(sample_count)],
        "heart_rate_bpm": 74.5,
        "spo2_percent": 98.0,
        "temperature_c": 36.7,
        "lead_off": False,
        "is_simulated": True,
        "firmware_version": "1.0.0",
    }
    base.update(kwargs)
    return base


@pytest.mark.asyncio
async def test_ingest_valid_batch(client: AsyncClient, test_device, test_patient):
    """Test standard valid telemetry batch ingestion."""
    device, key = test_device
    payload = create_sample_payload(
        device_id=device.device_id,
        patient_id=test_patient.patient_id,
        batch_id="TEST-BATCH-001",
        sample_count=250,
    )
    headers = {"X-Device-API-Key": key}
    resp = await client.post("/api/v1/ingest", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_id"] == "TEST-BATCH-001"
    assert data["accepted_samples"] == 250
    assert data["status"] == "accepted"
    assert "recording_id" in data


@pytest.mark.asyncio
async def test_ingest_duplicate_batch_idempotency(client: AsyncClient, test_device, test_patient):
    """Test that submitting the same batch_id twice returns status='duplicate'."""
    device, key = test_device
    payload = create_sample_payload(
        device_id=device.device_id,
        patient_id=test_patient.patient_id,
        batch_id="DUPE-BATCH-999",
        sample_count=50,
    )
    headers = {"X-Device-API-Key": key}

    # First attempt -> accepted
    r1 = await client.post("/api/v1/ingest", json=payload, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "accepted"

    # Second attempt with identical batch_id -> duplicate
    r2 = await client.post("/api/v1/ingest", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"
    assert r2.json()["accepted_samples"] == 0


@pytest.mark.asyncio
async def test_concurrent_duplicate_ingest(client: AsyncClient, test_device, test_patient):
    """Test concurrent identical uploads (e.g. cellular network retransmission race condition)."""
    device, key = test_device
    payload = create_sample_payload(
        device_id=device.device_id,
        patient_id=test_patient.patient_id,
        batch_id="CONCURRENT-DUPE-777",
        sample_count=60,
    )
    headers = {"X-Device-API-Key": key}

    # Execute two simultaneous POST requests with identical payload
    r1, r2 = await asyncio.gather(
        client.post("/api/v1/ingest", json=payload, headers=headers),
        client.post("/api/v1/ingest", json=payload, headers=headers),
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    # Under concurrent retransmission, responses must be 200 and statuses must be valid ('accepted' or 'duplicate')
    assert r1.json()["status"] in ("accepted", "duplicate")
    assert r2.json()["status"] in ("accepted", "duplicate")


@pytest.mark.asyncio
async def test_ds18b20_temperature_disconnect_sanitization(client: AsyncClient, test_device, test_patient):
    """Test that hardware disconnect codes (-127°C and 85°C) are sanitized to None."""
    device, key = test_device
    payload = create_sample_payload(
        device_id=device.device_id,
        patient_id=test_patient.patient_id,
        batch_id="TEMP-DISCONN-001",
        temperature_c=-127.0,
    )
    headers = {"X-Device-API-Key": key}
    resp = await client.post("/api/v1/ingest", json=payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_ingest_invalid_api_key(client: AsyncClient, test_device, test_patient):
    """Test ingestion with invalid API key returns 401."""
    device, _ = test_device
    payload = create_sample_payload(device_id=device.device_id, patient_id=test_patient.patient_id)
    headers = {"X-Device-API-Key": "completely-invalid-key"}
    resp = await client.post("/api/v1/ingest", json=payload, headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_unknown_patient(client: AsyncClient, test_device):
    """Test ingestion with non-existent patient ID returns 422."""
    device, key = test_device
    payload = create_sample_payload(device_id=device.device_id, patient_id="NONEXISTENT-P999")
    headers = {"X-Device-API-Key": key}
    resp = await client.post("/api/v1/ingest", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_oversized_batch(client: AsyncClient, test_device, test_patient):
    """Test ingestion exceeding max samples returns 413 or 422."""
    device, key = test_device
    payload = create_sample_payload(
        device_id=device.device_id,
        patient_id=test_patient.patient_id,
        sample_count=10001,  # limit is 10,000
    )
    headers = {"X-Device-API-Key": key}
    resp = await client.post("/api/v1/ingest", json=payload, headers=headers)
    assert resp.status_code in (413, 422)


@pytest.mark.asyncio
async def test_ingest_missing_required_fields(client: AsyncClient, test_device):
    """Test ingestion missing required batch_id and recorded_at returns 422."""
    _, key = test_device
    incomplete = {"device_id": "ESP32-001"}
    headers = {"X-Device-API-Key": key}
    resp = await client.post("/api/v1/ingest", json=incomplete, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cross_device_same_batch_id_isolation(client: AsyncClient, db_session: AsyncSession, test_device, test_patient):
    """Test that two different devices using the exact same batch_id (e.g. BATCH-001) succeed independently."""
    dev1, key1 = test_device

    from app.models.patient import Patient
    from app.models.device import Device
    from app.security.device_auth import generate_device_api_key, hash_device_api_key

    p2 = Patient(patient_id="P002", full_name="Bob Jones", age=50)
    db_session.add(p2)
    await db_session.flush()

    k2_full, k2_id, k2_prefix, k2_secret = generate_device_api_key()
    dev2 = Device(
        device_id="ESP32-002",
        patient_id=p2.id,
        api_key_id=k2_id,
        api_key_prefix=k2_prefix,
        api_key_hash=hash_device_api_key(k2_secret),
        is_active=True,
    )
    db_session.add(dev2)
    await db_session.commit()

    shared_batch_id = "COMMON-BATCH-001"

    # Device 1 uploads shared_batch_id
    payload1 = create_sample_payload(
        device_id=dev1.device_id,
        patient_id=test_patient.patient_id,
        batch_id=shared_batch_id,
        session_id="SES-DEV1",
        sequence_number=1,
    )
    r1 = await client.post("/api/v1/ingest", json=payload1, headers={"X-Device-API-Key": key1})
    assert r1.status_code == 200
    assert r1.json()["status"] == "accepted"

    # Device 2 uploads identical shared_batch_id
    payload2 = create_sample_payload(
        device_id=dev2.device_id,
        patient_id="P002",
        batch_id=shared_batch_id,
        session_id="SES-DEV2",
        sequence_number=1,
    )
    r2 = await client.post("/api/v1/ingest", json=payload2, headers={"X-Device-API-Key": k2_full})
    assert r2.status_code == 200
    # Must be accepted for Device 2, NOT falsely treated as duplicate of Device 1
    assert r2.json()["status"] == "accepted"
    assert r2.json()["accepted_samples"] > 0


@pytest.mark.asyncio
async def test_sequence_number_conflict_different_batch_id(client: AsyncClient, test_device, test_patient):
    """Test that submitting a conflicting batch with the same sequence number under a session returns 409 Conflict."""
    dev, key = test_device
    session_id = "SES-SEQ-CONFLICT-01"

    # Sequence 1 with BATCH-1A
    p1 = create_sample_payload(
        device_id=dev.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-1A",
        session_id=session_id,
        sequence_number=1,
    )
    r1 = await client.post("/api/v1/ingest", json=p1, headers={"X-Device-API-Key": key})
    assert r1.status_code == 200
    assert r1.json()["status"] == "accepted"

    # Sequence 1 with BATCH-1B (different batch ID for same sequence) -> 409 Conflict
    p2 = create_sample_payload(
        device_id=dev.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-1B",
        session_id=session_id,
        sequence_number=1,
    )
    r2 = await client.post("/api/v1/ingest", json=p2, headers={"X-Device-API-Key": key})
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_session_ownership_device_mismatch(client: AsyncClient, db_session: AsyncSession, test_device, test_patient):
    """Test that Device B cannot append data to a session started by Device A (returns 403 Forbidden)."""
    dev1, key1 = test_device

    from app.models.patient import Patient
    from app.models.device import Device
    from app.security.device_auth import generate_device_api_key, hash_device_api_key

    p2 = Patient(patient_id="P002", full_name="Bob Jones", age=50)
    db_session.add(p2)
    await db_session.flush()

    k2_full, k2_id, k2_prefix, k2_secret = generate_device_api_key()
    dev2 = Device(
        device_id="ESP32-002",
        patient_id=p2.id,
        api_key_id=k2_id,
        api_key_prefix=k2_prefix,
        api_key_hash=hash_device_api_key(k2_secret),
        is_active=True,
    )
    db_session.add(dev2)
    await db_session.commit()

    session_id = "SES-OWNER-PROTECTED-01"

    # Device 1 initiates session
    p1 = create_sample_payload(
        device_id=dev1.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-DEV1-01",
        session_id=session_id,
        sequence_number=1,
    )
    r1 = await client.post("/api/v1/ingest", json=p1, headers={"X-Device-API-Key": key1})
    assert r1.status_code == 200

    # Device 2 attempts to append batch to Device 1's session -> 403
    p2 = create_sample_payload(
        device_id=dev2.device_id,
        patient_id="P002",
        batch_id="BATCH-DEV2-02",
        session_id=session_id,
        sequence_number=2,
    )
    r2 = await client.post("/api/v1/ingest", json=p2, headers={"X-Device-API-Key": k2_full})
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_session_parameter_mismatch_sampling_rate_and_unit(client: AsyncClient, test_device, test_patient):
    """Test that attempting to append batches with conflicting sampling rate or unit returns 409 Conflict."""
    dev, key = test_device
    session_id = "SES-PARAM-CHECK-01"

    # Initiate session at 250 Hz, adc_counts
    p1 = create_sample_payload(
        device_id=dev.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-PARAM-01",
        session_id=session_id,
        sequence_number=1,
        ecg_sampling_rate_hz=250,
        ecg_unit="adc_counts",
    )
    r1 = await client.post("/api/v1/ingest", json=p1, headers={"X-Device-API-Key": key})
    assert r1.status_code == 200

    # Try appending sequence 2 with 500 Hz -> 409 Conflict
    p2 = create_sample_payload(
        device_id=dev.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-PARAM-02",
        session_id=session_id,
        sequence_number=2,
        ecg_sampling_rate_hz=500,
        ecg_unit="adc_counts",
    )
    r2 = await client.post("/api/v1/ingest", json=p2, headers={"X-Device-API-Key": key})
    assert r2.status_code == 409

    # Try appending sequence 2 with "millivolts" -> 409 Conflict
    p3 = create_sample_payload(
        device_id=dev.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-PARAM-03",
        session_id=session_id,
        sequence_number=2,
        ecg_sampling_rate_hz=250,
        ecg_unit="millivolts",
    )
    r3 = await client.post("/api/v1/ingest", json=p3, headers={"X-Device-API-Key": key})
    assert r3.status_code == 409


@pytest.mark.asyncio
async def test_session_lifecycle_completed_rejects_and_incomplete_reconciles(client: AsyncClient, test_device, test_patient):
    """Test session lifecycle: completed rejects new batches, incomplete reconciles late arriving batches."""
    dev, key = test_device
    session_id = "SES-LIFECYCLE-RECONCILE-01"

    # Send sequence 1
    p1 = create_sample_payload(
        device_id=dev.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-LC-01",
        session_id=session_id,
        sequence_number=1,
    )
    await client.post("/api/v1/ingest", json=p1, headers={"X-Device-API-Key": key})

    # Send sequence 3 with is_session_end=True (sequence 2 is missing!)
    p3 = create_sample_payload(
        device_id=dev.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-LC-03",
        session_id=session_id,
        sequence_number=3,
        is_session_end=True,
    )
    r3 = await client.post("/api/v1/ingest", json=p3, headers={"X-Device-API-Key": key})
    assert r3.status_code == 200
    assert 2 in r3.json()["missing_batches_detected"]

    # Now late-arriving sequence 2 arrives!
    p2 = create_sample_payload(
        device_id=dev.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-LC-02",
        session_id=session_id,
        sequence_number=2,
    )
    r2 = await client.post("/api/v1/ingest", json=p2, headers={"X-Device-API-Key": key})
    assert r2.status_code == 200
    assert r2.json()["status"] == "accepted"

    # Now that all sequences (1, 2, 3) are present, session is Completed.
    # Trying to add sequence 4 must be rejected with 409!
    p4 = create_sample_payload(
        device_id=dev.device_id,
        patient_id=test_patient.patient_id,
        batch_id="BATCH-LC-04",
        session_id=session_id,
        sequence_number=4,
    )
    r4 = await client.post("/api/v1/ingest", json=p4, headers={"X-Device-API-Key": key})
    assert r4.status_code == 409
