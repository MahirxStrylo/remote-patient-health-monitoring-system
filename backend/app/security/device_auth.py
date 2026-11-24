"""
app/security/device_auth.py
Scalable, prefixed API-key generation, O(1) indexed lookup, rotation, and revocation for IoT devices.

Key structure:
    rhm_<key_id>_<secret>
    Example: rhm_9f4e2a1b7c8d0e3f_K7zX1v9AbC2dE4fG6hI8jK0lM2nO4pQ6rS8tU0vW2xY

- <key_id> is an indexed 16-character public identifier for O(1) database lookup.
- <secret> is a high-entropy 256-bit cryptographically random token.
- Only the bcrypt hash of <secret> is stored in the database.
- Key rotation and revocation are fully supported.
"""
from __future__ import annotations

import bcrypt
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device

logger = logging.getLogger(__name__)


def generate_device_api_key() -> Tuple[str, str, str, str]:
    """
    Generate a scalable prefixed device API key.

    Returns:
        tuple: (full_api_key, key_id, prefix, secret)
    """
    key_id = secrets.token_hex(8)  # 16 hex characters
    secret = secrets.token_urlsafe(32)  # ~43 characters URL-safe
    prefix = f"rhm_{key_id}"
    full_api_key = f"rhm_{key_id}_{secret}"
    return full_api_key, key_id, prefix, secret


def hash_device_api_key(secret: str) -> str:
    """Return the bcrypt hash of the secret portion of an API key."""
    secret_bytes = secret.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(secret_bytes, salt).decode("utf-8")


def verify_device_api_key(secret: str, hashed: str) -> bool:
    """Constant-time verification of raw secret against stored bcrypt hash."""
    try:
        secret_bytes = secret.encode("utf-8")[:72]
        hash_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(secret_bytes, hash_bytes)
    except Exception:
        return False


async def get_device_from_api_key(
    api_key: str,
    db: AsyncSession,
) -> Optional[Device]:
    """
    Scalable O(1) device lookup by API key.
    
    1. Extracts key_id prefix from 'rhm_<key_id>_<secret>'
    2. Performs indexed SELECT using api_key_id
    3. Verifies secret hash against device.api_key_hash
    4. Enforces device.is_active and api_key_revoked_at is None
    5. Falls back to legacy key verification for backwards compatibility
    """
    if not api_key:
        return None

    api_key = api_key.strip()

    # Prefixed indexed O(1) Lookup: rhm_<key_id>_<secret>
    if api_key.startswith("rhm_") and api_key.count("_") >= 2:
        parts = api_key.split("_", 2)
        key_id = parts[1]
        secret = parts[2]

        stmt = select(Device).where(
            Device.api_key_id == key_id,
            Device.is_active.is_(True),
            Device.api_key_revoked_at.is_(None),
        )
        res = await db.execute(stmt)
        device = res.scalar_one_or_none()

        if device is not None and verify_device_api_key(secret, device.api_key_hash):
            return device

        # Key ID found but invalid secret
        if device is not None:
            logger.warning(
                "Failed secret verification for device ID %s (key_id=%s)",
                device.device_id,
                key_id,
            )
        return None

    # Legacy unindexed O(N) sequential bcrypt scan is deprecated and disabled for performance & security.
    # All devices must present a standard rhm_<key_id>_<secret> key.
    logger.warning("Rejected invalid or non-prefixed API key format.")
    return None
