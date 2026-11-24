# REST API Documentation — Remote Patient Health Monitoring System

The Remote Health Monitoring System provides a production-grade, RESTful JSON API.

- Base URL: `http://localhost:8000/api/v1`
- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc Documentation: `http://localhost:8000/redoc`

---

## 1. Authentication Schemes

The API uses two distinct, decoupled authentication mechanisms:

### 1.1. Doctor Authentication (`Bearer <JWT>`)
- Header: `Authorization: Bearer <access_token>`
- Acquired via `POST /api/v1/auth/login` (`application/x-www-form-urlencoded`).
- Authenticates physicians for clinical management, patient records, device provisioning, and ECG analysis.
- Protected by sliding-window IP rate limiting (10 attempts / minute).

### 1.2. Scalable Device Telemetry Authentication (`X-Device-API-Key`)
- Header: `X-Device-API-Key: rhm_<key_id>_<secret>`
- Formatted as `rhm_<key_id>_<secret>` (e.g. `rhm_80eedcd9eedb1f43_EnZ6ej9kDYl23pm0qLtnBqvpcdZgphdovZ3hSHHYgVc`).
  - `<key_id>`: 16-character public hex identifier for indexed $O(1)$ database lookup.
  - `<secret>`: 256-bit cryptographically random token.
  - Database stores only the Bcrypt hash (12 rounds) of the secret.
  - Supports key rotation (`POST /api/v1/devices/{id}/rotate-key`) and instant revocation (`POST /api/v1/devices/{id}/revoke-key`).
- Used exclusively on `POST /api/v1/ingest`.

---

