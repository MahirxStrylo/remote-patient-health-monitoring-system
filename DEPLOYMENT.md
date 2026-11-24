# Cloud Deployment Guide — Remote Patient Health Monitoring System
## 100% Free Tier Production Deployment Guide

This guide describes how to deploy the entire Remote Patient Health Monitoring System to production on **100% free cloud services** without credit card commitments, disk wiping issues, or data loss.

---

## Architecture Overview

```
+-------------------------------------------------------------+
|                      IoT EDGE HARDWARE                      |
|  AD8232 (ECG) + MAX30102 (HR/SpO2) + DS18B20 (Temperature)   |
|                              |                              |
|                    ESP32 Microcontroller                    |
|                              |                              |
|                    SIM800L 2G/GPRS Modem                    |
+------------------------------+------------------------------+
                               | Cellular HTTP POST
                               v
+-------------------------------------------------------------+
|                    FASTAPI CLOUD BACKEND                    |
|                 Hosted on: Render.com (Free)                |
|           • Device Bcrypt Authentication (X-Device-API-Key) |
|           • Telemetry Ingest & Duplicate Detection          |
|           • SOS 0.5–40 Hz Zero-Phase ECG Filter             |
|           • JWT Doctor Authentication & Directives          |
+------------------------------+------------------------------+
              |                               |
       SQLAlchemy Async                 REST API / JSON
              v                               v
+-----------------------------+ +-----------------------------+
|     PERSISTENT DATABASE     | |    REACT DOCTOR PORTAL      |
|  Hosted on: Neon.tech (Free)| |   Hosted on: Vercel / Render|
|  • Serverless PostgreSQL 16 | |   • Clinical High-Density UI|
|  • Permanent Cloud Storage  | |   • Interactive Plotly ECG  |
|  • Built-in Connection Pool | |   • 20x4 LCD Simulator      |
+-----------------------------+ +-----------------------------+
```

---

## Strategy: Why Neon PostgreSQL + Render + Vercel?

| Platform | Role | Why Chosen | Cost |
| :--- | :--- | :--- | :--- |
| **Neon.tech** | Persistent Database | Render's free tier has an ephemeral disk (SQLite databases are wiped on restart/sleep). Neon provides **0.5 GB free serverless PostgreSQL** that never wipes and stays permanent. | **$0 / month** |
| **Render.com** | FastAPI Backend | Direct GitHub integration, native Python 3.12 ASGI runtime, automatic HTTPS, free Web Service tier. | **$0 / month** |
| **Vercel** / **Render** | React Frontend | Ultra-fast global Edge CDN, free automatic SSL, seamless React SPA rewrite support. | **$0 / month** |

---

## Step 1: Create Free Persistent PostgreSQL on Neon

