# University Engineering Project Guide: Remote Patient Health Monitoring System

**Project Type:** Undergraduate Engineering Project / Capstone Demonstration  
**Hardware Platform:** ESP32 DevKit V1 + AD8232 + MAX30102 + DS18B20 + SIM800L (2G GSM/GPRS)  
**Software Stack:** Python 3.11+ / FastAPI / SQLite / React / TypeScript / Tailwind CSS / Plotly.js  

---

## 1. System Overview & Complete End-to-End Data Flow

The project is designed to bridge the healthcare divide for rural communities where hospital access, Wi-Fi, and 4G coverage are limited, but basic 2G cellular coverage exists.

```
+-----------------------------------------------------------------------------------------+
|                                    PATIENT SIDE (IoT NODE)                              |
|                                                                                         |
|  [ AD8232 ECG Sensor ]  ──(Analog ADC)──┐                                               |
|  [ MAX30102 HR & SpO2]  ──(I2C Bus)─────┼──> [ ESP32 DevKit V1 ]                        |
|  [ DS18B20 Temperature] ──(1-Wire)──────┘         │                                     |
|                                                   │ (Hardware UART2)                    |
|                                                   ▼                                     |
|                                          [ SIM800L 2G GPRS Modem ]                      |
+---------------------------------------------------|-------------------------------------+
                                                    │
                                                    │ 2G Cellular Radio (GPRS)
                                                    ▼
+-----------------------------------------------------------------------------------------+
|                                 TELEMETRY INGESTION (SERVER)                            |
|                                                                                         |
|       [ Cellular Carrier GPRS Network ]  ──>  [ FastAPI REST Server (:8000) ]           |
|                                                          │                              |
|                                                          ▼                              |
|                                                [ SQLite Database ]                      |
|                                          (health_monitor.db - Vitals & ECG)             |
+----------------------------------------------------------|------------------------------+
                                                           │
                                                           │ JSON REST API
                                                           ▼
+-----------------------------------------------------------------------------------------+
|                                  DOCTOR DASHBOARD (WEB)                                 |
|                                                                                         |
|                 [ React + TypeScript + Plotly.js Dashboard (:5173) ]                    |
|                 - Real-time Patient Vital Signs (HR, SpO2, Temp)                        |
|                 - Interactive Clinical ECG Waveform with Physical Gap Display           |
|                 - Historical Trends and PDF/CSV Export                                  |
+-----------------------------------------------------------------------------------------+
```

---

## 2. 2-Minute Quick Start (Live Demonstration for Evaluators)

To demonstrate the full working pipeline on your computer in under 2 minutes:

### Step 1: Start the Backend Server
Open a terminal in the project directory:
```powershell
# Double-click start_server.bat OR run:
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*The FastAPI backend will start on `http://localhost:8000`. Documentation available at `http://localhost:8000/docs`.*

### Step 2: Start the Doctor Dashboard
Open a second terminal:
```powershell
# Double-click start_dashboard.bat OR run:
cd frontend
npm run dev
```
*The React Dashboard will be available at `http://localhost:5173`.*

### Step 3: Run the Live Telemetry Demo
Open a third terminal:
```powershell
python run_demo.py
```
*This streams 5 realistic sequential ECG telemetry batches matching the exact JSON format sent by the ESP32.*

### Step 4: View the Live Dashboard
1. Open your browser to **`http://localhost:5173`**.
2. Log in with evaluator credentials:
   - **Username:** `admin`
   - **Password:** `admin123`
3. View the patient dashboard:
   - Patient **P001** displays the latest heart rate, SpO₂, and body temperature.
   - Click **ECG Recordings** $\to$ select the active session to see the interactive P-Q-R-S-T ECG waveform with zoom, pan, and raw/filtered views.

---

## 3. Hardware Schematic & Pinout

