"""
app/models/__init__.py
Centralised import of all ORM models.

Importing this package guarantees that every model class is registered on
``Base.metadata`` before ``init_db()`` calls ``create_all()``.
"""
from app.models.audit import AuditEvent, DoctorNote
from app.models.device import Device
from app.models.doctor import DoctorUser
from app.models.ecg import ECGBatch, ECGRecording, ECGSession
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.vitals import DeviceUpload, VitalReading

__all__ = [
    "AuditEvent",
    "Device",
    "DeviceUpload",
    "DoctorNote",
    "DoctorUser",
    "ECGBatch",
    "ECGRecording",
    "ECGSession",
    "Patient",
    "Prescription",
    "VitalReading",
]
