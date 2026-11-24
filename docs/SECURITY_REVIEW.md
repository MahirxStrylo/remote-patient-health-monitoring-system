# Cybersecurity Architecture Review & Threat Model

**System:** Remote Patient Health Monitoring System  
**Review Date:** November 23, 2026  
**Scope:** Embedded Telemetry Ingestion, API Key Lifecycle, Web Dashboard Authentication, Database Constraints, and Cellular Modem Trust Boundary  

---

## 1. Threat Modeling & Trust Boundaries

The system spans three distinct security zones with explicit trust boundaries:

```
+-----------------------------------------------------------------------------------------+
| ZONE 1: UNTRUSTED / RURAL CELLULAR FIELD                                                |
| ESP32 DevKit V1 + AD8232 + MAX30102 + DS18B20 + SIM800L Modem                           |
+-----------------------------------------------------------------------------------------+
                                         │
                                         │ 2G GPRS (GSM 850/900/1800/1900 MHz)
                                         ▼
+-----------------------------------------------------------------------------------------+
| ZONE 2: CELLULAR INGESTION GATEWAY / PRIVATE APN (TRUST BOUNDARY A)                     |
| Carrier Gateway / Secure Reverse Proxy / TLS 1.3 Termination                             |
| - Terminates GPRS / HTTP from SIM800L baseband                                          |
| - Injects client IP metadata                                                            |
| - Connects to Core Server via mutual TLS 1.3 or internal VPC                            |
+-----------------------------------------------------------------------------------------+
                                         │
                                         │ HTTPS / TLS 1.3 with Strict Header Authentication
                                         ▼
+-----------------------------------------------------------------------------------------+
| ZONE 3: CORE BACKEND & DATABASE (TRUST BOUNDARY B)                                      |
| FastAPI Server + SQLite/PostgreSQL Database                                              |
| - Enforces dual authentication (JWT for Doctors, Prefixed API Keys for Devices)          |
| - Enforces 2 MB body size limit & sample count quotas                                    |
| - Validates session ownership & device-patient bindings                                 |
| - Append-only AuditEvent logging                                                        |
+-----------------------------------------------------------------------------------------+
                                         ▲
                                         │ HTTPS / TLS 1.3 (Browser JWT Session)
+-----------------------------------------------------------------------------------------+
| ZONE 4: CLINICAL / DOCTOR WEB CLIENT                                                    |
| React + TypeScript Dashboard (Web Browser)                                               |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Security Controls & Mitigations

### 2.1 Device API Key Lifecycle & Storage
- **Pre-Shared Prefixed Tokens:** Keys follow the format `rhm_<key_id>_<secret>`:
  - `<key_id>`: 16 hex characters ($64\text{ bits}$) indexed in database for $O(1)$ query lookup.
  - `<secret>`: 32 bytes base64url ($256\text{ bits}$ entropy) cryptographically generated with `secrets.token_urlsafe(32)`.
- **Zero Plaintext Storage:** Only the Bcrypt hash (work factor 12) of `<secret>` is stored in the database.
- **Key Rotation and Revocation:** Keys can be rotated or revoked instantaneously via `POST /api/v1/devices/{device_id}/rotate-key` and `POST /api/v1/devices/{device_id}/revoke-key`. Revocation sets `api_key_revoked_at` which immediately invalidates all subsequent telemetry.
- **Mitigation of Timing & DoS Attacks:** The legacy sequential bcrypt scan was eliminated. Attackers cannot induce high CPU loads on the server by submitting forged keys.

### 2.2 Device-Scoped Idempotency & Ingestion Hijacking Prevention
- **Composite Identity:** `DeviceUpload` is constrained by `(device_id, batch_id)`. `ECGBatch` is constrained by `(session_id, batch_id)` and `(session_id, sequence_number)`.
- **Session Hijacking Mitigation:** When appending batches to an ongoing session, the server validates that `session.device_id == device.id` and `session.patient_id == patient.id`. A compromised or misconfigured device cannot inject data into another patient's ongoing ECG recording.
- **Sequence Collision Rejection:** If an attacker attempts to overwrite an already stored sequence with a different batch ID, the server rejects the request with `HTTP 409 Conflict`.

### 2.3 Denial-of-Service (DoS) and Resource Exhaustion Defense
- **Request Body Size Limit:** FastAPI HTTP middleware rejects payloads exceeding 2 MB (`MAX_BODY_SIZE_BYTES = 2 * 1024 * 1024`) with `HTTP 413 Request Entity Too Large`.
- **Sample Count Clamping:** Payloads are restricted to `MAX_ECG_SAMPLES_PER_BATCH` (default 10,000 samples).
- **CORS Lock-Down:** Configurable origin whitelist (`CORS_ORIGINS`) prevents unauthorized browser origins from accessing endpoints.

### 2.4 SIM800L GPRS & TLS Reality
- **Hardware Constraint:** The SIM800L modem baseband firmware (`SIM800 R14.18`) only supports legacy SSLv3/TLS 1.0. Modern cloud servers and CDN edge proxies enforce TLS 1.2+ with elliptic curve cipher suites (e.g. `ECDHE-RSA-AES128-GCM-SHA256`) which the SIM800L hardware cannot negotiate.
- **Architectural Solution:** For rural field deployments, cellular telemetry must route through either:
  1. A carrier-provided private APN tunnel into the hospital/clinic intranet.
  2. A local cellular ingestion gateway proxy that bridges SIM800L HTTP into a secure TLS 1.3 tunnel to the main FastAPI application.
- **Doctor Web Clients:** All doctor access to the web dashboard and REST API strictly mandates TLS 1.3 with HTTPS.

---

## 3. Residual Risks & Production Recommendations

1. **Production Database:** Transition from SQLite to PostgreSQL (`asyncpg`) for high-concurrency production deployments. The SQLAlchemy models and Alembic migrations are PostgreSQL-ready.
2. **Key Storage on ESP32:** In physical deployments, the device API key must be stored in ESP32 encrypted NVS (Non-Volatile Storage) with Flash Encryption enabled to prevent physical firmware extraction.
3. **Medical Prototype Disclaimer:** As stated in the system disclaimer, this application is an educational engineering prototype and is not certified for clinical emergency alerting or definitive medical diagnosis.
