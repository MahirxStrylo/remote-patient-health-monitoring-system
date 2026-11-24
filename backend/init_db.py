"""
init_db.py
Database initialization and administrator provisioning script.

Usage:
    python init_db.py
    python init_db.py --admin-username admin --admin-password secret
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Ensure backend package root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.database.session import AsyncSessionLocal, init_db
from app.models.doctor import DoctorUser


async def provision_admin(
    username: str, password: str, full_name: str = "System Administrator"
) -> None:
    """Create default administrator account if not present."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(DoctorUser).where(DoctorUser.username == username)
        )
        existing = res.scalar_one_or_none()
        if existing is not None:
            print(f"[INFO] Admin user '{username}' already exists. Skipping creation.")
            return

        admin = DoctorUser(
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
            email=f"{username}@health-monitor.local",
            is_active=True,
            is_admin=True,
        )
        db.add(admin)
        await db.commit()
        print(f"[SUCCESS] Initial admin account '{username}' created successfully.")


async def provision_demo_data() -> None:
    """Provision demo patient and ESP32 device with pre-configured API key for instant university demonstrations."""
    from app.models.patient import Patient
    from app.models.device import Device
    from app.security.device_auth import hash_device_api_key

    demo_key_id = "80eedcd9eedb1f43"
    demo_secret = "EnZ6ej9kDYl23pm0qLtnBqvpcdZgphdovZ3hSHHYgVc"
    demo_full_key = f"rhm_{demo_key_id}_{demo_secret}"

    async with AsyncSessionLocal() as db:
        # Check / provision patient P001
        res_p = await db.execute(select(Patient).where(Patient.patient_id == "P001"))
        patient = res_p.scalar_one_or_none()
        if patient is None:
            patient = Patient(
                patient_id="P001",
                full_name="Rahim Uddin",
                age=58,
                notes="Rural patient monitoring program (Sylhet). History of mild hypertension.",
            )
            db.add(patient)
            await db.flush()
            print("[SUCCESS] Demo patient 'P001' (Rahim Uddin) created.")
        else:
            print(f"[INFO] Demo patient 'P001' ({patient.full_name}) already exists.")

        # Check / provision device ESP32-001
        res_d = await db.execute(select(Device).where(Device.device_id == "ESP32-001"))
        device = res_d.scalar_one_or_none()
        if device is None:
            device = Device(
                device_id="ESP32-001",
                description="ESP32 DevKit V1 + SIM800L Telemetry Node",
                patient_id=patient.id,
                api_key_id=demo_key_id,
                api_key_prefix=f"rhm_{demo_key_id}",
                api_key_hash=hash_device_api_key(demo_secret),
                is_active=True,
            )
            db.add(device)
            await db.commit()
            print(f"[SUCCESS] Demo device 'ESP32-001' created with key: {demo_full_key}")
        else:
            if not device.api_key_id:
                device.api_key_id = demo_key_id
                device.api_key_prefix = f"rhm_{demo_key_id}"
                device.api_key_hash = hash_device_api_key(demo_secret)
                device.patient_id = patient.id
                device.is_active = True
                await db.commit()
                print(f"[INFO] Configured demo API key on existing device 'ESP32-001': {demo_full_key}")
            else:
                print(f"[INFO] Demo device 'ESP32-001' already configured.")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize database tables and create initial administrator."
    )
    parser.add_argument(
        "--admin-username",
        default=settings.ADMIN_USERNAME,
        help="Initial admin username (default from settings)",
    )
    parser.add_argument(
        "--admin-password",
        default=settings.ADMIN_PASSWORD,
        help="Initial admin password (default from settings)",
    )
    parser.add_argument(
        "--admin-name",
        default="System Administrator",
        help="Full display name for the admin user",
    )
    args = parser.parse_args()

    print("[*] Initializing database tables...")
    await init_db()
    print("[*] Tables verified.")

    print(f"[*] Provisioning administrator account '{args.admin_username}'...")
    await provision_admin(args.admin_username, args.admin_password, args.admin_name)
    print("[*] Provisioning demo patient and device...")
    await provision_demo_data()
    print("[*] Database initialization complete.")


if __name__ == "__main__":
    asyncio.run(main())
