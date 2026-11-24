# Remote Patient Health Monitoring System — Comprehensive Project Audit
**Generated:** November 24, 2026  
**Project Location:** `D:\Remote_Health_Monitoring_Server`  
**Classification:** Medical IoT Telemetry & Clinical Informatics Architecture Audit

---

## 1. Executive Summary

This audit establishes the baseline architectural, cryptographic, numerical, and interface state of the **Remote Patient Health Monitoring Server**. The platform is engineered to serve low-resource rural healthcare settings (specifically rural Bangladesh) utilizing low-power edge nodes (ESP32 DevKit V1) transmitting physiological telemetry over 2G cellular networks (SIM800L GPRS) and Wi-Fi to a centralized FastAPI backend and React clinical doctor dashboard.

The audit verified that the core numerical, cryptographic, and session-integrity foundations are robust. The backend test suite executes with **100% pass rate (45/45 tests passing)**, and the frontend TypeScript compilation builds cleanly with **zero type errors**.

This document details the complete system topology, API contract inventory, database schema, edge firmware behavior, baseline validation results, and an actionable roadmap for Phase 2 (UI/UX Reconstruction) and Phase 4 (Free Cloud Deployment).

---

## 2. Architecture & Component Inventory

```
+-----------------------------------------------------------------------------------+
|                              PATIENT / EDGE SENSOR LAYER                           |
|  AD8232 (ECG)      MAX30102 (HR/SpO2)     DS18B20 (Temp)    20x4 LCD & Push Buttons|
|  [GPIO 34/33/32]      [I2C 21/22]            [GPIO 4]           [GPIO 21/22, 18, 19] |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                             EDGE CONTROLLER LAYER                                  |
|  ESP32 DevKit V1: FreeRTOS Dual-Core Firmware (C++ / Arduino IDE / PlatformIO)     |
|  - Core 0: High-Priority 250 Hz ADC Sampling & Digital Filter Processing           |
|  - Core 1: Cellular Transmission (SIM800L GPRS) / Wi-Fi HTTP Client & LCD Engine   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          | HTTP POST /api/v1/ingest (API Key Auth)
                                          | HTTP GET  /api/v1/devices/{id}/inbox
                                          | HTTP POST /api/v1/devices/{id}/acknowledge
                                          v
+-----------------------------------------------------------------------------------+
|                        APPLICATION & INGESTION BACKEND                             |
|  FastAPI (Python 3.12) ASGI Application                                           |
|  - Asynchronous Database Engine: SQLAlchemy 2.0 Async ORM + aiosqlite / asyncpg    |
|  - Numerical Signal Processing: SciPy SOS Bandpass Zero-Phase Filter + NumPy       |
|  - Export Engines: Matplotlib (PNG Plotting) & Streaming CSV Waveform Exporter     |
|  - Auth & Security: PBKDF2/Bcrypt API Key Indexing + JWT HS256 Doctor Authentication|
+-----------------------------------------+-----------------------------------------+
                                          |
                                          | REST API + Bearer JWT
                                          v
+-----------------------------------------------------------------------------------+
|                         CLINICAL DOCTOR DASHBOARD                                  |
|  React 18 + TypeScript + Vite 6 Single-Page Application (SPA)                     |
|  - State Management: TanStack React Query v5 (Optimistic Updates & Auto-Polling)  |
|  - Visualization: Plotly.js High-Performance ECG Waveform Visualizer               |
|  - Navigation & Layout: React Router DOM v6 + Tailwind CSS System                 |
+-----------------------------------------------------------------------------------+
```

### Component Directory Map

