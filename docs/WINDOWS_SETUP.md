# Windows Setup & Operating Guide
## Remote Patient Health Monitoring System

This document provides step-by-step instructions for running the complete Remote Patient Health Monitoring platform locally on a Windows computer using PowerShell.

---

## 1. System Requirements

- **Operating System:** Windows 10 or Windows 11 (64-bit)
- **Python:** Python 3.11 or Python 3.12 (Check with `python --version`)
- **Node.js:** Node.js 18 or newer with npm (Check with `node -v` and `npm -v`)
- **Terminal:** Windows PowerShell or PowerShell 7

---

## 2. Directory Structure

```
D:\Remote_Health_Monitoring_Server\
├── backend\               # FastAPI REST API, SQLAlchemy models, security
│   ├── app\
│   ├── tests\             # 35 automated pytest unit and integration tests
│   ├── requirements.txt
│   └── health_monitor.db  # SQLite database (auto-created on startup)
├── frontend\              # React 18, TypeScript, Vite, Tailwind, Plotly.js
│   ├── src\
│   ├── package.json
│   └── vite.config.ts
├── simulator\             # IoT hardware telemetry simulation scripts
│   ├── send_test_data.py  # High-fidelity ESP32/SIM800L simulator
│   └── test_live_api.py   # Automated acceptance test script
├── docs\                  # Technical architecture and integration docs
└── README.md
```

---

## 3. Backend Setup & Startup

### Step 3.1: Open PowerShell and navigate to backend
```powershell
cd D:\Remote_Health_Monitoring_Server\backend
```

### Step 3.2: Create and activate a Python virtual environment (Optional if already installed)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3.3: Install backend dependencies
```powershell
pip install -r requirements.txt
```

### Step 3.4: Configure Environment Variables
Copy `.env.example` to `.env` in the `backend/` directory:
```powershell
Copy-Item .env.example .env
```

### Step 3.5: Run Backend Automated Test Suite
To verify that all 35 tests pass:
```powershell
pytest -v
```
*(All 35 tests should pass with 0 errors.)*

### Step 3.6: Start the Backend Server
```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- The backend API will be available at: `http://127.0.0.1:8000`
- Interactive OpenAPI Swagger docs: `http://127.0.0.1:8000/docs`
- Health check probe: `http://127.0.0.1:8000/api/v1/health`

---

## 4. Frontend Setup & Startup

Open a **second PowerShell window**:

### Step 4.1: Navigate to frontend directory
```powershell
cd D:\Remote_Health_Monitoring_Server\frontend
```

### Step 4.2: Install npm dependencies
```powershell
npm install
```

### Step 4.3: Start the Vite Development Server
```powershell
npm run dev
```
- The web application will be accessible at: `http://127.0.0.1:5173`
- The dev server includes hot module replacement (HMR) and automatically proxies `/api/v1` calls to `http://127.0.0.1:8000`.

### Step 4.4: Verify Production Build
To verify the TypeScript types and build a standalone production bundle:
```powershell
npm run build
```

---

## 5. Doctor Portal Sign-In

1. Open your browser and go to `http://127.0.0.1:5173/login`.
2. Enter the initial administrator credentials:
   - **Username:** `admin`
   - **Password:** `admin123`
3. Click **Sign In**.
4. You will be redirected to the main medical dashboard showing real-time statistics, active devices, patient rosters, and system audit events.

---

## 6. Running the Hardware Telemetry Simulator

Open a **third PowerShell window** to simulate patient hardware (ESP32 + SIM800L):

### Step 6.1: Navigate to project root
```powershell
cd D:\Remote_Health_Monitoring_Server
```

### Step 6.2: Obtain an API Key for your Device
You can view or rotate device API keys in the dashboard under **Device Registry** (`http://127.0.0.1:5173/devices`), or run:
```powershell
python -c "
import urllib.request, urllib.parse, json
data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/login', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
token = json.loads(urllib.request.urlopen(req).read().decode())['access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/devices/ESP32-001/rotate-key', data=b'{}', headers=headers)
res = json.loads(urllib.request.urlopen(req).read().decode())
print('API Key:', res.get('plain_api_key'))
"
```

### Step 6.3: Run the Full Test Scenario Suite
Replace `<YOUR_API_KEY>` with the key obtained above:
```powershell
python simulator/send_test_data.py `
  --server-url http://127.0.0.1:8000 `
  --device-id ESP32-001 `
  --patient-id P001 `
  --api-key <YOUR_API_KEY> `
  --all-tests
```

### Step 6.4: Stream a Continuous Multi-Batch ECG Session
To stream 5 consecutive batches (50 seconds continuous recording at 250 Hz) under a single session:
```powershell
python simulator/send_test_data.py `
  --server-url http://127.0.0.1:8000 `
  --device-id ESP32-001 `
  --patient-id P001 `
  --api-key <YOUR_API_KEY> `
  --stream-session `
  --repeat 5 `
  --interval 1.0
```

### Step 6.5: Verify Visualizations in the Browser
1. Navigate to **ECG Recordings** (`http://127.0.0.1:5173/recordings`).
2. Click on the newly streamed session to open the **ECG Waveform Viewer** (`/ecg/<session_id>`).
3. Toggle between **Raw ADC counts** and **Filtered (0.5–40 Hz)** views.
4. Zoom and pan on the interactive Plotly strip chart.
5. Click **Export CSV** or **Export PNG Plot** to download diagnostic artifacts.

---

## 7. Troubleshooting & FAQs

- **Port 8000 is already in use:**
  Run `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force` in PowerShell, then restart uvicorn.
- **Port 5173 is already in use:**
  Run `Get-Process -Id (Get-NetTCPConnection -LocalPort 5173).OwningProcess | Stop-Process -Force`, then restart `npm run dev`.
- **Database Schema Updates:**
  The server automatically migrates and verifies SQLite tables on startup. If you ever need to reset to a pristine state, simply delete `backend/health_monitor.db` and restart `uvicorn`. Initial seed data (default admin user and clinic patient) will be automatically provisioned.
