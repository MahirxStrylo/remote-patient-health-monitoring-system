"""
run_demo.py
Interactive End-to-End Demonstration Script for University Evaluators.

Demonstrates the complete data flow:
ESP32 (Sensors) -> SIM800L 2G/GPRS -> FastAPI Server -> SQLite Database -> React Dashboard.

Usage:
    python run_demo.py
"""
import os
import sys
import time
import requests
from datetime import datetime

# Add simulator folder to python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "simulator"))

from simulator.send_test_data import build_payload, send_payload, print_response
import simulator.config as cfg

def main():
    print("=" * 65)
    print("  REMOTE PATIENT HEALTH MONITORING SYSTEM — LIVE DEMO")
    print("  University Engineering Prototype Demonstration")
    print("=" * 65)
    print(f"  Target Server: {cfg.SERVER_URL}")
    print(f"  Device ID:     {cfg.DEVICE_ID}")
    print(f"  Patient ID:    {cfg.PATIENT_ID}")
    print(f"  API Key:       {cfg.DEVICE_API_KEY[:20]}... (Pre-configured)")
    print("=" * 65)

    # 1. Check if backend is running
    print("\n[Step 1/3] Testing FastAPI server health probe...")
    try:
        r = requests.get(f"{cfg.SERVER_URL.rstrip('/')}/api/v1/health", timeout=3)
        if r.status_code == 200:
            print("  [OK] FastAPI backend is ONLINE and healthy.")
        else:
            print(f"  [WARN] Backend responded with status {r.status_code}.")
    except Exception as e:
        print(f"  [ERROR] Cannot connect to FastAPI backend at {cfg.SERVER_URL}.")
        print("  Please start the backend in a separate terminal:")
        print("     cd backend")
        print("     uvicorn app.main:app --host 0.0.0.0 --port 8000")
        print("  Then re-run this demo script.")
        sys.exit(1)

    # 2. Check if frontend is running (optional advisory)
    print("\n[Step 2/3] Checking React doctor dashboard...")
    try:
        rf = requests.get("http://localhost:5173", timeout=2)
        if rf.status_code == 200:
            print("  [OK] React Dashboard is ONLINE at http://localhost:5173")
    except Exception:
        print("  [ADVISORY] React frontend is not detected on http://localhost:5173.")
        print("  To view the web dashboard in your browser, open another terminal:")
        print("     cd frontend")
        print("     npm run dev")

    # 3. Stream sequential telemetry batches
    print("\n[Step 3/3] Streaming live ESP32 telemetry batches to the server...")
    session_id = f"SES-DEMO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    print(f"  Session ID: {session_id}")
    print("  Simulating 5 sequential batches (250 Hz AD8232 ECG, HR, SpO2, Temp)...")

    num_batches = 5
    for seq in range(1, num_batches + 1):
        is_end = (seq == num_batches)
        payload = build_payload(
            device_id=cfg.DEVICE_ID,
            patient_id=cfg.PATIENT_ID,
            session_id=session_id,
            batch_id=f"{cfg.DEVICE_ID}-B{seq:03d}",
            sequence_number=seq,
            is_session_end=is_end,
            sampling_rate_hz=250,
            duration_seconds=2.0,  # 500 samples per batch
            heart_rate_bpm=74.0 + (seq % 3),
        )

        print(f"\n  >> Transmitting Batch {seq}/{num_batches} (HR: {payload['heart_rate_bpm']} bpm, SpO2: {payload['spo2_percent']}%, Temp: {payload['temperature_c']} C)...")
        resp = send_payload(cfg.SERVER_URL, cfg.DEVICE_API_KEY, payload)
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            print(f"     Status: {data.get('status')} | Accepted: {data.get('accepted_samples')} samples | Batch ID: {data.get('batch_id')}")
        else:
            status_code = resp.status_code if resp else 'No response'
            print(f"     [FAILED] Status {status_code}: {resp.text if resp else ''}")

        if not is_end:
            time.sleep(1.0)

    print("\n" + "=" * 65)
    print("  DEMO TELEMETRY COMPLETED SUCCESSFULLY!")
    print("=" * 65)
    print("  You can now view the results in the Doctor Dashboard:")
    print("  1. Open http://localhost:5173 in your web browser")
    print("  2. Login with credentials:")
    print("     - Username: admin")
    print("     - Password: secret")
    print(f"  3. Open Patient 'P001' to view the latest physiological readings")
    print(f"  4. Open ECG Recordings to inspect the live reconstructed waveform:")
    print(f"     http://localhost:5173/ecg-viewer/{session_id}")
    print("=" * 65)

if __name__ == "__main__":
    main()