1. Sign up at [https://neon.tech](https://neon.tech) (using GitHub or Google login).
2. Click **Create Project**:
   - **Project Name**: `remote-health-db`
   - **Postgres Version**: 16 (default)
   - **Region**: Choose the closest region to you (e.g., `us-east-2` or `eu-central-1`).
3. Once created, copy the connection string displayed on the dashboard.
   - Example format:
     ```text
     postgresql://neondb_owner:AbCdEf123456@ep-cool-butterfly-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```
4. **No driver change needed!** The FastAPI server automatically detects `postgres://` or `postgresql://` and routes it through `postgresql+asyncpg://` with connection pooling enabled.

---

## Step 2: Deploy Backend to Render

1. Sign up at [https://render.com](https://render.com) using your GitHub account.
2. Ensure you have pushed this repository to your GitHub account (`remote-patient-health-monitoring-system`).
3. In the Render Dashboard, click **New +** → **Web Service**.
4. Connect your GitHub repository:
   - **Name**: `remote-health-backend`
   - **Region**: Same region as your Neon database (e.g., `Oregon (US West)` or `Frankfurt (EU)`).
   - **Root Directory**: `backend`
   - **Runtime**: `Python`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Plan**: `Free`
5. Under **Environment Variables**, add the following keys:

| Key | Example Value | Description |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.12.10` | Python runtime version |
| `DATABASE_URL` | `postgresql://...` | Connection string copied from Neon.tech |
| `SECRET_KEY` | `your-secure-random-token-here` | Secret key for signing JWT tokens |
| `ADMIN_USERNAME` | `admin` | Initial doctor login username |
| `ADMIN_PASSWORD` | `admin123` | Initial doctor login password |
| `CORS_ORIGINS` | `["*"]` | Allows connections from your Vercel frontend |
| `STALE_READING_THRESHOLD_MINUTES` | `15` | Flag telemetry as stale after 15 min |
| `MAX_ECG_SAMPLES_PER_BATCH` | `10000` | Safety limit on ingest batches |

6. Click **Deploy Web Service**.
7. Once deployed, Render will provide your public backend URL:
   ```text
   https://remote-health-backend.onrender.com
   ```
8. Verify deployment by visiting `https://remote-health-backend.onrender.com/docs` in your browser. The Swagger interactive API documentation should load immediately.

---

## Step 3: Deploy Frontend Dashboard

### Option A: Deploy on Vercel (Recommended)

1. Sign up at [https://vercel.com](https://vercel.com) using GitHub.
2. Click **Add New…** → **Project**, and select your repository.
3. Configure the project:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click edit and select `frontend`.
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Under **Environment Variables**:
   - `VITE_API_BASE_URL`: Set to your Render backend API base:
     ```text
     https://remote-health-backend.onrender.com/api/v1
     ```
5. Click **Deploy**. Vercel will build and assign you a global HTTPS domain:
   ```text
   https://remote-health-frontend.vercel.app
   ```

### Option B: Deploy on Render Static Sites

You can also use the included `render.yaml` blueprint. In Render:
1. Click **New +** → **Blueprint**.
2. Select your repository. Render will automatically configure both the backend and frontend using `render.yaml`.
3. Provide the `DATABASE_URL` and `VITE_API_BASE_URL` values when prompted.

---

## Step 4: Connecting the Physical ESP32 + SIM800L Device

Now that your server is live on cloud HTTPS, update the ESP32 firmware:

1. Open `firmware/esp32_health_monitor/esp32_health_monitor.ino` in Arduino IDE or VS Code PlatformIO.
2. Update the cloud server endpoint and API key:
   ```cpp
   // Set your live cloud server host
   const char* SERVER_URL = "https://remote-health-backend.onrender.com/api/v1/ingest";

   // Device Identifier & API Key (created in Doctor Portal -> Devices -> Register Device)
   const char* DEVICE_ID = "ESP32-001";
   const char* DEVICE_API_KEY = "dev_YOUR_GENERATED_API_KEY_HERE";
   ```
3. Set your local cellular operator APN:
   ```cpp
   // Examples:
   // Grameenphone (BD): "gpinternet"
   // Banglalink (BD): "blweb"
   // Robi / Airtel (BD): "internet"
   // Jio (India): "jionet"
   // Airtel (India): "airtelgprs.com"
   const char* APN = "gpinternet";
   ```
4. Flash the code to the ESP32.
5. Open Serial Monitor at 115200 baud. The ESP32 will:
   - Synchronize with the SIM800L module via AT commands.
   - Attach to GPRS.
   - Transmit JSON telemetry batches.
   - Read and display remote doctor prescriptions on the 20x4 LCD screen.

---

## Step 5: Cold Start Optimization (Free Tier Trick)

Render's free tier spins down the web service after 15 minutes of inactivity. When a new request arrives, it takes ~40 seconds to wake up (cold start).

To keep your university demo instant and warm:
1. Sign up for free at [https://cron-job.org](https://cron-job.org) or [https://uptimerobot.com](https://uptimerobot.com).
2. Create a monitor to ping:
   ```text
   https://remote-health-backend.onrender.com/health
   ```
   every **10 minutes**.
3. This keeps the backend warm 24/7 without incurring any costs.

---

## Local Development (No Cloud Needed)

If presenting in a classroom or laboratory without internet, run everything locally:

### Option 1: One-Click Windows Launchers
Double-click:
```text
hardware\START_ALL.bat
```
This automatically starts the FastAPI server, the Vite React frontend, and opens the dashboard in your default browser.

### Option 2: Docker Compose
```bash
docker-compose up --build
```
Access the dashboard at `http://localhost:5173` and backend at `http://localhost:8000`.
