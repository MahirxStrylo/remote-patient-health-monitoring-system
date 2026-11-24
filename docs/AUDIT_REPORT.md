# System Audit Report — Remote Patient Health Monitoring Server

**Date:** 2026-11-22  
**Auditor:** Senior Full-Stack, IoT & Security Engineer  
**Status:** Audit Completed — Architecture Baseline Established  

---

## 1. Executive Summary

A comprehensive architectural and code-level audit was conducted on the existing Remote Patient Health Monitoring Server located at `D:\Remote_Health_Monitoring_Server`.

The codebase contains a functional foundational architecture:
- **Backend:** FastAPI with SQLAlchemy 2.0 async ORM, Pydantic v2 schemas, and SQLite (`aiosqlite`).
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, and Plotly.js.
- **Simulator:** Python CLI generator producing synthetic PQRST ECG signals.
- **Automated Tests:** 28 passing unit and integration tests.

However, several **critical architectural and security limitations** have been identified that must be resolved to meet university engineering standards and real-world deployment viability for rural Bangladesh.

---

## 2. Component-by-Component Audit

### 2.1 ECG Recording & Batch Storage (CRITICAL DEFECT)
- **Current Implementation:** Each incoming telemetry payload creates an isolated `ECGRecording` record and an `ECGBatch` with `batch_sequence = 1`.
- **Defect:** Successive uploads from the same patient monitoring event are treated as disconnected, independent recordings rather than sequential segments of an ongoing **ECG Recording Session**.
- **Impact:**
  - Doctors cannot view a continuous 1-minute, 5-minute, or 1-hour monitoring session.
  - The server cannot detect sequence gaps or missing batches across an interrupted cellular transmission.
  - The database lacks a parent-child relationship linking a continuous monitoring session to its chronological sequence of batches.
- **Required Fix:** Introduce a formal `ECGSession` (with `session_id`, `status`, `started_at`, `ended_at`, `sampling_rate_hz`, `unit`) and associate `ECGBatch` entities to the session using strict sequence numbers and database constraints.

### 2.2 Device Authentication & Scalability (CRITICAL BOTTLENECK)
- **Current Implementation:** `get_device_from_api_key()` in `app/security/device_auth.py` loads every active device (`SELECT * FROM devices WHERE is_active = True`) and executes `bcrypt.checkpw` in Python sequentially against each device's hash.
- **Defect:**
  - $O(N)$ linear scan with an intentionally slow cryptographic hashing function ($~100\text{ ms}$ per check).
  - With 50 deployed clinic nodes, verifying a single ingestion request takes ~5 seconds of 100% CPU time.
  - With 500 devices, the server would experience total denial-of-service on every incoming HTTP POST.
- **Required Fix:** Implement prefix-based key lookup (`rhm_<key_id>_<secret>`). Store an indexed non-secret `api_key_id` in the database for $O(1)$ indexed lookup, then verify the secret hash. Add key rotation and revocation timestamps.

### 2.3 Duplicate Handling & Ingestion Idempotency
- **Current Implementation:** Application-level check querying `DeviceUpload.batch_id` before inserting.
- **Defect:** Under concurrent retransmissions (e.g. SIM800L rapid retries or cellular gateway jitter), race conditions can allow duplicate batch insertion if two requests execute between the SELECT and INSERT statements.
- **Required Fix:** Enforce database-level unique constraints (`UniqueConstraint('session_id', 'sequence_number')` and `UniqueConstraint('device_id', 'batch_id')`), wrap ingestion in database transactions with concurrency error trapping, and return idempotent HTTP 200 responses with `status="duplicate"`.

### 2.4 ECG Waveform Processing & Visualization
- **Current Implementation:** Raw ADC counts are fetched and plotted directly.
- **Defects & Missing Features:**
  - No baseline wander or high-frequency noise filtering option (only raw view is available).
  - Missing batch gaps are not visually indicated; if batch 3 is lost, there is no visual discontinuity indicator.
  - No session-level multi-batch timeline view.
