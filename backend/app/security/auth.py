"""
app/security/auth.py
FastAPI dependencies for authenticating doctor/clinical users via JWT.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.doctor import DoctorUser

# The tokenUrl must match the login endpoint path.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_doctor(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DoctorUser:
    """
    Decode the JWT from the ``Authorization: Bearer …`` header and return the
    corresponding ``DoctorUser``.

    Raises ``401 Unauthorized`` if:
    - The token is missing, malformed, or expired.
    - The ``sub`` claim does not correspond to an existing user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str | None = payload.get("sub")
    if not username:
        raise credentials_exception

    result = await db.execute(
        select(DoctorUser).where(DoctorUser.username == username)
    )
    doctor = result.scalar_one_or_none()
    if doctor is None:
        raise credentials_exception

    return doctor


async def get_current_active_doctor(
    doctor: Annotated[DoctorUser, Depends(get_current_doctor)],
) -> DoctorUser:
    """
    Extend ``get_current_doctor`` by enforcing that the account is active.

    Raises ``403 Forbidden`` for deactivated accounts.
    """
    if not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
    return doctor


async def require_admin(
    doctor: Annotated[DoctorUser, Depends(get_current_active_doctor)],
) -> DoctorUser:
    """
    Extend ``get_current_active_doctor`` by enforcing admin privileges.

    Raises ``403 Forbidden`` for non-admin accounts.
    """
    if not doctor.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required.",
        )
    return doctor