```
           +---------------------------------------------+
           |               ESP32 DevKit V1               |
           |                                             |
           |  3V3 ---------+                             |
           |  GND ---------|---------+                   |
           |               |         |                   |
           |  GPIO 34 <----+ (AOUT)  |                   |
           |  GPIO 33 <----+ (LO+)   |  AD8232 ECG       |
           |  GPIO 32 <----+ (LO-)   |                   |
           |  3V3  --------> (3V3)   |                   |
           |  GND  --------> (GND)---+                   |
           |                                             |
           |  GPIO 21 (SDA)<>(SDA)                       |
           |  GPIO 22 (SCL)->(SCL)   MAX30102 Oximeter   |
           |  3V3  --------> (VIN)                       |
           |  GND  --------> (GND)                       |
           |                                             |
           |  GPIO 4 (1-W) <>(DATA)  DS18B20 Temp        |
           |  [4.7k pullup to 3V3]                       |
           |  3V3  --------> (VDD)                       |
           |  GND  --------> (GND)                       |
           |                                             |
           |  GPIO 16 (RX2)<- (TXD)  SIM800L Modem       |
           |  GPIO 17 (TX2)-> (RXD)  [Voltage Divider]   |
           |  GND  --------> (GND)                       |
           +---------------------------------------------+
                                     |
               +---------------------+
               |
     +---------+----------+
     |   External 4.0V    | ====> Powers SIM800L VCC
     |   Li-Ion / Buck    |       (Needs up to 2.0A bursts)
     +--------------------+
```

### Critical Electrical Engineering Requirements:
1. **SIM800L Power Rail:** SIM800L draws up to **2.0A peak current** during RF transmission bursts. Powering it directly from the ESP32 3.3V or 5V rail causes brownout resets (`UNDER-VOLTAGE WARN`). Use an external 1S Li-Ion cell (3.7V–4.2V) or buck converter with a **1000µF capacitor** across SIM800L VCC and GND.
2. **UART Logic Voltage:** The SIM800L RX pin is 2.8V–3.0V logic. ESP32 outputs 3.3V. Place a simple resistor divider ($1\text{ k}\Omega$ and $2\text{ k}\Omega$) between ESP32 TX2 (GPIO 17) and SIM800L RXD to protect the module.

---

## 4. SIM800L AT-Command Flow & GPRS Protocol

When the ESP32 transmits telemetry over 2G cellular, it executes this sequence over HardwareSerial:

```text
1. Modem Health & SIM Check:
   >> AT
   << OK
   >> ATE0                    (Disable local echo)
   << OK
   >> AT+CPIN?                (Verify SIM card is inserted and unlocked)
   << +CPIN: READY
   >> AT+CSQ                  (Check signal strength, 15-31 is good)
   << +CSQ: 18,0
   >> AT+CREG?                (Check GSM network registration)
   << +CREG: 0,1              (1 = Registered to home cellular carrier)

2. GPRS Bearer Activation (Bangladesh APN):
   >> AT+CGATT=1              (Attach to GPRS service)
   << OK
   >> AT+SAPBR=3,1,"CONTYPE","GPRS"
   << OK
   >> AT+SAPBR=3,1,"APN","gpinternet"   (For Grameenphone, or "blweb" for Banglalink)
   << OK
   >> AT+SAPBR=1,1            (Open GPRS context)
   << OK
   >> AT+SAPBR=2,1            (Query assigned cellular IP)
   << +SAPBR: 1,1,"10.142.56.88"

3. HTTP POST Ingestion:
   >> AT+HTTPINIT
   << OK
   >> AT+HTTPPARA="CID",1
   << OK
   >> AT+HTTPPARA="URL","http://<YOUR_SERVER_IP>:8000/api/v1/ingest"
   << OK
   >> AT+HTTPPARA="CONTENT","application/json"
   << OK
   >> AT+HTTPPARA="USERDATA","X-Device-API-Key: rhm_80eedcd9eedb1f43_EnZ6ej9kDYl23pm0qLtnBqvpcdZgphdovZ3hSHHYgVc"
   << OK
   >> AT+HTTPDATA=1845,15000  (Specify payload length in bytes and 15s timeout)
   << DOWNLOAD
   >> [Transmit JSON body]
   << OK
   >> AT+HTTPACTION=1         (Execute HTTP POST)
   << OK
   << +HTTPACTION: 1,200,128  (HTTP 200 OK received from server, 128 response bytes)
   >> AT+HTTPREAD
   << {"batch_id":"...","status":"accepted",...}
   << OK
   >> AT+HTTPTERM             (Close HTTP session)
   << OK
```

---

## 5. ESP32 Arduino Firmware Features

The included Arduino firmware (`firmware/esp32_health_monitor/esp32_health_monitor.ino`) is ready to flash using the Arduino IDE:

