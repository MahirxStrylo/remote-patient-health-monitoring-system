"""
app/schemas/__init__.py
Convenience re-exports for all Pydantic schemas.
"""
from app.schemas.auth import DoctorUserPublic, LoginRequest, TokenResponse
from app.schemas.dashboard import DashboardStats, RecentEvent
from app.schemas.device import (
    DeviceCreate,
    DevicePublic,
    DeviceRegisterResponse,
    DeviceUpdate,
)
from app.schemas.ecg import ECGBatchPublic, ECGRecordingPublic, ECGSamplesResponse
from app.schemas.ingest import IngestPayload, IngestResponse
from app.schemas.patient import PatientCreate, PatientPublic, PatientUpdate, PatientWithDevice
from app.schemas.vitals import VitalReadingPublic

__all__ = [
    # auth
    "LoginRequest",
    "TokenResponse",
    "DoctorUserPublic",
    # dashboard
    "DashboardStats",
    "RecentEvent",
    # device
    "DeviceCreate",
    "DeviceUpdate",
    "DevicePublic",
    "DeviceRegisterResponse",
    # ecg
    "ECGRecordingPublic",
    "ECGSamplesResponse",
    "ECGBatchPublic",
    # ingest
    "IngestPayload",
    "IngestResponse",
    # patient
    "PatientCreate",
    "PatientUpdate",
    "PatientPublic",
    "PatientWithDevice",
    # vitals
    "VitalReadingPublic",
]
