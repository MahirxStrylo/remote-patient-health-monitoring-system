"""
app/services/device_service.py
Business logic for IoT Device registration, scalable key rotation, and status tracking.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.security.device_auth import generate_device_api_key, hash_device_api_key


async def get_devices(db: AsyncSession) -> List[Device]:
    """List all registered devices ordered by creation date."""
    result = await db.execute(select(Device).order_by(Device.created_at.desc()))
    return list(result.scalars().all())


async def get_device_by_device_id(db: AsyncSession, device_id: str) -> Optional[Device]:
    """Retrieve device by hardware device_id (e.g. 'ESP32-001')."""
    result = await db.execute(select(Device).where(Device.device_id == device_id))
    return result.scalar_one_or_none()


async def get_device_by_id(db: AsyncSession, id_: int) -> Optional[Device]:
    """Retrieve device by primary key id."""
    result = await db.execute(select(Device).where(Device.id == id_))
    return result.scalar_one_or_none()


async def create_device(
    db: AsyncSession, data: DeviceCreate, actor_id: str
) -> Tuple[Device, str]:
    """
    Register a new device with scalable prefixed API key (rhm_<key_id>_<secret>).
    Stores only non-secret key_id and bcrypt hash of the secret.
    Returns (device, plain_full_api_key).
    """
    full_api_key, key_id, prefix, secret = generate_device_api_key()
    hashed_secret = hash_device_api_key(secret)

    device = Device(
        device_id=data.device_id,
        description=data.description,
        patient_id=data.patient_id,
        api_key_id=key_id,
        api_key_prefix=prefix,
        api_key_hash=hashed_secret,
        api_key_revoked_at=None,
        is_active=True,
    )
    db.add(device)
    audit = AuditEvent(
        event_type="device_registered",
        actor_type="doctor",
        actor_id=actor_id,
        resource_type="device",
        resource_id=data.device_id,
        detail=f"Device {data.device_id} registered with key prefix {prefix}.",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(device)
    return device, full_api_key


async def rotate_device_key(
    db: AsyncSession, device: Device, actor_id: str
) -> Tuple[Device, str]:
    """
    Rotate a device's API key. Generates a new key_id and secret,
    updating the hash and clearing any revocation timestamp.
    """
    full_api_key, key_id, prefix, secret = generate_device_api_key()
    hashed_secret = hash_device_api_key(secret)

    device.api_key_id = key_id
    device.api_key_prefix = prefix
    device.api_key_hash = hashed_secret
    device.api_key_revoked_at = None

    audit = AuditEvent(
        event_type="device_key_rotated",
        actor_type="doctor",
        actor_id=actor_id,
        resource_type="device",
        resource_id=device.device_id,
        detail=f"Rotated API key for device {device.device_id}. New prefix: {prefix}.",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(device)
    return device, full_api_key


async def revoke_device_key(
    db: AsyncSession, device: Device, actor_id: str
) -> Device:
    """Revoke a device's API key immediately."""
    device.api_key_revoked_at = datetime.now(timezone.utc)

    audit = AuditEvent(
        event_type="device_key_revoked",
        actor_type="doctor",
        actor_id=actor_id,
        resource_type="device",
        resource_id=device.device_id,
        detail=f"Revoked API key for device {device.device_id}.",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(device)
    return device


async def update_device(
    db: AsyncSession, device: Device, data: DeviceUpdate, actor_id: str
) -> Device:
    """Update device assignment, description, or active status."""
    update_data = data.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(device, field, val)

    audit = AuditEvent(
        event_type="device_updated",
        actor_type="doctor",
        actor_id=actor_id,
        resource_type="device",
        resource_id=device.device_id,
        detail=f"Device {device.device_id} updated: {list(update_data.keys())}",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(device)
    return device


async def update_device_heartbeat(
    db: AsyncSession, device: Device, batch_id: str, firmware_version: Optional[str] = None
) -> None:
    """Record device activity timestamp and latest received batch ID."""
    device.last_seen = datetime.now(timezone.utc)
    device.last_batch_id = batch_id
    if firmware_version:
        device.firmware_version = firmware_version
    await db.commit()