## 2. Endpoints Summary

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/health` | None | System health check and status |
| `POST` | `/api/v1/auth/login` | None | Doctor login (OAuth2 form-urlencoded, rate-limited) |
| `GET` | `/api/v1/auth/me` | Doctor | Get current authenticated doctor profile |
| `POST` | `/api/v1/auth/logout` | Doctor | Record doctor logout event in audit trail |
| `GET` | `/api/v1/dashboard/stats` | Doctor | Real-time aggregate statistics & audit feed |
| `GET` | `/api/v1/patients` | Doctor | List / search paginated patients (`?search=&page=&size=`) |
| `POST` | `/api/v1/patients` | Doctor | Register a new patient record |
| `GET` | `/api/v1/patients/{patient_id}` | Doctor | Get patient details by clinical patient ID |
| `PATCH` | `/api/v1/patients/{patient_id}` | Doctor | Update patient demographics or archive status |
| `GET` | `/api/v1/patients/{patient_id}/readings` | Doctor | Retrieve patient historical vital signs |
| `GET` | `/api/v1/patients/{patient_id}/ecg-recordings` | Doctor | List patient ECG sessions |
| `GET` | `/api/v1/patients/{patient_id}/notes` | Doctor | List clinical doctor notes for patient |
| `POST` | `/api/v1/patients/{patient_id}/notes` | Doctor | Add clinical doctor note |
| `GET` | `/api/v1/devices` | Doctor | List all registered devices with key prefixes |
| `POST` | `/api/v1/devices` | Doctor | Register a new device (returns plain key once) |
| `GET` | `/api/v1/devices/{device_id}` | Doctor | Get device telemetry details |
| `PATCH` | `/api/v1/devices/{device_id}` | Doctor | Update device assignment, status, or description |
| `POST` | `/api/v1/devices/{device_id}/rotate-key` | Doctor | Rotate device API key (returns new key once) |
| `POST` | `/api/v1/devices/{device_id}/revoke-key` | Doctor | Immediately revoke device API key |
| `POST` | `/api/v1/ingest` | Device | Ingest ECG batch & vitals from IoT hardware |
| `GET` | `/api/v1/ecg/sessions` | Doctor | List paginated multi-batch ECG sessions |
| `GET` | `/api/v1/ecg/sessions/{session_id}` | Doctor | Get ECG session metadata & batch status |
| `GET` | `/api/v1/ecg/sessions/{session_id}/samples` | Doctor | Reconstruct timeline, raw ADC & filtered samples |
| `POST` | `/api/v1/ecg/sessions/{session_id}/complete` | Doctor | Finalize ECG session & detect missing batches |
| `GET` | `/api/v1/ecg/sessions/{session_id}/export.csv` | Doctor | Export RFC 4180 CSV with dual tracks & metadata |
| `GET` | `/api/v1/ecg/sessions/{session_id}/plot.png` | Doctor | Render diagnostic PNG ECG waveform strip |
| `GET` | `/api/v1/settings` | Doctor | Get system configuration & database status |

---

## 3. Telemetry Ingestion API

`POST /api/v1/ingest`

### Request Headers
- `Content-Type: application/json`
- `X-Device-API-Key: rhm_<key_id>_<secret>`

### Payload Schema
```json
{
  "device_id": "ESP32-001",
  "patient_id": "P001",
  "session_id": "SES-ESP32-001-2906c652",
  "batch_id": "ESP32-001-B001-aa72e9",
  "sequence_number": 1,
  "is_session_end": false,
  "expected_batches": 5,
  "recorded_at": "2026-11-22T13:47:40Z",
  "ecg_sampling_rate_hz": 250,
  "ecg_unit": "adc_counts",
  "ecg_samples": [512, 518, 525, 540, 590, 720, 950, 780, 610, 540],
  "heart_rate_bpm": 69.6,
  "spo2_percent": 97.3,
  "temperature_c": 36.4,
  "lead_off": false,
  "is_simulated": true,
  "firmware_version": "ESP32-FW-1.0.4-SIM"
}
```

### Success Response (`HTTP 200 OK`)
```json
{
  "batch_id": "ESP32-001-B001-aa72e9",
  "session_id": "SES-ESP32-001-2906c652",
  "sequence_number": 1,
  "recording_id": "SES-ESP32-001-2906c652",
  "accepted_samples": 2500,
  "status": "accepted",
  "message": "Batch accepted. 2500 ECG samples stored under session SES-ESP32-001-2906c652.",
  "missing_batches_detected": []
}
```

### Duplicate Ingestion Response (`HTTP 200 OK`)
When the same batch is retransmitted due to cellular network ack loss:
```json
{
  "batch_id": "ESP32-001-B001-aa72e9",
  "session_id": "SES-ESP32-001-2906c652",
  "sequence_number": 1,
  "recording_id": "SES-ESP32-001-2906c652",
  "accepted_samples": 0,
  "status": "duplicate",
  "message": "Duplicate batch already stored. Acknowledged without reprocessing.",
  "missing_batches_detected": []
}
```

---

## 4. ECG Timeline Reconstruction API

`GET /api/v1/ecg/sessions/{session_id}/samples`

Reconstructs all sequential batches belonging to an ECG monitoring session:
- Assembles numerical samples in order of `sequence_number`.
- Detects missing batch numbers (e.g. sequence 1, 2, 4 -> missing `[3]`).
- Inserts `null` values across dropped batches so waveform visualizers display an explicit gap rather than connecting lines falsely across missing intervals.
- Generates zero-phase 0.5–40 Hz digital bandpass-filtered signal on the fly.
- Preserves raw ADC counts untouched (`unit: adc_counts`).

### Response Schema:
```json
{
  "recording_id": "SES-GAP-2e94b5fc",
  "session_id": "SES-GAP-2e94b5fc",
  "status": "Incomplete",
  "sampling_rate_hz": 250,
  "ecg_unit": "adc_counts",
  "samples": [512, 518, null, 520, 530],
  "filtered_samples": [0.012, 0.045, null, 0.038, 0.052],
  "sample_count": 2250,
  "duration_seconds": 9.0,
  "recorded_at": "2026-11-22T13:47:30Z",
  "is_simulated": true,
  "has_gaps": true,
  "missing_sequences": [3],
  "batches": [
    {
      "batch_id": "ESP32-001-GAP-001-4d4c",
      "sequence_number": 1,
      "sample_count": 750,
      "recorded_at": "2026-11-22T13:47:30Z",
      "received_at": "2026-11-22T13:47:30Z",
      "signal_quality": "good",
      "lead_off": false
    }
  ]
}
```