| Directory / File | Component Role | Language / Framework | Critical Dependencies |
|---|---|---|---|
| `backend/app/` | Core API Server | Python 3.12, FastAPI | `fastapi`, `uvicorn`, `pydantic-settings` |
| `backend/app/models/` | Relational ORM Entities | SQLAlchemy 2.0 (Async) | `sqlalchemy`, `aiosqlite`, `asyncpg` |
| `backend/app/services/` | Business & Signal Logic | Python, SciPy, NumPy | `scipy.signal`, `numpy`, `matplotlib` |
| `backend/tests/` | Verification & Test Suite | Pytest, AnyIO | `pytest`, `pytest-asyncio`, `httpx` |
| `frontend/src/` | Clinical Doctor Dashboard | React 18, TypeScript | `@tanstack/react-query`, `axios`, `date-fns` |
| `frontend/src/pages/` | Visual Modules (12 views) | React, Tailwind, Plotly | `plotly.js`, `react-plotly.js`, `lucide-react` |
| `firmware/esp32_health_monitor/` | Physical Hardware Firmware | C++ / FreeRTOS | `HardwareSerial`, `DallasTemperature` |
| `hardware/wokwi/` | Hardware Simulation Env | Wokwi JSON / C++ | `LiquidCrystal_I2C`, `ArduinoJson` |
| `hardware/*.bat` | Production Service Launchers | Windows Batch | `cmd.exe`, `uvicorn`, `vite`, `ngrok` |
| `simulator/` | Synthetic Stream Simulator | Python | `requests`, `scipy`, `numpy` |

---

## 3. API Contract & Endpoint Inventory

The server exposes a strictly typed, OpenAPI 3.1-compliant REST interface under the `/api/v1` namespace:

### 3.1 Device Telemetry & Ingestion
- `POST /api/v1/ingest`: Device telemetry ingestion.
  - **Auth:** `X-Device-API-Key: rhm_<prefix>_<secret>`
  - **Payload:** `IngestBatchRequest` (Device ID, Patient ID, Session ID, Batch ID, Sequence Number, Timestamp, Sampling Rate 250 Hz, ECG Unit, 250 ADC samples, HR bpm, SpO2 %, Temp C, Lead Off flag, Is Simulated, Is Session End).
  - **Guarantees:** Concurrency-safe idempotent retransmission handling via composite constraints (`uq_device_batch` and `uq_session_sequence`). Rejects cross-device session hijacking with `HTTP 403` and parameter mismatches with `HTTP 409`.

### 3.2 Two-Way Device Inbox & Directives
- `GET /api/v1/devices/{device_id}/inbox`: Authenticated polling endpoint for ESP32.
  - Automatically transitions pending prescriptions to `Delivered` status with timestamp.
- `POST /api/v1/devices/{device_id}/acknowledge`: Authenticated patient hardware confirmation endpoint.
  - Updates prescription status to `Acknowledged` with `acknowledged_at` timestamp.

### 3.3 Clinical Authentication
- `POST /api/v1/auth/login`: Doctor OAuth2 password login (form-encoded username/password). Returns JWT Bearer token.
- `GET /api/v1/auth/me`: Authenticated profile retrieval.
- `POST /api/v1/auth/logout`: Revocation & session termination.

### 3.4 Patient Informatics & Directives
- `GET /api/v1/patients`: Paginated list of registered rural patients with search and archive filtering.
- `POST /api/v1/patients`: Patient registration (`patient_id`, `full_name`, `age`, `notes`).
- `GET /api/v1/patients/{patient_id}`: Patient profile and assigned hardware node.
- `PATCH /api/v1/patients/{patient_id}`: Patient demographic and clinical updates.
- `GET /api/v1/patients/{patient_id}/readings`: Longitudinal vitals history (HR, SpO2, Temp).
- `GET /api/v1/patients/{patient_id}/ecg-recordings`: Historical ECG recording sessions.
- `GET /api/v1/patients/{patient_id}/notes`: Attending physician clinical notes.
- `POST /api/v1/patients/{patient_id}/notes`: Add physician clinical observation.
- `POST /api/v1/patients/{patient_id}/prescriptions`: Author remote prescription/directive.
- `GET /api/v1/patients/{patient_id}/prescriptions`: List directives for specific patient.

### 3.5 Device Registry & Key Lifecycle
- `GET /api/v1/devices`: Inventory of registered ESP32 edge units with connection health and battery/signal status.
- `POST /api/v1/devices`: Provision new edge hardware unit.
- `GET /api/v1/devices/{device_id}`: Hardware diagnostics, firmware version, and last-seen telemetry.
- `POST /api/v1/devices/{device_id}/rotate-key`: Cryptographic rotation of device API key (returns plain key once; stores hash).
- `POST /api/v1/devices/{device_id}/revoke-key`: Immediate revocation of compromised edge node credentials.