- **Required Fix:** Add client-side and server-side selectable filtering (preserving original raw ADC samples without overwriting), compute multi-batch chronological timeline stitching, and detect missing sequence numbers with explicit visual gap markers.

### 2.5 Security, Rate Limiting & Credentials
- **Current Implementation:** Basic JWT authentication for doctors, but no rate limiting on `/api/v1/auth/login`.
- **Defect:** Vulnerable to automated brute-force password guessing.
- **Required Fix:** Implement request rate limiting for authentication endpoints, enforce strict CORS domain allowlists, audit log rotations, and verify `.env.example` contains only placeholder credentials.

### 2.6 Sensor Validation (MAX30102 & DS18B20)
- **Current Implementation:** Pydantic schema validates basic ranges (`ge=0, le=400` for HR, `ge=20, le=60` for temperature).
- **Improvement Needed:** Enforce physiological validation boundaries, flag disconnected sensor values ($0\text{ BPM}$, $<90\% \text{ SpO}_2$, or DS18B20 disconnect codes such as $-127^\circ\text{C}$ or $85^\circ\text{C}$ power-on reset), and clearly distinguish stale telemetry ($>60$ minutes).

### 2.7 Frontend Navigation & Medical Views
- **Current Implementation:** 7 base pages exist (`Login`, `Dashboard`, `Patients`, `PatientDetail`, `ECGViewer`, `Devices`, `Settings`).
- **Defect:** Several clinical workflows required by Section 11 of the specification are missing dedicated views:
  - ECG Recording Sessions history (`/sessions` or `/recordings`).
  - Dedicated Device Status & Diagnostics (`/devices/status`).
  - Longitudinal Vital Signs History (`/vitals`).
  - System Status and Health Diagnostics (`/system`).

### 2.8 Simulator Capabilities
- **Current Implementation:** Supports single upload, duplicate test, lead-off test, and missing batch test.
- **Improvement Needed:** Add explicit session management commands: start an ECG session, stream $N$ consecutive batches with continuous sequence numbers, inject gaps, and close the session.

---

## 3. Audit Verification Matrix

| Area | Current Status | Priority | Required Action |
|---|---|---|---|
| ECG Architecture | Single-batch isolated recordings | **P0 (Critical)** | Implement `ECGSession` + `ECGBatch` data model & timeline reconstruction |
| Device API Key Auth | $O(N)$ linear bcrypt scan | **P0 (Critical)** | Implement indexed prefix lookup `rhm_<key_id>_<secret>` ($O(1)$) |
| Ingestion Idempotency | App-level check only | **P0 (Critical)** | Database unique constraints + concurrent transaction handling |
| Waveform Filter | Raw only | **P1 (High)** | Digital filtering (raw vs. filtered selectable, gap markers) |
| Security & Limits | No rate limits on login | **P1 (High)** | Rate limiter on `/auth/login`, strict CORS, secret sanitization |
| Vitals Quality | Basic range check | **P2 (Medium)** | Sensor disconnect checks ($0\text{ BPM}$, $-127^\circ\text{C}$), stale markers |
| Frontend Views | 7 pages | **P1 (High)** | Implement complete 11-page medical portal suite |
| Hardware Docs | General guide | **P1 (High)** | Address SIM800L TLS firmware limitations & gateway architecture |
| Simulator | Standalone batches | **P1 (High)** | Add session-oriented multi-batch streaming |
| Automated Tests | 28 tests passing | **P0 (Critical)** | Expand to 40+ tests covering sessions, concurrency, and filters |

---

## 4. Preservation Strategy

The existing working foundation will be strictly preserved:
- Existing database tables (`doctor_users`, `patients`, `devices`, `vital_readings`, `audit_events`, `doctor_notes`) remain intact and backwards-compatible.
- Existing frontend components, color palette, and routing are extended rather than discarded.
- All 28 current unit tests will continue to pass alongside newly introduced session and concurrency test suites.
