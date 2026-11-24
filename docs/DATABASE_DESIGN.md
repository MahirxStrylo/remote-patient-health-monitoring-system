# Database Design — Remote Patient Health Monitoring System

This document describes the schema architecture, entities, indexes, relationships, and data storage design implemented in SQLite (with direct migration compatibility for PostgreSQL).

---

## Entity-Relationship Diagram

```
 +------------------+           +------------------+
 |    DoctorUser    |           |     Patient      |
 |------------------|           |------------------|
 | id (PK)          |           | id (PK)          |
 | username (UQ)    |           | patient_id (UQ)  |<-------+
 | hashed_password  |           | full_name        |        |
 | email            |           | age              |        |
 | is_active        |           | notes            |        |
 | is_admin         |           | is_archived      |        |
 +--------+---------+           +---+----+----+----+        |
          |                         |    |    |             |
          | 1:N                     |    |    |             |
          v                         |    |    |             |
 +------------------+               |    |    |             |
 |    DoctorNote    |<--------------+    |    |             |
 |------------------| 1:N                |    |             |
 | id (PK)          |                    |    |             |
 | patient_id (FK)  |                    |    |             |
 | doctor_id (FK)   |                    |    |             |
 | content          |                    |    |             |
 +------------------+                    |    |             |
                                         |    |             |
          +------------------------------+    |             |
          | 1:N                               | 1:N         |
          v                                   v             |
 +------------------+               +------------------+    |
 |   VitalReading   |               |   ECGRecording   |    |
 |------------------|               |------------------|    |
 | id (PK)          |               | id (PK)          |    |
 | patient_id (FK)  |               | recording_id(UQ) |    |
 | device_id (FK)   |               | patient_id (FK)  |    |
 | batch_id         |               | device_id (FK)   |    |
 | recorded_at (IX) |               | batch_id (IX)    |    |
 | heart_rate_bpm   |               | sampling_rate_hz |    |
 | spo2_percent     |               | sample_count     |    |
 | temperature_c    |               | ecg_unit         |    |
 | is_simulated     |               | is_simulated     |    |
 +------------------+               | lead_off         |    |
                                    | signal_quality   |    |
                                    | ai_analysis_*    |    |
                                    +--------+---------+    |
                                             | 1:N          |
                                             v              |
                                    +------------------+    |
                                    |     ECGBatch     |    |
                                    |------------------|    |
                                    | id (PK)          |    |
                                    | recording_id(FK) |    |
                                    | batch_id (IX)    |    |
                                    | batch_sequence   |    |
                                    | samples_json     |    |
                                    | sample_count     |    |
                                    | is_duplicate     |    |
                                    +------------------+    |
                                                            |
                                                            |
 +------------------+                                       |
 |      Device      |                                       |
 |------------------|                                       |
 | id (PK)          |                                       |
 | device_id (UQ)   |                                       |
 | description      |                                       |
 | api_key_hash     |                                       |
 | patient_id (FK)  |---------------------------------------+ (Assigned to)
 | is_active        |
 | last_seen        |
 | last_batch_id    |
 +--------+---------+
          | 1:N
          v
 +------------------+               +------------------+
 |   DeviceUpload   |               |    AuditEvent    |
 |------------------|               |------------------|
 | id (PK)          |               | id (PK)          |
 | device_id (FK)   |               | event_type (IX)  |
 | batch_id (UQ)    |               | actor_type       |
 | patient_id (FK)  |               | actor_id         |
 | status           |               | resource_type    |
 | payload_size     |               | resource_id      |
 | is_duplicate     |               | detail           |
 +------------------+               | ip_address       |
                                    | created_at (IX)  |
                                    +------------------+
```

---

## ECG Numerical Sample Storage Rationale

A standard 10-second ECG recording at $250\text{ Hz}$ produces $2,500$ discrete integers. Storing each individual sample as an independent database row would result in millions of rows for just a few minutes of recording, causing severe indexing overhead and high I/O latency.

### Implemented Approach: Structured `ECGBatch` JSON Chunks

1. **`ecg_recordings` table**: Stores session-level metadata (patient, device, duration, unit, sampling frequency, lead status, AI classification stub).
2. **`ecg_batches` table**: Stores chronological segments of raw samples encoded as JSON arrays (`samples_json`) alongside batch sequence numbering.
   - For SQLite, JSON text storage with batch chunking provides sub-millisecond retrieval of 2,500–10,000 samples.
   - For PostgreSQL migration, this column seamlessly converts to `jsonb` or binary `BYTEA` arrays.

---

## Schema Migration Readiness

All models use standard SQLAlchemy 2.0 type mapping:
- Timestamps use `DateTime(timezone=True)`.
- Foreign keys use explicit `ondelete` cascading (`CASCADE` for dependent records, `SET NULL` for device-patient assignments).
- Integer and String columns specify lengths compatible with PostgreSQL / MySQL / SQLite.
- To switch to PostgreSQL in production, update `DATABASE_URL` in `.env` to `postgresql+asyncpg://user:pass@host/dbname`. No schema modifications are required.