### 3.6 ECG Signal Processing, Waveforms & Exports
- `GET /api/v1/ecg/sessions`: Paginated ECG session registry with signal quality and batch counts.
- `GET /api/v1/ecg-recordings/{recording_id}`: Session metadata and batch continuity audit.
- `GET /api/v1/ecg-recordings/{recording_id}/samples?filter=none|bandpass`: Reconstructed numerical waveform timeline.
  - Accurately reconstructs physical missing-batch dropouts (e.g. 10.0-second gaps) using NaN padding.
  - Applies 0.5–40 Hz 4th-order Butterworth Second-Order Sections (SOS) zero-phase filtering (`sosfiltfilt`).
- `GET /api/v1/ecg-recordings/{recording_id}/export.csv`: Export full numerical sample series with physical timestamps.
- `GET /api/v1/ecg-recordings/{recording_id}/plot.png`: Render publication-quality clinical ECG waveform strip.
- `POST /api/v1/ecg/sessions/{session_id}/complete`: Manual or edge-triggered session closure.

### 3.7 Health & System Observability
- `GET /api/v1/dashboard/stats`: High-level clinical telemetry counters (total patients, active sessions, alerts).
- `GET /api/v1/dashboard/recent-vitals`: Aggregated multi-patient vitals feed.
- `GET /api/v1/health`: Ingestion pipeline, database connection, and memory status check.
- `GET /api/v1/settings`: Application runtime configuration and threshold boundaries.

---

## 4. Database Schema & Data Models

The database models are constructed with strict declarative typing in SQLAlchemy 2.0 Async ORM:

```
+--------------------+       1:N       +---------------------+
|    DoctorUser      |---------------->|     DoctorNote      |
+--------------------+                 +---------------------+
          |
          | 1:N
          v
+--------------------+
|    Prescription    |
+--------------------+
     ^          ^
 1:N |          | 1:N
     |          |
+---------+   +---------+     1:N      +---------------------+
| Patient |   | Device  |------------->|    DeviceUpload     |
+---------+   +---------+              +---------------------+
     |             |
 1:N |             | 1:N
     v             v
+--------------------+        1:N      +---------------------+
|    VitalReading    |                 |      ECGBatch       |
+--------------------+                 +---------------------+
     |                                            ^
     | 1:N                                        | 1:N
     v                                            |
+--------------------+----------------------------+
|     ECGSession     |
+--------------------+
```

### Table Schema Summary

1. **`doctor_users`**: Clinician accounts. Fields: `id`, `username`, `hashed_password`, `full_name`, `email`, `is_admin`, `is_active`, `created_at`, `updated_at`.
2. **`patients`**: Rural patient index. Fields: `id`, `patient_id` (Unique, indexed), `full_name`, `age`, `notes`, `is_archived`, `created_at`, `updated_at`.
3. **`devices`**: Edge hardware index. Fields: `id`, `device_id` (Unique, indexed), `description`, `patient_id` (FK), `is_active`, `api_key_hash`, `api_key_prefix` (Indexed), `api_key_revoked_at`, `last_seen`, `last_batch_id`, `firmware_version`, `created_at`, `updated_at`.
4. **`device_uploads`**: Ingestion deduplication index. Fields: `id`, `device_id` (FK), `batch_id`, `recorded_at`, `received_at`, `status`. Constraint: `uq_device_batch` (`device_id`, `batch_id`).
5. **`ecg_sessions`**: Recording session parent. Fields: `id`, `session_id` (Unique, indexed), `patient_id` (FK), `device_id` (FK), `started_at`, `ended_at`, `sampling_rate_hz`, `unit`, `status`, `total_samples`, `total_batches`, `expected_batches`, `is_simulated`, `lead_off_count`, `signal_quality`, `ai_analysis_status`, `ai_classification`, `ai_confidence`, `notes`, `created_at`, `updated_at`.
6. **`ecg_batches`**: Sequential raw waveform chunks. Fields: `id`, `session_id` (FK), `batch_id`, `sequence_number`, `recorded_at`, `received_at`, `sampling_rate_hz`, `sample_count`, `samples_json`, `is_simulated`, `lead_off`. Constraints: `uq_session_batch` (`session_id`, `batch_id`), `uq_session_sequence` (`session_id`, `sequence_number`).
7. **`vital_readings`**: Physiological sensor records. Fields: `id`, `patient_id` (FK), `device_id` (FK), `recorded_at`, `received_at`, `heart_rate_bpm`, `spo2_percent`, `temperature_c`, `is_simulated`, `raw_payload`.
8. **`doctor_notes`**: Physician notes log. Fields: `id`, `patient_id` (FK), `doctor_id` (FK), `content`, `created_at`.
9. **`prescriptions`**: Two-way clinical directives. Fields: `id`, `patient_id` (FK), `device_id` (FK), `doctor_id` (FK), `assessment`, `medication`, `dosage`, `frequency`, `duration`, `instructions`, `follow_up_date`, `status` (`Pending` | `Delivered` | `Acknowledged`), `created_at`, `delivered_at`, `acknowledged_at`.

