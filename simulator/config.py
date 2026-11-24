"""Simulator configuration."""
import os

SERVER_URL = os.environ.get('SERVER_URL', 'http://localhost:8000')
DEVICE_ID = os.environ.get('DEVICE_ID', 'ESP32-001')
PATIENT_ID = os.environ.get('PATIENT_ID', 'P001')
DEVICE_API_KEY = os.environ.get(
    'DEVICE_API_KEY',
    'rhm_80eedcd9eedb1f43_EnZ6ej9kDYl23pm0qLtnBqvpcdZgphdovZ3hSHHYgVc'
)  # Pre-configured key matching demo device ESP32-001
SAMPLING_RATE_HZ = int(os.environ.get('SAMPLING_RATE_HZ', '250'))
RECORDING_DURATION_SECONDS = float(os.environ.get('RECORDING_DURATION_SECONDS', '10'))
