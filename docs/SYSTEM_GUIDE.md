# System Architecture & User Guide — Remote Patient Health Monitoring System

This document provides a comprehensive architectural and operational walkthrough of the Remote Patient Health Monitoring System.

---

## 1. System Purpose & Context

In rural and remote regions, access to specialized cardiological and primary healthcare is severely restricted by geographical distances, infrastructure deficits, and economic barriers. Patients in these areas frequently cannot travel to regional hospitals for periodic checkups and do not own smartphones or reliable home broadband.

This platform bridges that gap by using low-cost embedded hardware running on pervasive 2G cellular infrastructure to transmit vital signs and single-lead ECG data from village health clinics or patient homes directly to a central monitoring server. Doctors securely access this telemetry through an interactive, responsive medical web dashboard.

---

## 2. End-to-End Operational Workflow

```
[ Rural Patient ]
       │
       ▼
[ AD8232 ECG + MAX30102 + DS18B20 ]
       │ (Biopotentials + Optical + Thermal)
       ▼
[ ESP32 Microcontroller Node ]
       │
       ▼ (Hayes AT Commands via UART)
[ SIM800L 2G/GPRS Modem ]
       │
       ▼ (2G Cellular Airwaves)
[ Mobile Network Operator Base Station (BTS) ]
       │
       ▼ (GPRS Packet Switched Data)
[ Internet / Clinic Gateway ]
       │
       ▼ (HTTP POST /api/v1/ingest with X-Device-API-Key)
[ FastAPI Backend Server ]
       │
       ├─► [ Authenticate Device & Validate Batch ]
       ├─► [ Check Duplicates / Prevent Double-Store ]
       ├─► [ Store Raw Numerical Samples in Database ]
       └─► [ Log Audit Trail ]
       │
       ▼
[ SQLite / PostgreSQL Database ]
       ▲
       │ (REST API / JWT Session)
[ React + TypeScript Doctor Dashboard ]
       ▲
       │ (Secure Browser Session)
[ Physician / Medical Officer ]
```

---

## 3. Web Application User Guide

### 3.1 Authentication
1. Navigate to `http://localhost:5173/login`.
2. Enter doctor credentials (default: `admin` / `admin123`).
3. On successful authentication, the server generates a cryptographically signed JWT access token stored in client session storage.

### 3.2 Main Dashboard
- **Total Registered Patients**: Live count of active patients in the registry.
- **Registered Devices & Online Status**: Count of deployed devices and how many have transmitted telemetry within the last 10 minutes.
- **24-Hour Telemetry Volume**: Count of incoming uploads and ECG recordings.
- **Audit Feed**: Chronological log of device transmissions, login attempts, and administrative actions.
- **Ingestion Errors**: Notification banner showing any rejected or unauthenticated transmissions.

### 3.3 Patient Management
- **Add Patient**: Register new patient with unique ID (e.g. `P001`), full name, age, and clinical notes.
- **Search & Filter**: Search instantaneously by name or patient identifier; filter active vs. archived patients.
- **Patient Detail View**: Dedicated view showing assigned hardware, latest recorded vitals (Heart Rate, $SpO_2$, Body Temperature), historical ECG recordings, and doctor consultation notes.

### 3.4 Interactive ECG Viewer
- Access by clicking any ECG recording row or navigating to `/ecg/{recording_id}`.
- **Plotly.js Visualizer**: Full hardware-precision rendering of cardiac waveforms.
- **Time Axis**: Dynamically calculated from sampling frequency ($t = i / f_s$).
- **Unit Precision**: Raw biopotential is strictly labeled as **ADC Counts** to prevent misleading pseudo-voltage claims without verified hardware calibration.
- **Zoom & Pan**: Smooth scroll-wheel zoom and click-and-drag pan across multi-second recordings.
- **Export Capabilities**:
  - **Download CSV**: Full RFC 4180 export with elapsed time in seconds and sample counts.
  - **Download PNG**: Rendered publication-quality ECG strip diagram with medical dark-navy styling.

### 3.5 Device Management
- **Register Device**: Provision new device identifier (e.g. `ESP32-001`).
- **One-Time API Key**: Displays the generated cryptographically random 256-bit API key. Store this key immediately for flashing into firmware or configuring the simulator.
- **Live Device Status**:
  - **Online** (green): Upload received within last 10 minutes.
  - **Stale** (yellow): Upload received within last 60 minutes.
  - **Offline** (red): No upload for $>60$ minutes or never connected.
