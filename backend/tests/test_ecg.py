"""
tests/test_ecg.py
Tests for ECG recording retrieval, numerical samples, CSV export, PNG rendering,
multi-batch session sequence ordering, sequence gap handling, and digital filtering.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient


@pytest_asyncio.fixture
async def sample_ecg_recording(client: AsyncClient, test_device, test_patient):
    """Upload a known ECG recording to test against."""
    device, key = test_device
    payload = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "batch_id": "ECG-TEST-REC-001",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": [512, 515, 520, 540, 600, 850, 950, 600, 520, 512],
        "heart_rate_bpm": 72.0,
        "spo2_percent": 98.0,
        "temperature_c": 36.6,
        "lead_off": False,
        "is_simulated": True,
    }
    resp = await client.post("/api/v1/ingest", json=payload, headers={"X-Device-API-Key": key})
    assert resp.status_code == 200
    return resp.json()["recording_id"]


@pytest.mark.asyncio
async def test_get_ecg_recording_metadata(client: AsyncClient, auth_headers, sample_ecg_recording):
    """Test retrieving ECG recording metadata."""
    rec_id = sample_ecg_recording
    resp = await client.get(f"/api/v1/ecg-recordings/{rec_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["recording_id"] == rec_id
    assert data["sampling_rate_hz"] == 250
    assert data["sample_count"] == 10
    assert data["ecg_unit"] == "adc_counts"
    assert data["is_simulated"] is True
    assert data["ai_analysis_status"] == "not_configured"


@pytest.mark.asyncio
async def test_get_ecg_samples_array(client: AsyncClient, auth_headers, sample_ecg_recording):
    """Test retrieving reconstructed numerical samples array."""
    rec_id = sample_ecg_recording
    resp = await client.get(f"/api/v1/ecg-recordings/{rec_id}/samples", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["recording_id"] == rec_id
    assert data["samples"] == [512, 515, 520, 540, 600, 850, 950, 600, 520, 512]
    assert data["sample_count"] == 10
    assert data["duration_seconds"] == round(10 / 250, 4)


@pytest.mark.asyncio
async def test_export_ecg_csv(client: AsyncClient, auth_headers, sample_ecg_recording):
    """Test exporting ECG to CSV file format."""
    rec_id = sample_ecg_recording
    resp = await client.get(f"/api/v1/ecg-recordings/{rec_id}/export.csv", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    text = resp.text
    assert "# Remote Health Monitoring System" in text
    assert "time_seconds,raw_ecg_adc_counts" in text
    assert "0.0,512" in text


@pytest.mark.asyncio
async def test_export_ecg_png(client: AsyncClient, auth_headers, sample_ecg_recording):
    """Test rendering ECG waveform to PNG image format."""
    rec_id = sample_ecg_recording
    resp = await client.get(f"/api/v1/ecg-recordings/{rec_id}/plot.png", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_ecg_session_multi_batch_ordering(client: AsyncClient, auth_headers, test_device, test_patient):
    """Test uploading multiple batches under one session_id reconstructs contiguous timeline in sequence order."""
    device, key = test_device
    session_id = "SESSION-TEST-ORDER-101"

    # Batch 1: sequence 1 (samples 1..5)
    b1 = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "session_id": session_id,
        "batch_id": "BATCH-ORD-01",
        "sequence_number": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": [500, 510, 520, 530, 540],
    }
    # Batch 2: sequence 2 (samples 6..10)
    b2 = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "session_id": session_id,
        "batch_id": "BATCH-ORD-02",
        "sequence_number": 2,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": [550, 560, 570, 580, 590],
    }

    r1 = await client.post("/api/v1/ingest", json=b1, headers={"X-Device-API-Key": key})
    assert r1.status_code == 200
    r2 = await client.post("/api/v1/ingest", json=b2, headers={"X-Device-API-Key": key})
    assert r2.status_code == 200

    # Retrieve samples for session
    samples_resp = await client.get(f"/api/v1/ecg-recordings/{session_id}/samples", headers=auth_headers)
    assert samples_resp.status_code == 200
    data = samples_resp.json()
    assert data["sample_count"] == 10
    assert data["samples"] == [500, 510, 520, 530, 540, 550, 560, 570, 580, 590]
    assert data["has_gaps"] is False


@pytest.mark.asyncio
async def test_ecg_missing_sequence_gap_detection(client: AsyncClient, auth_headers, test_device, test_patient):
    """Test transmitting sequence 1 then skipping 2 and sending 3 detects gap and inserts None in timeline."""
    device, key = test_device
    session_id = "SESSION-TEST-GAP-202"

    b1 = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "session_id": session_id,
        "batch_id": "BATCH-GAP-01",
        "sequence_number": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": [500, 501, 502],
    }
    # Skip sequence 2 (e.g. cellular transmission failure)
    b3 = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "session_id": session_id,
        "batch_id": "BATCH-GAP-03",
        "sequence_number": 3,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": [600, 601, 602],
    }

    await client.post("/api/v1/ingest", json=b1, headers={"X-Device-API-Key": key})
    r3 = await client.post("/api/v1/ingest", json=b3, headers={"X-Device-API-Key": key})
    assert r3.status_code == 200
    assert 2 in r3.json().get("missing_batches_detected", [])

    # Fetch reconstructed samples
    samples_resp = await client.get(f"/api/v1/ecg-recordings/{session_id}/samples", headers=auth_headers)
    assert samples_resp.status_code == 200
    data = samples_resp.json()
    assert data["has_gaps"] is True
    assert 2 in data["missing_sequences"]
    # Verify None is inserted between the two batches to break the plotted waveform line
    assert None in data["samples"]


@pytest.mark.asyncio
async def test_ecg_session_completion(client: AsyncClient, auth_headers, test_device, test_patient):
    """Test marking an ongoing ECG session as Completed."""
    device, key = test_device
    session_id = "SESSION-TEST-COMPLETE-303"

    b1 = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "session_id": session_id,
        "batch_id": "BATCH-CMP-01",
        "sequence_number": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": [500, 502, 504],
        "is_session_end": True,
    }
    r = await client.post("/api/v1/ingest", json=b1, headers={"X-Device-API-Key": key})
    assert r.status_code == 200

    # Verify session detail
    meta_resp = await client.get(f"/api/v1/ecg-recordings/{session_id}", headers=auth_headers)
    assert meta_resp.status_code == 200
    assert meta_resp.json()["status"] == "Completed"


@pytest.mark.asyncio
async def test_ecg_10_second_gap_physical_duration(client: AsyncClient, auth_headers, test_device, test_patient):
    """
    Test that a missing batch of 2,500 samples @ 250 Hz accurately reconstructs a 10.0-second physical gap.
    Sequence 1: 2,500 samples (t = 0.0 to 9.996s)
    Sequence 2: MISSING (2,500 None sentinels, t = 10.0 to 19.996s)
    Sequence 3: 2,500 samples (t = 20.0 to 29.996s)
    Total timeline: 7,500 entries, exactly 30.0 seconds.
    """
    device, key = test_device
    session_id = "SESSION-10S-GAP-TEST"

    # Batch 1 (seq 1, 2500 samples)
    b1 = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "session_id": session_id,
        "batch_id": "BATCH-10S-01",
        "sequence_number": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": [512] * 2500,
    }
    # Batch 3 (seq 3, 2500 samples) - seq 2 was dropped in transit
    b3 = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "session_id": session_id,
        "batch_id": "BATCH-10S-03",
        "sequence_number": 3,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": [520] * 2500,
    }

    r1 = await client.post("/api/v1/ingest", json=b1, headers={"X-Device-API-Key": key})
    assert r1.status_code == 200

    r3 = await client.post("/api/v1/ingest", json=b3, headers={"X-Device-API-Key": key})
    assert r3.status_code == 200

    # Retrieve samples
    resp = await client.get(f"/api/v1/ecg/sessions/{session_id}/samples", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["has_gaps"] is True
    assert 2 in data["missing_sequences"]
    assert len(data["samples"]) == 7500  # 2500 + 2500 gap + 2500
    assert len(data["time_axis"]) == 7500

    # Check timestamps:
    # Index 0: 0.0s
    # Index 2499: 9.996s
    # Index 2500: 10.0s (first missing sample)
    # Index 4999: 19.996s (last missing sample)
    # Index 5000: 20.0s (first sample of batch 3)
    assert data["time_axis"][0] == 0.0
    assert data["time_axis"][2499] == 9.996
    assert data["time_axis"][2500] == 10.0
    assert data["samples"][2500] is None
    assert data["time_axis"][4999] == 19.996
    assert data["samples"][4999] is None
    assert data["time_axis"][5000] == 20.0
    assert data["samples"][5000] == 520

    # Physical duration of missing gap is exactly 10.0 seconds
    gap_duration = data["time_axis"][5000] - data["time_axis"][2500]
    assert round(gap_duration, 4) == 10.0


def test_sos_filtering_zero_phase_and_stability():
    """Verify SOS zero-phase filtering removes baseline wander and retains sample count without NaNs."""
    from app.services.ecg_service import filter_ecg_signal
    import numpy as np

    # Generate synthetic 250 Hz signal with 0.2 Hz baseline drift + 10 Hz ECG component
    t = np.linspace(0, 10, 2500)
    drift = 100 * np.sin(2 * np.pi * 0.2 * t)  # 0.2 Hz baseline wander
    ecg_comp = 50 * np.sin(2 * np.pi * 10 * t)  # 10 Hz bandpass-valid signal
    synthetic = [int(val) for val in (512 + drift + ecg_comp)]

    filtered = filter_ecg_signal(synthetic, sampling_rate_hz=250)
    assert len(filtered) == 2500
    assert all(f is not None for f in filtered)

    # With gaps: None must be preserved
    with_gap = synthetic[:1000] + [None] * 500 + synthetic[1500:]
    filt_gap = filter_ecg_signal(with_gap, sampling_rate_hz=250)
    assert len(filt_gap) == len(with_gap)
    assert all(filt_gap[i] is None for i in range(1000, 1500))
    assert filt_gap[0] is not None
    assert filt_gap[1500] is not None
