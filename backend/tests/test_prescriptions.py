"""
tests/test_prescriptions.py
Automated tests for doctor-to-patient prescription creation, device inbox polling,
and patient acknowledgement flow.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_fetch_prescription(client: AsyncClient, auth_headers, test_patient, test_device):
    """Test doctor creates a prescription and verifies it via patient prescriptions endpoint."""
    device, _ = test_device
    payload = {
        "assessment": "Mild tachycardia checkup",
        "medication": "Metoprolol",
        "dosage": "25 mg",
        "frequency": "Once daily",
        "duration": "7 days",
        "instructions": "Take in the morning with water.",
        "follow_up_date": "2026-12-01",
    }
    resp = await client.post(
        f"/api/v1/patients/{test_patient.patient_id}/prescriptions",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["medication"] == "Metoprolol"
    assert data["dosage"] == "25 mg"
    assert data["status"] == "Pending"
    assert data["patient_code"] == test_patient.patient_id
    assert data["device_code"] == device.device_id
    rx_id = data["id"]

    # List patient prescriptions
    list_resp = await client.get(
        f"/api/v1/patients/{test_patient.patient_id}/prescriptions",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    rx_list = list_resp.json()
    assert any(rx["id"] == rx_id for rx in rx_list)

    # List all prescriptions endpoint
    all_resp = await client.get("/api/v1/prescriptions", headers=auth_headers)
    assert all_resp.status_code == 200
    all_data = all_resp.json()
    assert all_data["total"] >= 1
    assert any(rx["id"] == rx_id for rx in all_data["items"])


@pytest.mark.asyncio
async def test_device_inbox_and_acknowledge_lifecycle(client: AsyncClient, auth_headers, test_patient, test_device):
    """Test the complete IoT device inbox polling and patient acknowledgement lifecycle."""
    device, _ = test_device
    # 1. Doctor creates prescription
    rx_payload = {
        "assessment": "Routine follow-up",
        "medication": "Sample Medicine A",
        "dosage": "1 tablet",
        "frequency": "Twice daily",
        "duration": "5 days",
        "instructions": "Take after meals",
        "follow_up_date": "2026-11-27",
    }
    create_resp = await client.post(
        f"/api/v1/patients/{test_patient.patient_id}/prescriptions",
        json=rx_payload,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    rx_id = create_resp.json()["id"]

    # 2. Device polls inbox -> message returned, status transitions to Delivered
    inbox_resp = await client.get(f"/api/v1/devices/{device.device_id}/inbox")
    assert inbox_resp.status_code == 200
    inbox_data = inbox_resp.json()
    messages = inbox_data["messages"]
    assert any(m["id"] == rx_id for m in messages)
    target_msg = next(m for m in messages if m["id"] == rx_id)
    assert target_msg["medication"] == "Sample Medicine A"
    assert target_msg["dosage"] == "1 tablet"

    # Verify status in doctor listing is now Delivered
    list_resp = await client.get("/api/v1/prescriptions", headers=auth_headers)
    delivered_rx = next(rx for rx in list_resp.json()["items"] if rx["id"] == rx_id)
    assert delivered_rx["status"] == "Delivered"
    assert delivered_rx["delivered_at"] is not None

    # 3. Patient presses CONFIRM button -> Device sends acknowledgement
    ack_resp = await client.post(
        f"/api/v1/devices/{device.device_id}/acknowledge",
        json={"message_id": rx_id},
    )
    assert ack_resp.status_code == 200
    ack_data = ack_resp.json()
    assert ack_data["status"] == "success"
    assert ack_data["message_id"] == rx_id

    # 4. Verify status in doctor listing is now Acknowledged
    list_resp2 = await client.get("/api/v1/prescriptions", headers=auth_headers)
    acked_rx = next(rx for rx in list_resp2.json()["items"] if rx["id"] == rx_id)
    assert acked_rx["status"] == "Acknowledged"
    assert acked_rx["acknowledged_at"] is not None

    # 5. Device polls inbox again -> acknowledged message is cleared
    inbox_resp2 = await client.get(f"/api/v1/devices/{device.device_id}/inbox")
    assert inbox_resp2.status_code == 200
    assert not any(m["id"] == rx_id for m in inbox_resp2.json()["messages"])


@pytest.mark.asyncio
async def test_acknowledge_nonexistent_message(client: AsyncClient, test_device):
    """Test acknowledging an invalid message ID returns 404."""
    device, _ = test_device
    resp = await client.post(
        f"/api/v1/devices/{device.device_id}/acknowledge",
        json={"message_id": 999999},
    )
    assert resp.status_code == 404