---

## 5. Baseline Test & Verification Results

### 5.1 Backend Pytest Suite
Executed on: `Python 3.12.10`, `pytest-8.3.4`, `FastAPI 0.115.6`.  
Command: `pytest -v`  
**Result:** **45 passed in 24.83s (100% Pass Rate)**

```
============================= test session starts =============================
tests/test_auth.py (6/6 PASSED)
  - test_login_success: PASSED
  - test_login_invalid_password: PASSED
  - test_login_unknown_user: PASSED
  - test_get_me_authenticated: PASSED
  - test_get_me_unauthenticated: PASSED
  - test_logout: PASSED

tests/test_devices.py (6/6 PASSED)
  - test_register_device: PASSED
  - test_register_duplicate_device_id: PASSED
  - test_list_devices: PASSED
  - test_get_device_detail: PASSED
  - test_rotate_device_api_key: PASSED
  - test_revoke_device_api_key: PASSED

tests/test_ecg.py (9/9 PASSED)
  - test_get_ecg_recording_metadata: PASSED
  - test_get_ecg_samples_array: PASSED
  - test_export_ecg_csv: PASSED
  - test_export_ecg_png: PASSED
  - test_ecg_session_multi_batch_ordering: PASSED
  - test_ecg_missing_sequence_gap_detection: PASSED
  - test_ecg_session_completion: PASSED
  - test_ecg_10_second_gap_physical_duration: PASSED
  - test_sos_filtering_zero_phase_and_stability: PASSED

tests/test_ingest.py (13/13 PASSED)
  - test_ingest_valid_batch: PASSED
  - test_ingest_duplicate_batch_idempotency: PASSED
  - test_concurrent_duplicate_ingest: PASSED
  - test_ds18b20_temperature_disconnect_sanitization: PASSED
  - test_ingest_invalid_api_key: PASSED
  - test_ingest_unknown_patient: PASSED
  - test_ingest_oversized_batch: PASSED
  - test_ingest_missing_required_fields: PASSED
  - test_cross_device_same_batch_id_isolation: PASSED
  - test_sequence_number_conflict_different_batch_id: PASSED
  - test_session_ownership_device_mismatch: PASSED
  - test_session_parameter_mismatch_sampling_rate_and_unit: PASSED
  - test_session_lifecycle_completed_rejects_and_incomplete_reconciles: PASSED

tests/test_integration.py (1/1 PASSED)
  - test_full_system_integration_flow: PASSED

tests/test_patients.py (7/7 PASSED)
  - test_create_patient: PASSED
  - test_create_duplicate_patient_id: PASSED
  - test_list_patients: PASSED
  - test_get_patient_by_id: PASSED
  - test_get_nonexistent_patient: PASSED
  - test_update_patient: PASSED
  - test_doctor_notes: PASSED

tests/test_prescriptions.py (3/3 PASSED)
  - test_create_and_fetch_prescription: PASSED
  - test_device_inbox_and_acknowledge_lifecycle: PASSED
  - test_acknowledge_nonexistent_message: PASSED
====================== 45 passed, 51 warnings in 24.83s =======================
```

### 5.2 Frontend Compilation & Type Integrity
Executed on: `Node.js v24.15.0`, `npm 11.12.1`, `TypeScript 5.7.2`, `Vite 6.4.6`.  
Command: `npm run test && npm run build`  
**Result:** **0 TypeScript errors, Production build generated in 23.54s.**

