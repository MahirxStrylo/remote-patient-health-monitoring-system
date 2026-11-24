"""
app/api/v1/endpoints/devices.py
Device registration, scalable key rotation, revocation, and status endpoints.
"""
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.doctor import DoctorUser
from app.schemas.device import (
    DeviceCreate,
    DeviceKeyRevokeResponse,
    DeviceKeyRotateResponse,
    DevicePublic,
    DeviceRegisterResponse,
    DeviceUpdate,
)
from app.schemas.prescription import (
    DeviceAcknowledgeRequest,
    DeviceAcknowledgeResponse,
    DeviceInboxResponse,
)
from app.services.prescription_service import (
    acknowledge_prescription,
    get_device_inbox,
)
from app.security.auth import get_current_active_doctor
from app.services.device_service import (
    create_device,
    get_device_by_device_id,
    get_devices,
    revoke_device_key,
    rotate_device_key,
    update_device,
)

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get("", response_model=List[DevicePublic])
async def list_all_devices(
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> List[DevicePublic]:
    """List all registered devices in the system."""
    devices = await get_devices(db)
    return [DevicePublic.model_validate(d) for d in devices]


@router.post("", response_model=DeviceRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_new_device(
    data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    doctor: DoctorUser = Depends(get_current_active_doctor),
) -> DeviceRegisterResponse:
    """
    Register a new IoT hardware unit (e.g. ESP32).
    Generates a secure prefixed API key (rhm_<id>_<secret>) shown once in the response.
    """
    existing = await get_device_by_device_id(db, data.device_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device ID {data.device_id!r} is already registered.",
        )

    device, plain_api_key = await create_device(db, data, actor_id=doctor.username)

    return DeviceRegisterResponse(
        id=device.id,
        device_id=device.device_id,
        description=device.description,
        patient_id=device.patient_id,
        is_active=device.is_active,
        api_key_prefix=device.api_key_prefix,
        api_key_revoked_at=device.api_key_revoked_at,
        last_seen=device.last_seen,
        last_batch_id=device.last_batch_id,
        firmware_version=device.firmware_version,
        created_at=device.created_at,
        plain_api_key=plain_api_key,
    )


@router.get("/{device_id}", response_model=DevicePublic)
async def get_single_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _: DoctorUser = Depends(get_current_active_doctor),
) -> DevicePublic:
    """Retrieve details of a single device."""
    device = await get_device_by_device_id(db, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id!r} not found.",
        )
    return DevicePublic.model_validate(device)


@router.patch("/{device_id}", response_model=DevicePublic)
async def update_device_info(
    device_id: str,
    data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    doctor: DoctorUser = Depends(get_current_active_doctor),
) -> DevicePublic:
    """Update device assignment, description, or active status."""
    device = await get_device_by_device_id(db, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id!r} not found.",
        )
    updated = await update_device(db, device, data, actor_id=doctor.username)
    return DevicePublic.model_validate(updated)


@router.post("/{device_id}/rotate-key", response_model=DeviceKeyRotateResponse)
async def rotate_device_api_key(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    doctor: DoctorUser = Depends(get_current_active_doctor),
) -> DeviceKeyRotateResponse:
    """
    Rotate device API key. Generates a new prefixed key and invalidates the previous secret.
    The new plaintext key is returned once.
    """
    device = await get_device_by_device_id(db, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id!r} not found.",
        )
    updated_device, new_key = await rotate_device_key(db, device, actor_id=doctor.username)
    return DeviceKeyRotateResponse(
        device_id=updated_device.device_id,
        api_key_prefix=updated_device.api_key_prefix or "",
        plain_api_key=new_key,
        rotated_at=updated_device.updated_at,
    )


@router.post("/{device_id}/revoke-key", response_model=DeviceKeyRevokeResponse)
async def revoke_device_api_key(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    doctor: DoctorUser = Depends(get_current_active_doctor),
) -> DeviceKeyRevokeResponse:
    """
    Immediately revoke a device's API key. Rejects future telemetry ingest until rotated.
    """
    device = await get_device_by_device_id(db, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id!r} not found.",
        )
    revoked = await revoke_device_key(db, device, actor_id=doctor.username)
    return DeviceKeyRevokeResponse(
        device_id=revoked.device_id,
        is_revoked=True,
        revoked_at=revoked.api_key_revoked_at or revoked.updated_at,
        message=f"API key for device {device_id!r} has been successfully revoked.",
    )


# ---------------------------------------------------------------------------
# IoT Device Inbox & Acknowledgement Endpoints (ESP32 / Wokwi / SIM800L)
# ---------------------------------------------------------------------------

@router.get(
    "/{device_id}/inbox",
    response_model=DeviceInboxResponse,
    summary="Retrieve pending prescriptions for an IoT device",
)
async def retrieve_device_inbox(
    device_id: str,
    db: AsyncSession = Depends(get_db),
) -> DeviceInboxResponse:
    """
    Device calls this endpoint periodically (e.g. every 30s) to poll for pending prescriptions.
    Messages in 'Pending' status are marked 'Delivered' upon fetch.
    """
    return await get_device_inbox(db, device_id)


@router.post(
    "/{device_id}/acknowledge",
    response_model=DeviceAcknowledgeResponse,
    summary="Acknowledge receipt of a prescription message from patient hardware",
)
async def acknowledge_device_message(
    device_id: str,
    payload: DeviceAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
) -> DeviceAcknowledgeResponse:
    """
    Device calls this endpoint when the patient presses the CONFIRM push button on hardware / Wokwi.
    Transitions prescription status to 'Acknowledged' and sets timestamp.
    """
    return await acknowledge_prescription(db, device_id, payload.message_id)

