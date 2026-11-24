# Remote Health Monitoring System — IoT Hardware Simulator

This directory contains the Python-based hardware emulator that generates realistic synthetic physiological data and transmits it to the backend server using the exact same REST API and JSON contract required for physical ESP32 + SIM800L firmware.

## Architecture

```
[generate_ecg.py] ──> Synthetic PQRST + Vitals ──> [send_test_data.py]
                                                           │
                                             HTTP POST /api/v1/ingest
                                             Header: X-Device-API-Key
                                                           ▼
                                                FastAPI Backend
```

## Features

1. **Synthetic PQRST ECG**:
   - Realistic wavelets for P-wave, Q-wave, sharp R-peak, S-wave, and T-wave.
   - Respiration baseline wander (0.25 Hz).
   - Thermal / muscular Gaussian noise.
   - Values in ADC counts (10-bit / 12-bit range, centered around baseline 512).
2. **Vital Signs Generation**:
   - Heart rate (BPM) with subtle physiological jitter.
   - Blood oxygen saturation ($SpO_2$ %).
   - Body temperature (°C) modeling digital DS18B20 sensing.
3. **Hardware Simulation Modes**:
   - Single batch upload (e.g. 2,500 samples at 250 Hz = 10s).
   - Periodic recurring uploads (`--repeat N --interval S`).
   - Duplicate batch retry test (verifying idempotency).
   - Lead-off electrode disconnection (`--test-lead-off`).
   - Cellular gap / missing batch simulation (`--test-missing-batches`).

## Installation

```bash
pip install requests numpy
```

## How to Run

### Step 1: Obtain an API Key
Start the server and frontend. Go to **Devices** (`http://localhost:5173/devices`), click **Register Device**, and enter `ESP32-001`. Copy the generated API key.

### Step 2: Send a 10-Second Test Recording
```bash
python send_test_data.py --api-key <YOUR_KEY> --patient-id P001
```

### Step 3: Run Continuous Monitoring (5 Batches Every 5s)
```bash
python send_test_data.py --api-key <YOUR_KEY> --patient-id P001 --repeat 5 --interval 5
```

### Step 4: Test Duplicate Batch Idempotency
```bash
python send_test_data.py --api-key <YOUR_KEY> --patient-id P001 --test-duplicate
```

### Step 5: Test All Scenarios
```bash
python send_test_data.py --api-key <YOUR_KEY> --patient-id P001 --all-tests
```
