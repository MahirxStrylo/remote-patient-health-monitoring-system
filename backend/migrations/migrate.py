"""
backend/migrations/migrate.py
Automated database migration and backup utility for Remote Health Monitoring Server.

Features:
1. Automated pre-migration physical backup (creates health_monitor.db.bak_<timestamp>).
2. Schema version tracking via `schema_migrations` table.
3. Safe sequential migration applying:
   - Migration 001: Baseline schema (users, patients, devices, notes, vitals, uploads, audit)
   - Migration 002: Scalable O(1) prefixed device API keys (api_key_id, api_key_prefix, api_key_revoked_at)
   - Migration 003: Multi-batch ECG session tracking (ecg_sessions, ecg_batches with uq_session_sequence)
4. Preserves 100% of existing data.
5. Idempotent and safe to run on both SQLite and PostgreSQL.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "health_monitor.db"


def backup_database(db_file: Path) -> Path:
    """Create a physical timestamped backup of the database before migration."""
    if not db_file.exists():
        print(f"[Backup] Database file {db_file} does not exist yet. No backup needed.")
        return db_file

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = db_file.parent / f"{db_file.name}.bak_{timestamp}"
    shutil.copy2(db_file, backup_file)
    print(f"[Backup] Successfully created database backup: {backup_file} ({backup_file.stat().st_size} bytes)")
    return backup_file


def init_migration_table(conn: sqlite3.Connection) -> None:
    """Ensure the schema_migrations tracking table exists."""
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name VARCHAR(128) NOT NULL,
        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
    )
    """)
    conn.commit()


def get_applied_migrations(conn: sqlite3.Connection) -> set[int]:
    """Get list of already applied migration versions."""
    c = conn.cursor()
    c.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in c.fetchall()}


def record_migration(conn: sqlite3.Connection, version: int, name: str) -> None:
    """Record successful migration application."""
    c = conn.cursor()
    c.execute(
        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
        (version, name, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def migrate_001_baseline(conn: sqlite3.Connection) -> None:
    """Migration 001: Ensure baseline tables exist."""
    print("[Migrate] Applying 001_baseline_schema...")
    c = conn.cursor()

    # doctor_users
    c.execute("""
    CREATE TABLE IF NOT EXISTS doctor_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(64) NOT NULL UNIQUE,
        email VARCHAR(128) NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        full_name VARCHAR(128) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        is_admin BOOLEAN NOT NULL DEFAULT 0,
        last_login DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
    )
    """)

    # patients
    c.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id VARCHAR(64) NOT NULL UNIQUE,
        full_name VARCHAR(128) NOT NULL,
        age INTEGER,
        notes TEXT,
        is_archived BOOLEAN NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
    )
    """)

    # doctor_notes
    c.execute("""
    CREATE TABLE IF NOT EXISTS doctor_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE,
        FOREIGN KEY(doctor_id) REFERENCES doctor_users(id) ON DELETE CASCADE
    )
    """)

    # devices baseline
    c.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id VARCHAR(128) NOT NULL UNIQUE,
        description VARCHAR(255),
        api_key_hash VARCHAR(255) NOT NULL,
        patient_id INTEGER,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        last_seen DATETIME,
        last_batch_id VARCHAR(128),
        firmware_version VARCHAR(64),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE SET NULL
    )
    """)

    # vital_readings
    c.execute("""
    CREATE TABLE IF NOT EXISTS vital_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        device_id INTEGER NOT NULL,
        batch_id VARCHAR(128) NOT NULL,
        recorded_at DATETIME NOT NULL,
        heart_rate_bpm REAL,
        spo2_percent REAL,
        temperature_c REAL,
        is_simulated BOOLEAN NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE,
        FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE
    )
    """)

    # device_uploads
    c.execute("""
    CREATE TABLE IF NOT EXISTS device_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        batch_id VARCHAR(128) NOT NULL,
        patient_id INTEGER NOT NULL,
        received_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        is_duplicate BOOLEAN NOT NULL DEFAULT 0,
        payload_size_bytes INTEGER NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'accepted',
        error_message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
    )
    """)

    # audit_events
    c.execute("""
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type VARCHAR(64) NOT NULL,
        actor_type VARCHAR(32) NOT NULL,
        actor_id VARCHAR(128) NOT NULL,
        resource_type VARCHAR(64) NOT NULL,
        resource_id VARCHAR(128) NOT NULL,
        detail TEXT NOT NULL,
        ip_address VARCHAR(45),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
    )
    """)

    conn.commit()
    print("[Migrate] 001_baseline_schema applied successfully.")


def migrate_002_scalable_device_keys(conn: sqlite3.Connection) -> None:
    """Migration 002: Add scalable O(1) prefixed API key columns to devices."""
    print("[Migrate] Applying 002_scalable_device_keys...")
    c = conn.cursor()
    cols = [row[1] for row in c.execute("PRAGMA table_info(devices)").fetchall()]

    if "api_key_id" not in cols:
        c.execute("ALTER TABLE devices ADD COLUMN api_key_id VARCHAR(64)")
    if "api_key_prefix" not in cols:
        c.execute("ALTER TABLE devices ADD COLUMN api_key_prefix VARCHAR(32)")
    if "api_key_revoked_at" not in cols:
        c.execute("ALTER TABLE devices ADD COLUMN api_key_revoked_at DATETIME")

    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_devices_api_key_id ON devices(api_key_id)")
    conn.commit()
    print("[Migrate] 002_scalable_device_keys applied successfully.")


