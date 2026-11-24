"""
tests/test_devices.py
Tests for device registration, API key generation, hashing, rotation, and revocation.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_device(client: AsyncClient, auth_headers, test_patient):
    """Test registering a new device returns plain API key once."""
    payload = {
        "device_id": "ESP32-NEW-01",
        "description": "Clinic Outpost B",
        "patient_id": test_patient.id,
    }
    resp = await client.post("/api/v1/devices", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["device_id"] == "ESP32-NEW-01"
    assert "plain_api_key" in data
    assert data["plain_api_key"].startswith("rhm_")
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_duplicate_device_id(client: AsyncClient, auth_headers, test_device):
    """Test registering duplicate device ID returns 409 Conflict."""
    device, _ = test_device
    payload = {"device_id": device.device_id}
    resp = await client.post("/api/v1/devices", json=payload, headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_devices(client: AsyncClient, auth_headers, test_device):
    """Test listing devices returns public representations without secrets."""
    resp = await client.get("/api/v1/devices", headers=auth_headers)
    assert resp.status_code == 200
    devices = resp.json()
    assert len(devices) >= 1
    for dev in devices:
        assert "api_key_hash" not in dev
        assert "plain_api_key" not in dev


@pytest.mark.asyncio
async def test_get_device_detail(client: AsyncClient, auth_headers, test_device):
    """Test retrieving specific device details."""
    device, _ = test_device
    resp = await client.get(f"/api/v1/devices/{device.device_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == device.device_id
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_rotate_device_api_key(client: AsyncClient, auth_headers, test_device, test_patient):
    """Test rotating a device API key invalidates old key and enables new key."""
    device, old_key = test_device

    # 1. Rotate the key
    rotate_resp = await client.post(f"/api/v1/devices/{device.device_id}/rotate-key", headers=auth_headers)
    assert rotate_resp.status_code == 200
    data = rotate_resp.json()
    new_key = data["plain_api_key"]
    assert new_key != old_key
    assert new_key.startswith("rhm_")

    # 2. Try ingesting with old key -> 401 Unauthorized
    payload = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "batch_id": "BATCH-OLD-KEY-TEST",
        "recorded_at": "2026-11-22T10:00:00Z",
        "ecg_samples": [512, 513, 514],
    }
    r_old = await client.post("/api/v1/ingest", json=payload, headers={"X-Device-API-Key": old_key})
    assert r_old.status_code == 401

    # 3. Ingest with new key -> 200 OK
    r_new = await client.post("/api/v1/ingest", json=payload, headers={"X-Device-API-Key": new_key})
    assert r_new.status_code == 200
    assert r_new.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_revoke_device_api_key(client: AsyncClient, auth_headers, test_device, test_patient):
    """Test revoking a device API key disables the device from ingesting."""
    device, key = test_device

    # Revoke key
    revoke_resp = await client.post(f"/api/v1/devices/{device.device_id}/revoke-key", headers=auth_headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["is_revoked"] is True

    # Ingestion attempt should fail with 401
    payload = {
        "device_id": device.device_id,
        "patient_id": test_patient.patient_id,
        "batch_id": "BATCH-REVOKED-TEST",
        "recorded_at": "2026-11-22T10:00:00Z",
        "ecg_samples": [512, 513, 514],
    }
    resp = await client.post("/api/v1/ingest", json=payload, headers={"X-Device-API-Key": key})
    assert resp.status_code == 401
