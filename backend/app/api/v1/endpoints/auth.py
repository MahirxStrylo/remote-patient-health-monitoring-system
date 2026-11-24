"""
app/api/v1/endpoints/auth.py
Doctor authentication endpoints (login, profile, logout).
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import create_access_token, verify_password
from app.database.session import get_db
from app.models.audit import AuditEvent
from app.models.doctor import DoctorUser
from app.schemas.auth import DoctorUserPublic, TokenResponse
from app.security.auth import get_current_active_doctor

logger = get_logger("app.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory sliding-window rate limiter for sensitive authentication attempts
_login_attempts: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = Lock()
LOGIN_RATE_LIMIT_MAX = 10  # Max attempts
LOGIN_RATE_LIMIT_WINDOW = 60.0  # Window in seconds


def check_login_rate_limit(client_ip: str) -> None:
    now = time.time()
    with _rate_limit_lock:
        window_start = now - LOGIN_RATE_LIMIT_WINDOW
        # Prune old timestamps
        _login_attempts[client_ip] = [t for t in _login_attempts[client_ip] if t > window_start]
        if len(_login_attempts[client_ip]) >= LOGIN_RATE_LIMIT_MAX:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication attempts. Please wait 60 seconds before trying again.",
                headers={"Retry-After": "60"},
            )
        _login_attempts[client_ip].append(now)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a doctor by username and password.
    Returns a JWT Bearer token on success.
    Enforces IP-based rate limiting against brute-force attacks.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_ip)

    result = await db.execute(
        select(DoctorUser).where(DoctorUser.username == form_data.username)
    )
    user: DoctorUser | None = result.scalar_one_or_none()

    if not user:
        logger.warning(
            "Authentication failed: Doctor account '%s' not found in database (IP: %s).",
            form_data.username,
            client_ip,
        )
        audit = AuditEvent(
            event_type="login_failed",
            actor_type="doctor",
            actor_id=form_data.username,
            detail="Failed login attempt - user not found.",
        )
        db.add(audit)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user.hashed_password):
        logger.warning(
            "Authentication failed: Invalid credentials for user '%s' (IP: %s).",
            form_data.username,
            client_ip,
        )
        audit = AuditEvent(
            event_type="login_failed",
            actor_type="doctor",
            actor_id=form_data.username,
            detail="Failed login attempt - invalid credentials.",
        )
        db.add(audit)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(
            "Authentication failed: Doctor account '%s' is deactivated (IP: %s).",
            user.username,
            client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Please contact an administrator.",
        )

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    audit = AuditEvent(
        event_type="login_success",
        actor_type="doctor",
        actor_id=user.username,
        detail=f"Doctor {user.username} successfully signed in.",
    )
    db.add(audit)
    await db.commit()

    token = create_access_token(
        data={"sub": user.username, "user_id": user.id}
    )
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    logger.info(
        "Authentication successful: Doctor '%s' signed in (IP: %s).",
        user.username,
        client_ip,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get("/me", response_model=DoctorUserPublic)
async def get_me(
    current_user: DoctorUser = Depends(get_current_active_doctor),
) -> DoctorUser:
    """Return the profile of the currently signed-in doctor."""
    return current_user


@router.post("/logout")
async def logout(
    current_user: DoctorUser = Depends(get_current_active_doctor),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a logout audit event."""
    audit = AuditEvent(
        event_type="logout",
        actor_type="doctor",
        actor_id=current_user.username,
        detail=f"Doctor {current_user.username} signed out.",
    )
    db.add(audit)
    await db.commit()
    return {"message": "Successfully logged out."}