1. **Dual Operating Mode:**
   - `#define SIMULATE_SENSORS true`: Generates clean P-Q-R-S-T ECG, heart rate, SpO₂, and temperature mathematically in memory. Evaluators can see live telemetry without needing breadboard sensor wiring.
   - `#define SIMULATE_SENSORS false`: Reads live ADC counts from AD8232 on GPIO 34, I2C from MAX30102, and 1-Wire from DS18B20.
2. **Wi-Fi Fallback Option:**
   - `#define USE_WIFI_FALLBACK false`: Standard SIM800L 2G GPRS mode.
   - `#define USE_WIFI_FALLBACK true`: Transmits the exact same JSON telemetry over Wi-Fi if 2G cellular reception is shielded inside concrete university exam halls.
3. **Optimized Batch Sizing for 2G GPRS:**
   - Samples at **250 Hz** (standard clinical biopotential rate).
   - Groups samples into **250-sample batches** (1.0 second per packet, ~1.5 KB JSON), ensuring fast and reliable GPRS delivery over rural cellular links.

---

## 6. Questions & Answers for Viva / University Project Defense

### Q1: Why did you choose SIM800L 2G instead of 4G (LTE) or Wi-Fi?
> **Answer:**  
> 1. **Rural Coverage:** In rural and remote areas of Bangladesh (such as haor/char riverine regions), 4G and Wi-Fi infrastructure is often absent or unreliable, but standard 2G GSM/GPRS towers provide near-universal voice and telemetry coverage.  
> 2. **Cost-Effectiveness:** A SIM800L module costs approximately \$3–\$5 compared to \$25–\$35 for an LTE Cat-1/Cat-4 modem (e.g. SIM7600), making rural telemedicine units affordable for resource-constrained community clinics.  
> 3. **Payload Efficiency:** Health monitoring telemetry (numerical ECG batches and vitals) produces modest data throughput (~2–4 kbps), which operates comfortably within 2G GPRS speeds (20–40 kbps).

### Q2: Why send ECG samples in batches instead of one sample at a time?
> **Answer:**  
> Transmitting individual ADC samples at 250 Hz over cellular HTTP would require 250 HTTP connections per second, causing extreme protocol overhead and network congestion. Grouping samples into 1-second or 2-second batches (~250–500 samples) allows the ESP32 to send a single compact JSON packet, minimizing cellular connection handshakes and battery consumption.

### Q3: How does the system handle cellular dropouts and packet loss?
> **Answer:**  
> Every batch has a sequential `sequence_number` (1, 2, 3...). If a packet is lost due to cellular fading:  
> 1. The server detects the gap (e.g. sequences 1 and 3 received, sequence 2 missing).  
> 2. The timeline reconstruction inserts `None` sentinels representing the exact physical elapsed duration (e.g. 1.0 second) of the missing batch.  
> 3. The doctor dashboard renders an explicit visual break rather than falsely connecting disjointed points.  
> 4. If the ESP32 retransmits the missing batch later (store-and-forward), the server accepts it, fills the gap, and updates the session status to `Completed`.

### Q4: Why can't a pulse oximeter (MAX30102) reading of 0 BPM be called "asystole"?
> **Answer:**  
> The MAX30102 is an optical photoplethysmogram (PPG) sensor, not an electrical cardiac lead. A reading of 0 BPM indicates that the optical probe has detached from the finger or peripheral perfusion is too weak to detect a pulse wave. Asystole is a formal electrophysiological diagnosis that can only be made using an ECG showing absence of electrical cardiac activity. Calling optical detachment "asystole" is a medical classification error.

---

## 7. Transparent Hardware Testing Status Disclosure

In accordance with university engineering ethics:
- **Fully Tested & Verified:**
  - FastAPI ingestion API, database schema, and composite unique constraints.
  - ECG reconstruction, physical gap preservation, and SOS zero-phase filtering.
  - Doctor web dashboard, interactive Plotly visualization, and authentication.
  - Python simulator and end-to-end data transmission pipeline.
  - Firmware compilation and logic syntax for ESP32.
- **Hardware Assembly Step (For Students with Physical Kit):**
  - Requires physical breadboard wiring with ESP32 DevKit V1 and SIM800L modem.
  - Requires active 2G SIM card with data balance from a local carrier.
  - Requires dedicated 4.0V battery/buck power supply for SIM800L transmission bursts.
