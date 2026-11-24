# Remote Patient Health Monitoring System (IoT Telehealth Platform)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?logo=vite&logoColor=white)](https://vitejs.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Tests](https://img.shields.io/badge/Pytest-45%20Passed-success)](https://docs.pytest.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An end-to-end, dual-database IoT Remote Patient Health Monitoring System specifically engineered for continuous physiological telemetry in rural and off-grid health clinics via embedded microcontrollers and cellular (2G/GPRS) connectivity.

Built as an academic engineering research prototype with a decoupled **FastAPI** backend, **React 18 + TypeScript + Vite** clinical dashboard, **Plotly.js** hardware-precision ECG waveform reconstructor, **Dual SQLite / PostgreSQL async engine**, and remote **Doctor-to-Patient Prescription Dispatch** to a 20x4 character LCD screen with physical hardware confirmation.

---

> [!NOTE]
> **University Engineering Research Prototype**: This system is designed for academic demonstration, engineering evaluation, and low-cost rural telehealth research. It is not an FDA-cleared, CE-marked, or certified medical device and must not be used for emergency triage, life-critical decisions, or definitive clinical diagnosis.

---

## System Architecture

```mermaid
flowchart TD
    subgraph Edge ["Rural Patient Node (ESP32 IoT)"]
        Sensors["AD8232 (ECG) + MAX30102 (HR/SpO2) + DS18B20 (Temp)"]
        ESP32["ESP32 Microcontroller (240MHz, 250Hz ADC)"]
        LCD["20x4 I2C Character LCD (Patient Directives)"]
        Btn["Physical Acknowledge Button"]
        SIM800L["SIM800L 2G/GPRS Quad-Band GSM Modem"]

        Sensors --> ESP32
        Btn --> ESP32
        ESP32 --> LCD
        ESP32 <-->|UART AT Commands| SIM800L
    end

    subgraph Network ["Cellular / Tunnel Infrastructure"]
        GPRS["2G/GPRS Cellular Network / ngrok HTTPS Tunnel"]
        SIM800L <-->|HTTP POST JSON Batches| GPRS
    end

    subgraph Server ["FastAPI ASGI Platform"]
        Gateway["Uvicorn ASGI Gateway"]
        AuthEngine["Device Auth (SHA256 Prefix + Bcrypt)"]
        IngestService["Batch Ingest & Idempotency Engine"]
        DSP["0.5–40 Hz 4th-order SOS Butterworth Bandpass"]
        RxService["Doctor Prescription Queue & LCD Pager"]

        GPRS --> Gateway
        Gateway --> AuthEngine --> IngestService
        IngestService --> DSP
    end

    subgraph Database ["Persistence Layer (Dual Async Engine)"]
        DB[("PostgreSQL 16 (Neon.tech) / Local SQLite (aiosqlite)")]
        IngestService <--> DB
        RxService <--> DB
    end

    subgraph UI ["Doctor Clinical Dashboard (React + Vite)"]
        Portal["Clinical Analytics & Live Telemetry Stream"]
        ECGAnalyzer["250Hz ECG Strip Viewer (Paper Grid vs Oscilloscope)"]
        RxConsole["Prescription Dispatcher & 20x4 LCD Simulator"]

        Gateway <-->|REST API + JWT Bearer| UI
        UI --- Portal
        UI --- ECGAnalyzer
        UI --- RxConsole
    end
```

---

## Core Innovations & Features

### 1. Dual-Database Cloud Compatibility (SQLite + PostgreSQL)
- **Zero-Setup Local Mode**: Uses `aiosqlite` with SQLite (`health_monitor.db`) for immediate offline demonstration.
- **Free Cloud Production Mode**: Native `asyncpg` driver support with automated connection pooling for **Neon.tech** or **Render** serverless PostgreSQL 16.
- **Automatic Connection Normalization**: Cloud `postgres://` or `postgresql://` environment variables are automatically routed to `postgresql+asyncpg://`.

### 2. Biomedical ECG Acquisition & Signal Processing (AD8232)
- **High-Precision Sampling**: Preserves raw 12-bit ADC counts sampled strictly at 250 Hz (4 ms intervals).
- **Physical Lead-Off Detection**: Monitors AD8232 LO+ and LO- leads; samples during lead-off are flagged as disconnected gaps instead of fabricating false sinusoidal waves.
- **Digital Filter**: 4th-order Second-Order Sections (SOS) Butterworth bandpass (0.5 Hz – 40.0 Hz) using zero-phase forward-backward filtering (`scipy.signal.sosfiltfilt`).
- **Interactive Visualization**: Toggle between **Clinical Millimeter Paper Grid** (25 mm/s, 10 mm/mV) and **Midnight Dark Oscilloscope** modes. One-click RFC 4180 CSV export and high-resolution PNG strip charts.

### 3. Remote Doctor-to-Patient Prescriptions & 20x4 LCD Protocol
- Physicians dispatch structured clinical advice (assessment, medication, dosage, frequency, instructions, follow-up).
- The ESP32 polls for directives during routine telemetry uploads and renders text across 4 pages on a 20x4 character LCD screen.
- A physical push button on the patient's device registers hardware acknowledgement, transmitted back to the server with a synchronized audit timestamp.

### 4. Duplicate-Safe Ingestion & Idempotency
- Handles unreliable 2G/GPRS signal drops with zero data loss or duplicate records.
- Unique constraints enforce idempotency across `(device_id, batch_id)` and `(session_id, sequence_number)`.
- Concurrent duplicate uploads are safely deduplicated with `HTTP 200` duplicate-ignored responses.