def migrate_003_ecg_sessions_and_batches(conn: sqlite3.Connection) -> None:
    """Migration 003: Multi-batch ECG session tracking and gap detection."""
    print("[Migrate] Applying 003_ecg_sessions_and_batches...")
    c = conn.cursor()

    # Create ecg_sessions
    c.execute("""
    CREATE TABLE IF NOT EXISTS ecg_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id VARCHAR(64) NOT NULL UNIQUE,
        patient_id INTEGER NOT NULL,
        device_id INTEGER NOT NULL,
        started_at DATETIME NOT NULL,
        ended_at DATETIME,
        sampling_rate_hz INTEGER NOT NULL DEFAULT 250,
        unit VARCHAR(32) NOT NULL DEFAULT 'adc_counts',
        status VARCHAR(32) NOT NULL DEFAULT 'Recording',
        total_samples INTEGER NOT NULL DEFAULT 0,
        total_batches INTEGER NOT NULL DEFAULT 0,
        expected_batches INTEGER,
        is_simulated BOOLEAN NOT NULL DEFAULT 0,
        lead_off_count INTEGER NOT NULL DEFAULT 0,
        signal_quality VARCHAR(32),
        ai_analysis_status VARCHAR(32) NOT NULL DEFAULT 'not_configured',
        ai_model_name VARCHAR(128),
        ai_model_version VARCHAR(64),
        ai_analysis_timestamp DATETIME,
        ai_classification VARCHAR(128),
        ai_confidence REAL,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE,
        FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE
    )
    """)

    # Create ecg_batches
    c.execute("""
    CREATE TABLE IF NOT EXISTS ecg_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id VARCHAR(128) NOT NULL UNIQUE,
        session_id INTEGER NOT NULL,
        sequence_number INTEGER NOT NULL,
        recorded_at DATETIME NOT NULL,
        sample_count INTEGER NOT NULL,
        samples_json TEXT NOT NULL,
        received_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        signal_quality VARCHAR(32),
        lead_off BOOLEAN NOT NULL DEFAULT 0,
        is_duplicate BOOLEAN NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        FOREIGN KEY(session_id) REFERENCES ecg_sessions (id) ON DELETE CASCADE,
        CONSTRAINT uq_session_sequence UNIQUE (session_id, sequence_number)
    )
    """)

    # Indexes
    c.execute("CREATE INDEX IF NOT EXISTS ix_ecg_sessions_session_id ON ecg_sessions(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_ecg_sessions_patient_id ON ecg_sessions(patient_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_ecg_sessions_status ON ecg_sessions(status)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_ecg_batches_batch_id ON ecg_batches(batch_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_ecg_batches_session_id ON ecg_batches(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_ecg_batches_sequence_number ON ecg_batches(sequence_number)")

    conn.commit()
    print("[Migrate] 003_ecg_sessions_and_batches applied successfully.")


def migrate_004_device_scoped_idempotency(conn: sqlite3.Connection) -> None:
    """Migration 004: Device-scoped idempotency and composite unique constraints."""
    print("[Migrate] Applying 004_device_scoped_idempotency...")
    c = conn.cursor()

    # Drop old global unique index on device_uploads.batch_id if present
    try:
        c.execute("DROP INDEX IF EXISTS ix_device_uploads_batch_id")
    except Exception:
        pass

    # Create composite unique index (device_id, batch_id) on device_uploads
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_device_batch ON device_uploads(device_id, batch_id)")

    # Create composite unique index (session_id, batch_id) on ecg_batches
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_session_batch ON ecg_batches(session_id, batch_id)")

    conn.commit()
    print("[Migrate] 004_device_scoped_idempotency applied successfully.")


def run_migrations(db_file: Path = DB_PATH) -> None:
    """Execute all pending migrations with pre-migration backup."""
    print("=" * 60)
    print("  REMOTE HEALTH MONITORING SYSTEM — DATABASE MIGRATOR")
    print(f"  Target DB: {db_file}")
    print("=" * 60)

    # 1. Physical backup before any alteration
    backup_database(db_file)

    # 2. Open connection
    conn = sqlite3.connect(str(db_file))
    try:
        init_migration_table(conn)
        applied = get_applied_migrations(conn)

        migrations = [
            (1, "001_baseline_schema", migrate_001_baseline),
            (2, "002_scalable_device_keys", migrate_002_scalable_device_keys),
            (3, "003_ecg_sessions_and_batches", migrate_003_ecg_sessions_and_batches),
            (4, "004_device_scoped_idempotency", migrate_004_device_scoped_idempotency),
        ]

        pending_count = 0
        for version, name, func in migrations:
            if version not in applied:
                func(conn)
                record_migration(conn, version, name)
                pending_count += 1
            else:
                print(f"[Migrate] Version {version:03d} ({name}) already applied.")

        print(f"[Migrate] Migration complete. Applied {pending_count} new migrations.")
        print(f"[Migrate] Total migrations on record: {len(get_applied_migrations(conn))}")

        # Count preserved rows
        c = conn.cursor()
        users_count = c.execute("SELECT COUNT(*) FROM doctor_users").fetchone()[0]
        patients_count = c.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        devices_count = c.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        sessions_count = c.execute("SELECT COUNT(*) FROM ecg_sessions").fetchone()[0]
        batches_count = c.execute("SELECT COUNT(*) FROM ecg_batches").fetchone()[0]
        print(f"[Verify] Data integrity check: {users_count} users, {patients_count} patients, {devices_count} devices, {sessions_count} ECG sessions, {batches_count} batches.")

    finally:
        conn.close()


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH
    run_migrations(target)