```
dist/index.html                                0.66 kB │ gzip:     0.37 kB
dist/assets/index-BCZspKMs.css                27.99 kB │ gzip:     5.82 kB
dist/assets/LoginPage-BSfrXD0h.js              2.52 kB │ gzip:     1.10 kB
dist/assets/SettingsPage-CSgQ_g81.js           3.18 kB │ gzip:     1.25 kB
dist/assets/DashboardPage-BdnQ-Ttr.js          3.26 kB │ gzip:     1.19 kB
dist/assets/PatientsPage-8ky3jKIr.js           6.33 kB │ gzip:     1.93 kB
dist/assets/RecordingsPage-DWvfAC2B.js         6.33 kB │ gzip:     2.00 kB
dist/assets/DeviceStatusPage-DOKJLrbH.js       7.72 kB │ gzip:     2.27 kB
dist/assets/VitalsHistoryPage-CypmeJ0y.js      8.96 kB │ gzip:     2.37 kB
dist/assets/SystemStatusPage-DJs5QstA.js       9.09 kB │ gzip:     2.21 kB
dist/assets/DevicesPage-1VbGI1OG.js            9.70 kB │ gzip:     3.05 kB
dist/assets/ECGViewerPage-D1Ojnw_k.js         10.62 kB │ gzip:     3.59 kB
dist/assets/PatientDetailPage-aq215eYE.js     12.99 kB │ gzip:     3.65 kB
dist/assets/PrescriptionsPage-DGZ7eim2.js     21.78 kB │ gzip:     4.88 kB
dist/assets/lucide-vendor-DY1pRa7x.js         20.30 kB │ gzip:     4.50 kB
dist/assets/date-fns-vendor-Btll3TRk.js       22.84 kB │ gzip:     6.44 kB
dist/assets/index-DpNl5Duq.js                 71.62 kB │ gzip:    26.31 kB
dist/assets/react-vendor-B7nZ1ans.js         207.79 kB │ gzip:    66.30 kB
dist/assets/plotly-vendor-DWgZjsj2.js      4,751.74 kB │ gzip: 1,432.73 kB
✓ built in 23.54s
```

---

## 6. Deficiency Analysis & Target Improvements

| Domain | Current Implementation | Identified Issue / Limitation | Proposed Phase 2+ Improvement |
|---|---|---|---|
| **Theme & Tone** | Fixed dark navy-950 background only | Rigid dark mode; lacks a polished clinical light mode option for medical environments | Implement dual theme system (Clinical Light / Midnight Slate) inspired by `awesome-design-md` (Linear + Oura guidelines) |
| **Typography & Hierarchy** | Generic sans-serif system stack | Flat hierarchy; difficult to scan vitals quickly during critical patient events | Introduce clinical typographic scales with tabular numbers (`font-mono` / tabular figures) for sensor values and strict text contrast |
| **ECG Waveform Styling** | Basic Plotly line plot | Plain black background without clinical grid reference | Add medical ECG grid calibration (standard 25 mm/s, 10 mm/mV background grid lines) and interactive lead gain controls |
| **Component Density** | Standard Tailwind card spacing | Wide padding causes excessive vertical scrolling on laptop screens | Implement high-density information architecture with collapsible patient vitals ribbons and refined micro-badges |
| **Database & Storage** | SQLite file on local disk (`health_monitor.db`) | Render/free-tier cloud services have ephemeral disks; SQLite will be wiped on restart | Add PostgreSQL dual-engine compatibility (`asyncpg`), environment-driven dialect switching, and migration plan |
| **Deployment Topology** | Local batch scripts and ngrok tunnel | Relies on desktop machine remaining on; no permanent public cloud deployment | Prepare `render.yaml`, Docker configuration, static frontend hosting, and environment variable templates |
| **Repository State** | Not tracked in Git; local directory only | Risk of accidental data loss; no remote version control or GitHub release | Initialize Git with rigorous `.gitignore` excluding secrets, `.env`, and DB; push to GitHub repository |

---

## 7. Audit Sign-Off

The existing codebase is structurally sound, stable, and ready for Phase 2 (Design System & Frontend Reconstruction) and Phase 4 (Free Cloud Deployment Preparation). All functional routes, mathematical filters, and hardware contracts will be strictly preserved.