### 5. Dual-Tiered Security & O(1) Prefix Device Authentication
- **Physicians**: Scoped OAuth2 JWT Bearer tokens with Bcrypt password hashing.
- **Edge Devices**: Hardware API keys in format `dev_<prefix>_<secret>`. Fast $O(1)$ database prefix indexing followed by timing-safe Bcrypt hash verification.
- **Audit Log**: Immutable append-only `audit_events` table tracking all logins, key rotations, and suspicious telemetry attempts.

---

## Technology Stack

| Domain | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3.12+, FastAPI, Uvicorn | Asynchronous, high-throughput REST API |
| **Persistence** | SQLAlchemy 2.0, aiosqlite, asyncpg | Dual SQLite & PostgreSQL async ORM |
| **Signal Processing** | NumPy, SciPy, Matplotlib | Numerical filtering (SOS) and PNG strip rendering |
| **Security & Auth** | passlib (Bcrypt), python-jose | Cryptographic hashing and JWT token issuance |
| **Frontend Framework** | React 18, TypeScript, Vite | High-performance clinical Single Page App |
| **Styling & Design System** | Tailwind CSS, Lucide React | Clinical Light / Midnight Dark adaptive themes |
| **Charting Engine** | Plotly.js, react-plotly.js | Medical millimeter paper grid waveform analyzer |
| **Data Fetching** | TanStack React Query v5 | Real-time polling, query caching, background refetch |
| **Embedded Firmware** | C++, Arduino IDE, FreeRTOS | ESP32 hardware acquisition, SIM800L AT driver |

---

## Quick Start Guide

### Prerequisites
- **Python 3.11+ or 3.12+**
- **Node.js 18+ or 20+**
- (Optional) Git & Docker

---

### Method A: One-Click Windows Launchers (Recommended)
Navigate to the `hardware\` directory and double-click:
```text
hardware\START_ALL.bat
```
This launcher starts the FastAPI backend on port 8000, Vite frontend on port 5173, and launches the dashboard in your default browser.

Separate individual launchers are also available in `hardware\`:
- `START_BACKEND.bat` — Starts FastAPI server with virtual environment detection.
- `START_FRONTEND.bat` — Starts Vite dev server.
- `START_NGROK.bat` — Opens an ngrok tunnel to port 8000 for Wokwi or real ESP32 testing.

---

### Method B: Manual Command Line Setup

#### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*API live at `http://localhost:8000` (Interactive Swagger docs: `http://localhost:8000/docs`).*

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
*Dashboard live at `http://localhost:5173`.*

**Default Administrator Credentials**:
- **Username**: `admin`
- **Password**: `admin123`

---

### Method C: Docker Compose Setup
```bash
docker-compose up --build
```

---

## Running the Automated Test Suite

The test suite contains 45 automated tests validating authentication, device management, session ownership, duplicate ingestion, temperature disconnect sanitization, and SOS signal processing:

```bash
cd backend
python -m pytest -v
```

**Results**:
```text
============================== 45 passed in 30.29s ==============================
```

Frontend typecheck and production build:
```bash
cd frontend
npm run test
npm run build
```

---

## Free Cloud Deployment

For detailed instructions on deploying the backend to **Render (Free)**, the database to **Neon.tech (Free Serverless Postgres)**, and the frontend to **Vercel (Free)**, see:

📖 [**DEPLOYMENT.md**](DEPLOYMENT.md)

System architecture diagrams, data flow charts, and LCD paged display specifications:

📖 [**ARCHITECTURE.md**](ARCHITECTURE.md)

Comprehensive project audit report:

📖 [**PROJECT_AUDIT.md**](PROJECT_AUDIT.md)

---

## Repository Structure

```text
Remote_Health_Monitoring_Server/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/v1/           # API Routers (auth, devices, ecg, ingest, patients, prescriptions)
│   │   ├── core/             # Configuration, logging, security
│   │   ├── database/         # Session management (SQLite / PostgreSQL dual engine)
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic validation schemas
│   │   └── services/         # Business logic & DSP signal filters
│   ├── tests/                # 45 Pytest regression tests
│   ├── Dockerfile            # Production container image
│   └── requirements.txt      # Python dependencies (fastapi, asyncpg, scipy, etc.)
├── frontend/                 # React 18 + TypeScript + Vite Dashboard
│   ├── src/
│   │   ├── components/       # Clinical UI components (ECGViewer, etc.)
│   │   ├── hooks/            # useTheme (Clinical Light / Midnight Dark)
│   │   ├── layouts/          # Responsive AppLayout with telemetry indicator
│   │   ├── pages/            # Dashboard, Patients, ECGViewer, Prescriptions, Devices
│   │   └── services/         # Axios API client
│   └── package.json
├── firmware/                 # ESP32 + SIM800L Arduino source code
├── hardware/                 # Windows .bat startup scripts
├── simulator/                # High-fidelity synthetic ECG & vitals data generator
├── ARCHITECTURE.md           # System design & sequence flowcharts
├── DEPLOYMENT.md             # Free cloud deployment guide (Render + Neon + Vercel)
├── PROJECT_AUDIT.md          # Complete pre-deployment audit report
├── docker-compose.yml        # Multi-container orchestration
└── render.yaml               # Render.com infrastructure blueprint
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
