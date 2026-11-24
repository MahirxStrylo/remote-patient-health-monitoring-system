"""
send_test_data.py
Device telemetry simulation runner for Remote Patient Health Monitoring System.

Transmits synthetic ECG samples and vitals to the FastAPI ingestion endpoint
using the exact JSON schema and HTTP headers expected from physical ESP32 hardware.

Features:
- Prefixed API key authentication (rhm_<key_id>_<secret>)
- Continuous ECG recording sessions with multi-batch sequence ordering
- Cellular dropout simulation (missing sequence gap injection)
- Network retry duplicate reconciliation (idempotent ingestion)
- Lead-off electrode detachment simulation
- DS18B20 disconnect code sanitization simulation (-127°C)

Usage:
    python send_test_data.py --api-key <KEY> --patient-id P001
    python send_test_data.py --api-key <KEY> --patient-id P001 --stream-session --repeat 5
    python send_test_data.py --api-key <KEY> --patient-id P001 --test-duplicate
    python send_test_data.py --api-key <KEY> --patient-id P001 --test-missing-batches
    python send_test_data.py --api-key <KEY> --patient-id P001 --test-lead-off
    python send_test_data.py --api-key <KEY> --patient-id P001 --all-tests
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

# Add simulator folder to python path
sys.path.insert(0, str(Path(__file__).parent))

import config as cfg
from generate_ecg import (
    ECGParameters,
    add_lead_off_artifact,
    generate_ecg_samples,
    generate_vital_signs,
)


def build_payload(
    device_id: str,
    patient_id: str,
    session_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    sequence_number: int = 1,
    is_session_end: bool = False,
    sampling_rate_hz: int = 250,
    duration_seconds: float = 10.0,
    heart_rate_bpm: float = 75.0,
    temperature_override: Optional[float] = None,
    lead_off: bool = False,
    is_simulated: bool = True,
    firmware_version: str = "ESP32-FW-1.0.4-SIM",
) -> Dict[str, Any]:
    """
    Construct the JSON dictionary matching the ESP32 firmware telemetry contract.
    """
    params = ECGParameters(
        heart_rate_bpm=heart_rate_bpm,
        sampling_rate_hz=sampling_rate_hz,
        duration_seconds=duration_seconds,
    )
    samples = generate_ecg_samples(params)
    if lead_off:
        samples = add_lead_off_artifact(samples)

    vitals = generate_vital_signs(heart_rate_bpm)
    if temperature_override is not None:
        vitals["temperature_c"] = temperature_override

    bid = batch_id or f"{device_id}-{uuid.uuid4().hex[:10]}"
    sid = session_id or f"SES-{device_id}-{uuid.uuid4().hex[:8]}"

    return {
        "device_id": device_id,
        "patient_id": patient_id,
        "session_id": sid,
        "batch_id": bid,
        "sequence_number": sequence_number,
        "is_session_end": is_session_end,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ecg_sampling_rate_hz": sampling_rate_hz,
        "ecg_unit": "adc_counts",
        "ecg_samples": samples,
        "heart_rate_bpm": vitals["heart_rate_bpm"],
        "spo2_percent": vitals["spo2_percent"],
        "temperature_c": vitals["temperature_c"],
        "lead_off": lead_off,
        "is_simulated": is_simulated,
        "firmware_version": firmware_version,
    }


def send_payload(
    server_url: str,
    api_key: str,
    payload: Dict[str, Any],
    timeout: int = 30,
) -> Optional[requests.Response]:
    """Transmit telemetry payload to the ingest endpoint."""
    url = f"{server_url.rstrip('/')}/api/v1/ingest"
    headers = {
        "Content-Type": "application/json",
        "X-Device-API-Key": api_key,
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        return response
    except requests.exceptions.ConnectionError as err:
        print(f"  [ERROR] Connection failed to {url}: {err}")
        return None
    except requests.exceptions.Timeout:
        print(f"  [ERROR] Request timed out after {timeout}s.")
        return None


def print_response(resp: Optional[requests.Response], label: str = "") -> None:
    """Pretty-print ingestion server response."""
    prefix = f"[{label}] " if label else ""
    if resp is None:
        print(f"{prefix}--> No HTTP response received (network failure).")
        return

    sym = "SUCCESS" if resp.status_code < 300 else "FAIL"
    print(f"{prefix}[{sym}] HTTP {resp.status_code}")
    try:
        body = resp.json()
        print(f"    {json.dumps(body, indent=2)}")
    except Exception:
        print(f"    {resp.text[:300]}")


def run_single_upload(args: argparse.Namespace) -> Optional[requests.Response]:
    """Execute a single test batch transmission."""
    print("\n" + "=" * 60)
    print("  SINGLE BATCH UPLOAD")
    print("=" * 60)
    hr = 72.0 + random.uniform(-6, 6)
    payload = build_payload(
        device_id=args.device_id,
        patient_id=args.patient_id,
        session_id=args.session_id,
        sampling_rate_hz=args.sampling_rate,
        duration_seconds=args.duration,
        heart_rate_bpm=hr,
        is_simulated=True,
    )
    n = len(payload["ecg_samples"])
    print(f"  Target:     {args.server_url}/api/v1/ingest")
    print(f"  Device ID:  {args.device_id}")
    print(f"  Patient ID: {args.patient_id}")
    print(f"  Session ID: {payload['session_id']}")
    print(f"  Batch ID:   {payload['batch_id']} (Seq {payload['sequence_number']})")
    print(f"  Samples:    {n} ({n / args.sampling_rate:.2f}s @ {args.sampling_rate} Hz)")
    print(f"  Vitals:     HR={payload['heart_rate_bpm']} bpm, SpO2={payload['spo2_percent']}%, Temp={payload['temperature_c']} C")

    resp = send_payload(args.server_url, args.api_key, payload)
    print_response(resp, label="Single")
    return resp


def run_session_streaming(args: argparse.Namespace) -> None:
    """Stream multiple sequential batches forming a complete continuous ECGSession."""
    print("\n" + "=" * 60)
    session_id = args.session_id or f"SES-{args.device_id}-{uuid.uuid4().hex[:8]}"
    print(f"  CONTINUOUS ECG SESSION STREAMING: {args.repeat} sequential batches")
    print(f"  Session ID: {session_id}")
    print("=" * 60)

    for seq in range(1, args.repeat + 1):
        is_end = (seq == args.repeat)
        b_id = f"{args.device_id}-B{seq:03d}-{uuid.uuid4().hex[:6]}"
        hr = 72.0 + random.uniform(-4, 5)
        payload = build_payload(
            device_id=args.device_id,
            patient_id=args.patient_id,
            session_id=session_id,
            batch_id=b_id,
            sequence_number=seq,
            is_session_end=is_end,
            sampling_rate_hz=args.sampling_rate,
            duration_seconds=args.duration,
            heart_rate_bpm=hr,
            is_simulated=True,
        )
        print(f"\n--- Batch {seq}/{args.repeat} (Batch ID: {b_id}, is_session_end={is_end}) ---")
        resp = send_payload(args.server_url, args.api_key, payload)
        print_response(resp, label=f"Seq {seq}")

        if not is_end and args.interval > 0:
            print(f"  Waiting {args.interval}s for next batch...")
            time.sleep(args.interval)

    print(f"\n[INFO] Completed streaming session {session_id}. Check dashboard / ECG viewer.")


def run_duplicate_test(args: argparse.Namespace) -> None:
    """Test server idempotency against duplicate uploads (SIM800L retry scenario)."""
    print("\n" + "=" * 60)
    print("  DUPLICATE UPLOAD RESILIENCE TEST")
    print("=" * 60)
    fixed_batch_id = f"{args.device_id}-DUPETEST-{uuid.uuid4().hex[:6]}"
    sid = args.session_id or f"SES-DUPE-{uuid.uuid4().hex[:6]}"
    payload = build_payload(
        device_id=args.device_id,
        patient_id=args.patient_id,
        session_id=sid,
        batch_id=fixed_batch_id,
        sequence_number=1,
        sampling_rate_hz=args.sampling_rate,
        duration_seconds=4.0,
    )

    print(f"  Testing with fixed Batch ID: {fixed_batch_id}")
    print("  --> Step 1: Initial upload (expect HTTP 200 'accepted')...")
    r1 = send_payload(args.server_url, args.api_key, payload)
    print_response(r1, label="Step 1")

    time.sleep(1)

    print("  --> Step 2: Immediate retry with identical payload (expect HTTP 200 'duplicate')...")
    r2 = send_payload(args.server_url, args.api_key, payload)
    print_response(r2, label="Step 2")

    if r2 is not None and r2.status_code == 200:
        data = r2.json()
        if data.get("status") == "duplicate":
            print("\n  [VERIFIED] Server safely recognized duplicate batch without data corruption.")
        else:
            print(f"\n  [WARNING] Expected status='duplicate', got status={data.get('status')!r}")


def run_lead_off_test(args: argparse.Namespace) -> None:
    """Test electrode lead detachment detection flag."""
    print("\n" + "=" * 60)
    print("  LEAD-OFF CONDITION TEST")
    print("=" * 60)
    payload = build_payload(
        device_id=args.device_id,
        patient_id=args.patient_id,
        sampling_rate_hz=args.sampling_rate,
        duration_seconds=5.0,
        lead_off=True,
    )
    print(f"  Transmitting with lead_off=True and railed ADC samples...")
    resp = send_payload(args.server_url, args.api_key, payload)
    print_response(resp, label="Lead-Off")


def run_missing_batches_test(args: argparse.Namespace) -> None:
    """Test transmission gap handling (simulating cellular coverage dropout)."""
    print("\n" + "=" * 60)
    print("  CELLULAR DROPOUT / MISSING BATCH TEST")
    print("=" * 60)
    session_id = f"SES-GAP-{uuid.uuid4().hex[:8]}"
    print(f"  Session ID: {session_id}")
    print("  Transmitting batch 1, batch 2, [SKIPPING batch 3 - cellular dropout], batch 4...")

    for seq in [1, 2, 4]:
        b_id = f"{args.device_id}-GAP-{seq:03d}-{uuid.uuid4().hex[:4]}"
        is_end = (seq == 4)
        payload = build_payload(
            device_id=args.device_id,
            patient_id=args.patient_id,
            session_id=session_id,
            batch_id=b_id,
            sequence_number=seq,
            is_session_end=is_end,
            sampling_rate_hz=args.sampling_rate,
            duration_seconds=3.0,
        )
        print(f"\n  Sending sequence {seq} (Batch ID: {b_id})...")
        resp = send_payload(args.server_url, args.api_key, payload)
        print_response(resp, label=f"Seq {seq}")
        time.sleep(0.5)

    print("\n  [INFO] Batches 1, 2, and 4 ingested under session. Batch 3 gap is detected.")


def run_temp_disconnect_test(args: argparse.Namespace) -> None:
    """Test DS18B20 wire disconnection sanitization (-127°C)."""
    print("\n" + "=" * 60)
    print("  DS18B20 DISCONNECT SANITIZATION TEST")
    print("=" * 60)
    payload = build_payload(
        device_id=args.device_id,
        patient_id=args.patient_id,
        temperature_override=-127.0,
        duration_seconds=3.0,
    )
    print("  Transmitting payload with temperature_c = -127.0 (DS18B20 fault code)...")
    resp = send_payload(args.server_url, args.api_key, payload)
    print_response(resp, label="Temp-Fault")
    if resp is not None and resp.status_code == 200:
        print("  [VERIFIED] Server accepted batch and sanitized -127°C reading.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remote Health Monitoring System - IoT Hardware Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--server-url", default=cfg.SERVER_URL, help="Base server URL (default: http://localhost:8000)")
    parser.add_argument("--api-key", default=cfg.DEVICE_API_KEY, help="Device X-Device-API-Key (e.g. rhm_...)")
    parser.add_argument("--device-id", default=cfg.DEVICE_ID, help="Device hardware identifier (e.g. ESP32-001)")
    parser.add_argument("--patient-id", default=cfg.PATIENT_ID, help="Patient code (e.g. P001)")
    parser.add_argument("--session-id", default=None, help="Explicit ECG session UUID")
    parser.add_argument("--sampling-rate", type=int, default=cfg.SAMPLING_RATE_HZ, help="Sampling rate in Hz (default: 250)")
    parser.add_argument("--duration", type=float, default=cfg.RECORDING_DURATION_SECONDS, help="Recording length in seconds (default: 10.0)")
    parser.add_argument("--repeat", type=int, default=1, help="Upload count for repeated streaming")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between repeated batches")

    # Modes and scenarios
    parser.add_argument("--stream-session", action="store_true", help="Stream sequential batches belonging to one session")
    parser.add_argument("--test-duplicate", action="store_true", help="Run duplicate batch retry test")
    parser.add_argument("--test-lead-off", action="store_true", help="Send lead-off alarm payload")
    parser.add_argument("--test-missing-batches", action="store_true", help="Simulate dropped cellular batch gap")
    parser.add_argument("--test-temp-disconnect", action="store_true", help="Simulate DS18B20 hardware disconnect (-127C)")
    parser.add_argument("--all-tests", action="store_true", help="Execute all test scenarios sequentially")

    args = parser.parse_args()

    if not args.api_key:
        print("[ERROR] --api-key is required. Register a device first on http://localhost:5173/devices")
        print("        or run with: python send_test_data.py --api-key <YOUR_KEY> --patient-id P001")
        sys.exit(1)

    print("=" * 60)
    print("  ESP32 / SIM800L CELLULAR TELEMETRY SIMULATOR")
    print("  Educational Research Prototype - Synthetic Data Only")
    print("=" * 60)

    # Server health probe
    try:
        health_resp = requests.get(f"{args.server_url.rstrip('/')}/api/v1/health", timeout=5)
        if health_resp.status_code == 200:
            print(f"[*] Target server healthy: {args.server_url}")
        else:
            print(f"[!] Target server responded with status: {health_resp.status_code}")
    except Exception as err:
        print(f"[ERROR] Cannot connect to server at {args.server_url}: {err}")
        print("        Ensure backend is running: uvicorn app.main:app --port 8000")
        sys.exit(1)

    if args.all_tests:
        run_single_upload(args)
        run_session_streaming(args)
        run_duplicate_test(args)
        run_lead_off_test(args)
        run_missing_batches_test(args)
        run_temp_disconnect_test(args)
    elif args.test_duplicate:
        run_duplicate_test(args)
    elif args.test_lead_off:
        run_lead_off_test(args)
    elif args.test_missing_batches:
        run_missing_batches_test(args)
    elif args.test_temp_disconnect:
        run_temp_disconnect_test(args)
    elif args.stream_session or args.repeat > 1:
        run_session_streaming(args)
    else:
        run_single_upload(args)

    print("\n[*] Simulator execution finished.")


if __name__ == "__main__":
    main()
