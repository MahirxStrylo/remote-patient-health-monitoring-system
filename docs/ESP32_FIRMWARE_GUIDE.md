# ESP32 Firmware & Hardware Integration Guide

**Project:** Remote Patient Health Monitoring System (University Engineering Prototype)  
**Target Node:** ESP32 DevKit V1 (30-pin / 38-pin Xtensa Dual-Core 240 MHz)  
**Sensors:** AD8232 (ECG), MAX30102 (HR + SpO₂), DS18B20 (Temperature)  
**Connectivity:** SIM800L (2G GSM/GPRS Cellular Modem)  
**Firmware File:** `firmware/esp32_health_monitor/esp32_health_monitor.ino`  

---

## 1. Required Arduino Libraries and Installation Steps

### A. Arduino IDE Setup
1. Download and install **Arduino IDE 2.x** (or Arduino IDE 1.8.19+) from [arduino.cc](https://www.arduino.cc/en/software).
2. Open **File** $\to$ **Preferences**.
3. In **Additional Board Manager URLs**, add:
   ```text
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Open **Tools** $\to$ **Board** $\to$ **Boards Manager...**, search for `esp32`, and install **esp32 by Espressif Systems** (version 2.0.14 or later).
5. Select your board under **Tools** $\to$ **Board** $\to$ **ESP32 Arduino** $\to$ **DOIT ESP32 DEVKIT V1**.

### B. Library Installation (via Arduino Library Manager)
Open **Sketch** $\to$ **Include Library** $\to$ **Manage Libraries...** and install:

| Library Name | Author | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **DallasTemperature** | Miles Burton | Latest (3.9.x+) | DS18B20 1-Wire temperature acquisition |
| **OneWire** | Paul Stoffregen | Latest (2.3.x+) | Low-level 1-Wire communication protocol |

### C. Built-in ESP32 Core Libraries (No Manual Download Needed)
- `Wire.h` — Hardware I2C for MAX30102.
- `HardwareSerial.h` — Hardware UART2 for SIM800L modem communication.
- `Arduino.h` / `time.h` — FreeRTOS task primitives and POSIX timestamp handling.

### D. Architectural Note on MAX30102 Driver
> [!NOTE]
> **Zero External Library Lock-In for MAX30102**:  
> Many 3rd-party Arduino MAX30102 libraries suffer from memory fragmentation, blocking FIFO loops, or outdated register maps that freeze the ESP32. This firmware implements an **embedded direct-register I2C driver** (lines 141–278) directly in `esp32_health_monitor.ino`. It configures sample averaging (4x), 100 Hz ADC sample rate, 411 µs pulse width, and performs real-time optical peak detection and AC/DC ratio calculation without requiring any external MAX30102 library.

---

## 2. Final Hardware Wiring Table

### Full Pin Interconnection Matrix

| ESP32 Pin | Connected Peripheral | Peripheral Pin | Signal Type | Electrical Notes / Protection |
| :--- | :--- | :--- | :--- | :--- |
| **GPIO 34** | AD8232 ECG | `OUTPUT` (AOUT) | Analog Input | ADC1_CH6 (0V to 3.3V input range) |
| **GPIO 33** | AD8232 ECG | `LO+` | Digital Input | Lead-Off positive comparator |
| **GPIO 32** | AD8232 ECG | `LO-` | Digital Input | Lead-Off negative comparator |
| **3V3** | AD8232 ECG | `3.3V` | DC Power | Connect to ESP32 3.3V rail |
| **GND** | AD8232 ECG | `GND` | Ground | Common system ground |
| **GPIO 21** | MAX30102 Oximeter | `SDA` | I2C Data | Internal / module pull-up to 3.3V |
| **GPIO 22** | MAX30102 Oximeter | `SCL` | I2C Clock | 400 kHz Fast I2C bus |
| **3V3** | MAX30102 Oximeter | `VIN` | DC Power | Connect to ESP32 3.3V rail |
| **GND** | MAX30102 Oximeter | `GND` | Ground | Common system ground |
| **GPIO 4** | DS18B20 Temp | `DATA` (DQ) | 1-Wire Bus | **Requires 4.7 kΩ pull-up resistor to 3.3V** |
| **3V3** | DS18B20 Temp | `VDD` | DC Power | Connect to ESP32 3.3V rail |
| **GND** | DS18B20 Temp | `GND` | Ground | Common system ground |
| **GPIO 16** | SIM800L Modem | `TXD` | UART RX (ESP32) | Direct connection (SIM800L TX $\to$ ESP32 RX2) |
| **GPIO 17** | SIM800L Modem | `RXD` | UART TX (ESP32) | **Via 1 kΩ / 2 kΩ resistor voltage divider** |
| **GPIO 27** | SIM800L Modem | `RST` | Digital Output | Optional hardware reset (active low) |
| **GND** | SIM800L Modem | `GND` | Ground | **Must share common ground with ESP32 & battery** |
| **EXT 4.0V**| SIM800L Modem | `VCC` | DC Power | **External 3.7V–4.2V Li-Ion / Buck (Up to 2.0A bursts)** |

```
Voltage Divider for SIM800L RXD:
ESP32 GPIO 17 (3.3V) ────[ 1 kΩ ]────┬──── SIM800L RXD (~2.2V - safe for 2.8V UART)
                                     │
                                  [ 2 kΩ ]
                                     │
                                    GND
```

### Critical Power Supply Warning for SIM800L
> [!CAUTION]
> **DO NOT power the SIM800L module from the ESP32 3.3V or 5V (VIN) pin.**  
> The SIM800L power amplifier draws **up to 2.0 Amperes peak current** during GSM RF transmission bursts. Attempting to power it from the ESP32 will drop the voltage below 3.6V, triggering an immediate hardware reset (`UNDER-VOLTAGE WARN`), killing the GPRS connection, and resetting the ESP32.  
> **Mandatory:** Power SIM800L from a 1S Li-Ion cell (18650 or Li-Po 3.7V–4.2V) or an LM2596 / MP1584 buck converter tuned to **4.0V**, with a **1000 µF low-ESR electrolytic capacitor** soldered directly across the SIM800L `VCC` and `GND` pins. Ensure ESP32 GND and SIM800L GND are tied together.

---

## 3. SIM800L AT-Command Troubleshooting Guide

During firmware startup and data transmission, the ESP32 outputs verbose diagnostic logs to the Serial Monitor at **115200 baud**. Use this reference to diagnose modem responses:

| Symptom / Log Output | Root Cause | Exact Remedy |
| :--- | :--- | :--- |
| `[ERROR] SIM800L not responding to AT` | 1. Baud rate mismatch<br>2. RX/TX pins swapped<br>3. SIM800L unpowered | 1. Verify ESP32 GPIO 16 $\to$ SIM800L TX, GPIO 17 $\to$ SIM800L RX.<br>2. Check if SIM800L LED is blinking.<br>3. Verify common GND between ESP32 and SIM800L battery. |
| `UNDER-VOLTAGE WARN` / Continuous reboot loops | Voltage drops below 3.6V during GSM RF burst | 1. Solder a 1000 µF / 16V capacitor directly across SIM800L `VCC` and `GND`.<br>2. Ensure battery or buck converter can supply $\ge 2.0\text{ A}$. |
| `[ERROR] SIM card not READY` (`+CPIN: NOT READY`) | SIM card not seated or PIN locked | 1. Remove SIM, clean contacts, re-insert firmly in micro-SIM slot.<br>2. Disable SIM PIN code using a mobile phone before using in modem. |
| `+CSQ: 0,0` or `+CSQ: 99,99` | No cellular radio signal | 1. Connect the external rod or spring antenna.<br>2. Move closer to a window (2G signal penetrates deep buildings poorly). |
| `[ERROR] GSM network registration timed out` (`+CREG: 0,2` or `0,3`) | Searching or network denied registration | 1. Confirm the SIM card has an active subscription.<br>2. Verify local 2G coverage (in Bangladesh: GP, Robi, Banglalink, Teletalk). |
| `[HTTP 601 NETWORK ERROR]` | GPRS bearer connection failed or target host unreachable | 1. Check APN string in firmware.<br>2. **Target IP is private LAN and unreachable via GPRS** (see Section 4). |
| `[HTTP 401 UNAUTHORIZED]` | Missing or invalid API key | Copy the active device API key from the Web Dashboard (`/devices`) into `DEVICE_API_KEY`. |
| `[HTTP 403 FORBIDDEN]` | Device ID / Patient ID mismatch | Verify `DEVICE_ID` matches the registered device and `PATIENT_ID` matches the patient assigned. |
| `[HTTP 409 CONFLICT]` | Sequence collision or closed session | The device sent a reused sequence number with a different batch ID, or session is already closed. The firmware automatically generates fresh session IDs on boot. |
| `[HTTP 413 TOO LARGE]` | Payload exceeds server batch limit | The batch has more samples than `MAX_ECG_SAMPLES_PER_BATCH` (configured to 250 in firmware, matching server limit of 5000). |
| `[OVERFLOW] Buffer queue full! Total overflows: X` | GPRS transmission took longer than queue capacity | The network is experiencing severe latency. The firmware drops old batches to protect memory while keeping the sampling clock synchronized. |

---

## 4. Server Address & APN Configuration Guide

### Understanding Private LAN vs. 2G Cellular Routing

```
[ ESP32 + SIM800L ]
         │
         ▼ (2G Cellular Airwaves)
[ Cellular Base Station (Tower) ]
         │
         ▼
[ Mobile Carrier Core Network (CGNAT) ]   <── Assigns private carrier IP (e.g., 10.x.x.x)
         │
         ▼ (Public Internet)
         │
       XXXXX   <── CANNOT REACH `http://192.168.1.50:8000` DIRECTLY!
         │         (192.168.x.x is private to your home/lab Wi-Fi router)
         ▼
[ Your Home / Lab Router ] ───> [ Your Laptop / FastAPI Server ]
```

> [!IMPORTANT]
> **Why `192.168.x.x` Does NOT Work with SIM800L GPRS**:  
> A cellular SIM card connects to the carrier's mobile packet network via Carrier-Grade NAT (CGNAT). The SIM800L is on the cellular carrier's network, while your laptop running FastAPI is behind your private home/university Wi-Fi router.  
> The cellular network has **no route** to your computer's `192.168.x.x` address. If you set `SERVER_HOST "192.168.1.x"` with SIM800L, the modem will return **HTTP 601 Network Error**.

### Solution: Exposing the Local Server for Cellular Ingestion

To allow the real SIM800L to send HTTP data to your laptop running FastAPI during evaluation:

#### Method 1: Using ngrok (Recommended — Free & 60-Second Setup)
1. Download [ngrok](https://ngrok.com/) on your laptop.
2. In a terminal, run:
   ```bash
   ngrok http 8000
   ```
3. ngrok gives you a public forwarding URL, for example:
   `https://c123-103-230-104-5.ngrok-free.app`
4. In `firmware/esp32_health_monitor/esp32_health_monitor.ino`:
   ```cpp
   #define SERVER_HOST  "c123-103-230-104-5.ngrok-free.app"
   #define SERVER_PORT  80
   ```
   *(Note: Set `SERVER_PORT` to 80 for standard HTTP forwarding).*

#### Method 2: Public Cloud / VPS Deployment
If your backend is hosted on a cloud instance (AWS EC2, DigitalOcean, Google Cloud Run, Railway, etc.), set `SERVER_HOST` to your domain or public IPv4 address.

#### Method 3: Wi-Fi Fallback Mode (For Indoor Demonstrations Without Public IP)
If you are demonstrating in a university room where 2G cellular reception is shielded or you cannot set up ngrok, enable Wi-Fi fallback in `esp32_health_monitor.ino`:
```cpp
#define USE_WIFI_FALLBACK true
#define WIFI_SSID         "Your_Lab_WiFi"
#define WIFI_PASS         "Your_Password"
#define SERVER_HOST       "192.168.1.100"  // Your laptop's LAN IP
#define SERVER_PORT       8000
```
This routes telemetry across the local Wi-Fi router directly to the FastAPI server while exercising the exact same FreeRTOS producer-consumer pipeline and JSON serialization.

### Cellular Carrier APN Settings (Bangladesh)
In `esp32_health_monitor.ino`, line 54:
```cpp
#define SIM_APN  "gpinternet"
```
Set according to your SIM card operator:
- **Grameenphone (GP):** `gpinternet`
- **Banglalink:** `blweb` (or `internet`)
- **Robi Axiata:** `internet`
- **Airtel Bangladesh:** `internet`
- **Teletalk:** `teletalk`

---

## 5. Test Procedure with Simulated Sensors (Software/Lab Mode)

This mode allows complete end-to-end verification of FreeRTOS dual-core task synchronization, queue management, JSON serialization, and server communication without needing physical sensors attached to the ESP32.

### Step-by-Step Procedure:
1. Open `firmware/esp32_health_monitor/esp32_health_monitor.ino`.
2. Confirm the simulation toggle is enabled:
   ```cpp
   #define SIMULATE_SENSORS true
   ```
3. Set your `SERVER_HOST`, `SERVER_PORT`, and `DEVICE_API_KEY`.
4. Connect the ESP32 to your PC via USB cable.
5. In Arduino IDE, select the COM port and click **Upload**.
6. Open **Tools** $\to$ **Serial Monitor** at **115200 baud**.
7. **Observe Serial Output:**
   - ESP32 boots and initializes FreeRTOS queues.
   - Core 0 starts generating 250 Hz P-Q-R-S-T ECG waveform counts (4 ms timer interval).
   - Core 1 serializes 250 samples (1 second of data) into standard JSON.
   - Core 1 initiates HTTP POST transmission.
   - Server returns `HTTP 200` with status `"accepted"`.
   - Sequence number increments from `1` to `2`, `3`, etc.
8. **Verify on Web Dashboard:**
   - Open `http://localhost:5173` in your browser.
   - Log in with `admin` / `admin123`.
   - Open **Patient P001** $\to$ verify real-time vitals display (Heart Rate ~74 BPM, SpO₂ ~98%, Temp ~36.6°C).
   - Open **ECG Recordings** $\to$ inspect live P-Q-R-S-T waveform in the interactive viewer.

---

## 6. Test Procedure with Physical Sensors

Follow this procedure when physical sensors are connected to the breadboard.

### Step-by-Step Procedure:
1. Wire the sensors according to the **Hardware Wiring Table** in Section 2.
2. Open `firmware/esp32_health_monitor/esp32_health_monitor.ino`.
3. Set the simulation toggle to `false`:
   ```cpp
   #define SIMULATE_SENSORS false
   ```
4. Flash the firmware to the ESP32 and open Serial Monitor at **115200 baud**.

### A. AD8232 ECG Acquisition Test
1. Connect the 3 electrode leads:
   - **RA (Red):** Right inner forearm / below right clavicle.
   - **LA (Yellow):** Left inner forearm / below left clavicle.
   - **RL (Green):** Right lower abdomen or right leg (Ground reference).
2. With electrodes detached:
   - Observe Serial Monitor: `lead_off: true`.
   - ADC counts output `0` (flatline). Notice that **no fake waveform** is synthesized.
3. Attach electrodes with conductive gel:
   - Observe Serial Monitor: `lead_off: false`.
   - Raw ADC counts fluctuate between 1500 and 2600 counts in rhythm with the heartbeat.
   - On the web dashboard, verify real-time ECG trace.

### B. MAX30102 Pulse Oximeter Test
1. Without finger on the sensor:
   - Red and IR LED illuminate.
   - IR counts remain below 50,000.
   - Serial Monitor shows `hasHeartRate = false`, `hasSpO2 = false`.
   - JSON payload outputs `"heart_rate_bpm": null, "spo2_percent": null`.
   - Web dashboard displays `Unavailable` (not a fake 72 BPM / 98%).
2. Place index finger firmly on sensor glass:
   - IR count rises above 50,000 threshold.
   - Pulse detection algorithm calculates heart rate and SpO₂ from AC/DC ratio.
   - JSON payload begins reporting real values (e.g., `76.4 BPM`, `97.8%`).

### C. DS18B20 Temperature Test
1. Sensor in ambient air:
   - Temperature outputs ambient value (e.g., `26.5°C`).
2. Touch sensor between thumb and forefinger:
   - Temperature rises progressively to body surface temperature (`33.0°C` – `36.0°C`).
3. Disconnect data wire (GPIO 4):
   - Dallas library returns `-127.0°C`.
   - Firmware catches invalid reading, sets `hasTemperature = false`, and transmits `"temperature_c": null`.

---

## 7. Hardware Testing Matrix: Software vs. Physical Requirements

Use this checklist during defense/evaluation to clarify which verification tests are performed in software simulation versus requiring physical laboratory hardware:

| Test Item | Can Verify in Software / Simulator | Requires Physical Hardware | Components Required for Physical Test |
| :--- | :---: | :---: | :--- |
| **API Ingestion & Schema Validation** | **YES** (`pytest` / `run_demo.py`) | Optional | None (Local PC) |
| **Idempotent Batch Retransmission** | **YES** (`test_ingest.py`) | Optional | None (Local PC) |
| **ECG Waveform Gap Reconstruction** | **YES** (Dashboard Viewer) | Optional | None (Local PC) |
| **Device API Key Verification** | **YES** (`test_auth.py`) | Optional | None (Local PC) |
| **FreeRTOS Dual-Core Task Scheduling**| **YES** (ESP32 USB Serial Monitor) | **YES** | ESP32 DevKit V1 board |
| **Queue Overflow & Buffer Integrity** | **YES** (ESP32 USB Serial Monitor) | **YES** | ESP32 DevKit V1 board |
| **AD8232 Lead-Off Detection (LO+/LO-)** | Synthetic toggle | **YES** | AD8232 module + 3 ECG electrode pads |
| **MAX30102 Optical AC/DC & SpO₂** | Synthetic toggle | **YES** | MAX30102 module + Human finger |
| **DS18B20 1-Wire Disconnect (`-127°C`)** | Synthetic toggle | **YES** | DS18B20 sensor + 4.7 kΩ resistor |
| **SIM800L 2.0A RF Peak Current Draw** | NO | **YES** | 1S Li-Ion battery / Buck + 1000 µF capacitor |
| **2G GPRS Tower Handshake & NITZ Time**| NO | **YES** | SIM800L + 2G SIM Card + Mobile Network |
| **Carrier CGNAT Routing vs. Public Server**| NO | **YES** | ngrok tunnel or Public VPS server |

---

## 8. Summary of Engineering Integrity Assurances

1. **No Artificial Data Under Fault Conditions**: When sensors are unplugged or electrodes disconnect, the firmware transmits JSON `null` or raw ADC flatlines. It never fakes physiological numbers.
2. **Deterministic Retransmission**: In the event of cellular timeouts, the exact same `batch_id` and `sequence_number` are retained. `globalSequence` advances only after confirmed HTTP 200 acceptance.
3. **No Sampling Clock Starvation**: By isolating the 250 Hz ADC acquisition on Core 0 with FreeRTOS `vTaskDelayUntil`, multi-second cellular network latencies on Core 1 never cause skipped ECG samples.
4. **NITZ Clock Sync**: Real UTC timestamps are acquired directly from local cellular towers via `AT+CLTS=1` and `AT+CCLK?`, ensuring synchronized patient records even across power cycles.
