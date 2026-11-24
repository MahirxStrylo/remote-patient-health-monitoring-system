"""
tests/test_integration.py
Full end-to-end integration test:
1. Initialize doctor
2. Create patient
3. Register device and capture API key
4. Device sends 2,500 samples (10s @ 250 Hz)
5. Verify patient vitals and ECG recording stored
6. Test duplicate batch handling
7. Export CSV and PNG
8. Check dashboard metrics update
"""
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_system_integration_flow(client: AsyncClient, test_doctor):
    """Full end-to-end flow from doctor login to ingestion and visualizer export."""
    # 1. Doctor login
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "testdoc", "password": "docpassword123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create patient P100
    patient_resp = await client.post(
        "/api/v1/patients",
        json={"patient_id": "P100", "full_name": "Maria Gonzalez", "age": 52},
        headers=headers,
    )
    assert patient_resp.status_code == 201
    patient_data = patient_resp.json()
    p_db_id = patient_data["id"]

    # 3. Register device ESP32-INT-01
    dev_resp = await client.post(
        "/api/v1/devices",
        json={"device_id": "ESP32-INT-01", "patient_id": p_db_id},
        headers=headers,
    )
    assert dev_resp.status_code == 201
    dev_data = dev_resp.json()
    api_key = dev_data["plain_api_key"]
    device_headers = {"X-Device-API-Key": api_key}

    # 4. Device sends 2,500 ECG samples (10 seconds at 250 Hz)
    samples_2500 = [512 + int(100 * ((i % 50) / 50.0)) for i in range(2500)]
    batch_id = "ESP32-INT-01-BATCH-0001"
    ingest_payload = {
        "device_id": "ESP32-INT-01",
        "patient_id": "P100",
        "batch_id": batch_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": 250,
        "ecg_unit": "adc_counts",
        "ecg_samples": samples_2500,
        "heart_rate_bpm": 76.0,
        "spo2_percent": 98.2,
        "temperature_c": 36.8,
        "lead_off": False,
        "is_simulated": True,
        "firmware_version": "ESP32-1.0.0",
    }

    ingest_resp = await client.post("/api/v1/ingest", json=ingest_payload, headers=device_headers)
    assert ingest_resp.status_code == 200
    ingest_res = ingest_resp.json()
    assert ingest_res["status"] == "accepted"
    assert ingest_res["accepted_samples"] == 2500
    rec_id = ingest_res["recording_id"]

    # 5. Doctor retrieves patient vitals
    vitals_resp = await client.get("/api/v1/patients/P100/readings", headers=headers)
    assert vitals_resp.status_code == 200
    vitals = vitals_resp.json()
    assert len(vitals) == 1
    assert vitals[0]["heart_rate_bpm"] == 76.0
    assert vitals[0]["spo2_percent"] == 98.2
    assert vitals[0]["is_simulated"] is True

    # 6. Doctor verifies ECG recording & numerical samples
    samples_resp = await client.get(f"/api/v1/ecg-recordings/{rec_id}/samples", headers=headers)
    assert samples_resp.status_code == 200
    s_data = samples_resp.json()
    assert s_data["sample_count"] == 2500
    assert s_data["sampling_rate_hz"] == 250
    assert s_data["duration_seconds"] == 10.0
    assert s_data["is_simulated"] is True

    # 7. Test duplicate batch upload (should return status='duplicate')
    dup_resp = await client.post("/api/v1/ingest", json=ingest_payload, headers=device_headers)
    assert dup_resp.status_code == 200
    assert dup_resp.json()["status"] == "duplicate"
    assert dup_resp.json()["accepted_samples"] == 0

    # 8. Export CSV and PNG
    csv_resp = await client.get(f"/api/v1/ecg-recordings/{rec_id}/export.csv", headers=headers)
    assert csv_resp.status_code == 200
    assert "time_seconds,raw_ecg_adc_counts" in csv_resp.text

    png_resp = await client.get(f"/api/v1/ecg-recordings/{rec_id}/plot.png", headers=headers)
    assert png_resp.status_code == 200
    assert png_resp.content[:4] == b"\x89PNG"

    # 9. Verify dashboard statistics updated
    dash_resp = await client.get("/api/v1/dashboard/stats", headers=headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["total_patients"] >= 1
    assert dash_data["total_devices"] >= 1
    assert dash_data["latest_uploads_count"] >= 1
    assert dash_data["recent_ecg_count"] >= 1
    assert len(dash_data["recent_events"]) >= 1
