"""
tests/test_patients.py
Tests for patient CRUD, search, filtering, and clinical notes.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_patient(client: AsyncClient, auth_headers):
    """Test doctor can create a new patient."""
    payload = {
        "patient_id": "P002",
        "full_name": "Bob Martin",
        "age": 62,
        "notes": "Diabetic, monitored for bradycardia",
    }
    resp = await client.post("/api/v1/patients", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["patient_id"] == "P002"
    assert data["full_name"] == "Bob Martin"
    assert data["age"] == 62
    assert data["is_archived"] is False


@pytest.mark.asyncio
async def test_create_duplicate_patient_id(client: AsyncClient, auth_headers, test_patient):
    """Test creating a patient with existing ID returns 409 Conflict."""
    payload = {
        "patient_id": "P001",  # already exists from fixture
        "full_name": "Duplicate Alice",
    }
    resp = await client.post("/api/v1/patients", json=payload, headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_patients(client: AsyncClient, auth_headers, test_patient):
    """Test listing patients returns paginated response."""
    resp = await client.get("/api/v1/patients", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(p["patient_id"] == "P001" for p in data["items"])


@pytest.mark.asyncio
async def test_get_patient_by_id(client: AsyncClient, auth_headers, test_patient):
    """Test fetching a patient by their patient_id code."""
    resp = await client.get("/api/v1/patients/P001", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "P001"
    assert data["full_name"] == "Alice Smith"


@pytest.mark.asyncio
async def test_get_nonexistent_patient(client: AsyncClient, auth_headers):
    """Test fetching non-existent patient returns 404."""
    resp = await client.get("/api/v1/patients/P999", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_patient(client: AsyncClient, auth_headers, test_patient):
    """Test updating patient fields and archiving."""
    update_payload = {"full_name": "Alice Smith-Jones", "age": 46, "is_archived": True}
    resp = await client.patch("/api/v1/patients/P001", json=update_payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Alice Smith-Jones"
    assert data["age"] == 46
    assert data["is_archived"] is True


@pytest.mark.asyncio
async def test_doctor_notes(client: AsyncClient, auth_headers, test_patient):
    """Test creating and retrieving doctor clinical notes."""
    note_resp = await client.post(
        "/api/v1/patients/P001/notes",
        json={"content": "Patient reported mild fatigue. Advised rest."},
        headers=auth_headers,
    )
    assert note_resp.status_code == 201
    note_data = note_resp.json()
    assert note_data["content"] == "Patient reported mild fatigue. Advised rest."

    list_resp = await client.get("/api/v1/patients/P001/notes", headers=auth_headers)
    assert list_resp.status_code == 200
    notes = list_resp.json()
    assert len(notes) >= 1
    assert notes[0]["content"] == "Patient reported mild fatigue. Advised rest."
