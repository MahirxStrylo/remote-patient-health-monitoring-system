# Security, Authentication & Deployment Guide

This document describes the cybersecurity controls, device authentication architecture, cryptographic practices, and production deployment guidelines for the Remote Patient Health Monitoring System.

---

## 1. Authentication & Access Control

### 1.1 Dual Authentication Model

The platform strictly isolates **doctor user access** from **embedded device ingestion**:

| Domain | Mechanism | Credentials | Target Scope |
|---|---|---|---|
| **Doctor / Staff** | JWT Bearer Token (OAuth2) | Username + Bcrypt password | Management endpoints, patient records, ECG visualizer |
| **IoT Hardware** | Pre-shared API Key | Cryptographic high-entropy key via `X-Device-API-Key` | Ingest endpoint (`POST /api/v1/ingest`) only |

### 1.2 Password Hashing
- Passwords are hashed using standard **Bcrypt** with dynamic work factors.
- Passwords are never stored or logged in plaintext.
- The default initial administrator account (`admin`) is created via `init_db.py` and should be immediately updated in production.

### 1.3 Scalable Device API Key Management ($O(1)$ Indexed Lookup)
- Device API keys use the structured format `rhm_<key_id>_<secret>`.
- `<key_id>` is an indexed public identifier enabling high-performance $O(1)$ lookups without full-table bcrypt scans.
- `<secret>` provides 256 bits of cryptographically secure entropy.
- When a device is registered via `POST /api/v1/devices`, the full plaintext API key is returned **exactly once**.
- The server stores only the Bcrypt hash (`api_key_hash`) in the `devices` table.
- Compromising the database does not reveal plaintext device API keys.
- Key rotation and revocation are fully supported via `/api/v1/devices/{device_id}/rotate-key` and `/api/v1/devices/{device_id}/revoke-key`.

---

## 2. Ingestion Defense & Anti-Replay

1. **Device-Scoped Duplicate Batch Idempotency**:
   - Every upload is scoped to the device via composite unique constraints: `(device_id, batch_id)` on `device_uploads` and `(session_id, batch_id)` on `ecg_batches`.
   - Distinct devices using common batch names do not collide.
   - Retransmissions from the same device are idempotently acknowledged as `status="duplicate"` without creating duplicate entries or corrupting session metrics.
   - Submitting a different batch ID for an existing sequence number returns `HTTP 409 Conflict`.
2. **Payload Size & Sample Limits**:
   - An HTTP middleware enforces a strict **2 MB request-body size limit** (`MAX_BODY_SIZE_BYTES = 2 * 1024 * 1024`), rejecting oversized requests with `HTTP 413`.
   - The maximum number of samples in a single batch is capped by `MAX_ECG_SAMPLES_PER_BATCH` (10,000 samples).
3. **Strict Session Ownership & Device-Patient Binding**:
   - Devices cannot inject telemetry into an existing session started by another device (`HTTP 403 Forbidden`).
   - Telemetry claiming a mismatched patient ID is rejected with `HTTP 403 Forbidden`.
   - Telemetry with conflicting sampling frequencies or ECG units is rejected with `HTTP 409 Conflict`.
   - Sessions marked `Completed` reject further batch append attempts (`HTTP 409 Conflict`).

---

## 3. Cellular Ingestion Gateway & SIM800L Trust Boundary

The SIM800L modem baseband firmware (`SIM800 R14.18`) has legacy SSL/TLS limitations and cannot negotiate modern TLS 1.3 or elliptic-curve cipher suites.

### Deployment Trust Boundary:
1. **Field Network (2G GPRS):** The SIM800L communicates across the cellular carrier's 2G network.
2. **Ingestion Gateway / Private APN:** Telemetry reaches a dedicated cellular gateway proxy or private APN endpoint. The gateway validates initial network boundaries and forwards the requests via modern TLS 1.3 to the FastAPI core backend.
3. **Doctor Web Access:** Web dashboard users always connect directly over modern HTTPS with TLS 1.3 and JWT Bearer token authentication.

---

## 4. Audit Logging

All security-critical actions are recorded in an append-only `audit_events` table:
- `login_success` and `login_failed`
- `patient_created` and `patient_updated`
- `device_registered` and `device_updated`
- `ecg_uploaded`
- `auth_failed` and `ingest_error`

Audit rows include the timestamp, actor type (`doctor`, `device`, `system`), actor ID, IP address, and detail string.

---

## 4. Production Deployment & Hardening Checklist

1. **Enforce HTTPS / TLS 1.3**:
   - Place Uvicorn behind a reverse proxy (Nginx, Caddy, or Cloudflare) configured with automated Let's Encrypt certificates.
   - Force HTTP $\to$ HTTPS redirection.
2. **Set Strong Secrets**:
   - Change `SECRET_KEY` in `.env` to a 64-character random string (`openssl rand -hex 32`).
   - Change `ADMIN_PASSWORD` in `.env`.
3. **Database Migration to PostgreSQL**:
   - In `.env`, change `DATABASE_URL` to `postgresql+asyncpg://user:password@localhost/health_db`.
   - Configure automated daily database backups via `pg_dump`.
4. **CORS Restrictions**:
   - In production, set `CORS_ORIGINS` strictly to your production domain (e.g. `https://monitor.hospital.org`).
