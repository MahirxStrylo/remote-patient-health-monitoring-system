"""
app/api/v1/router.py
Consolidated API v1 router.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    dashboard,
    devices,
    ecg,
    ingest,
    patients,
    prescriptions,
    settings,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(devices.router)
api_router.include_router(ingest.router)
api_router.include_router(ecg.router)
api_router.include_router(prescriptions.router)
api_router.include_router(dashboard.router)
api_router.include_router(settings.router)
