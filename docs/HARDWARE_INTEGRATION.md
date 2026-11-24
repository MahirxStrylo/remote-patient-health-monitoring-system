# Hardware Integration Guide: ESP32 + AD8232 + MAX30102 + DS18B20 + SIM800L

This document specifies the hardware architecture, pinout, circuit design, non-blocking firmware architecture, AT command sequences, and network protocols for the Remote Patient Health Monitoring node.

---

## 1. System Overview

The patient monitoring node operates in rural, off-grid environments where Wi-Fi and 4G/5G may be unavailable or erratic, but standard 2G (GSM/GPRS) coverage remains accessible.

```
+--------------------+        +---------------------+
| AD8232 ECG Sensor  |------->|                     |
+--------------------+ (ADC)  |                     |
                              |                     |
+--------------------+ (I2C)  |   ESP32 DevKit V1   |        +--------------------+
| MAX30102 HR & SpO2 |------->|   Microcontroller   |------->| SIM800L GSM/GPRS   |==[ 2G GPRS ]==> Internet ==> FastAPI Server
+--------------------+        |                     | (UART) | Module             |
                              |                     |        +--------------------+
+--------------------+        |                     |
| DS18B20 Body Temp  |------->|                     |
+--------------------+ (1-Wire|                     |
                              +---------------------+
```

### Component Selection Rationale

1. **ESP32 DevKit V1 (Main MCU)**:
   - Dual 32-bit Xtensa cores at 240 MHz.
   - Core 0 runs hardware timers and real-time sensor sampling interrupts (250 Hz for ECG).
   - Core 1 handles buffer aggregation, JSON serialization, and SIM800L UART communication.
   - Dedicated hardware UART ports (UART0 for debug, UART2 for SIM800L).
2. **AD8232 (Single-Lead ECG Front End)**:
   - Integrated analog front-end for cardiac signal biopotential measurement.
   - Includes instrumentation amplifier, high-pass filter, and right-leg drive (RLD) circuit.
   - Output provides raw analog voltage directly to ESP32 ADC pin (GPIO 34 / ADC1_CH6).
   - Digital Lead-Off pins (`LO+`, `LO-`) indicate electrode contact state.
3. **MAX30102 (Pulse Oximeter & Heart Rate)**:
   - Integrated optical red (660 nm) and infrared (880 nm) LEDs with photodetector.
   - I2C communication interface (standard address `0x57`).
4. **DS18B20 (Digital Temperature Sensor)**:
   - Calibrated 1-Wire digital thermometer ($\pm 0.5^\circ\text{C}$ accuracy from $-10^\circ\text{C}$ to $+85^\circ\text{C}$).
   - External $4.7\text{ k}\Omega$ pull-up resistor to 3.3V.
5. **SIM800L (2G GSM/GPRS Cellular Modem)**:
   - Quad-band 850/900/1800/1900 MHz GSM/GPRS module.
   - Communicates with ESP32 via standard Hayes AT commands over UART.
   - Intentionally selected for maximum rural geographical coverage over 2G networks.

---

## 2. Wiring and Schematic Diagram

```
           +---------------------------------------------+
           |               ESP32 DevKit V1               |
           |                                             |
           |  3V3 ---------+                             |
           |  GND ---------|---------+                   |
           |               |         |                   |
           |  GPIO 34 <----+ (AOUT)  |                   |
           |  GPIO 32 <----+ (LO-)   |  AD8232 ECG       |
           |  GPIO 33 <----+ (LO+)   |                   |
           |  3V3  --------> (3V3)   |                   |
           |  GND  --------> (GND)---+                   |
           |                                             |
           |  GPIO 21 (SDA) <> (SDA)                     |
           |  GPIO 22 (SCL) -> (SCL)  MAX30102 Oximeter  |
           |  3V3  ----------> (VIN)                     |
           |  GND  ----------> (GND)                     |
           |                                             |
           |  GPIO 4 (1-Wire)<> (DATA) [4.7k to 3V3]     |
           |  3V3  ----------> (VDD)  DS18B20 Temp       |
           |  GND  ----------> (GND)                     |
           |                                             |
           |  GPIO 16 (RX2) <- (TXD)  SIM800L Modem      |
           |  GPIO 17 (TX2) -> (RXD)  [Voltage Divider]  |
           |  GND  ----------> (GND)                     |
           |  GPIO 27 -------> (RST)                     |
           +---------------------------------------------+
                                     |
               +---------------------+
               |
     +---------+----------+
     |   External 4.0V    | ====> Powers SIM800L VCC
     |   Li-Ion / Buck    |       (Needs up to 2.0A bursts)
     +--------------------+
```

### Critical Electrical Safety and Hardware Notes

> [!WARNING]
> **Electrical Isolation Requirement**: Real biopotential (ECG) measurements on human subjects must NEVER be performed while the microcontroller is connected via USB to a mains-powered PC. Use an isolated battery power supply or an optical/magnetic USB isolator rated for medical biopotentials ($>4\text{ kV}$ dielectric isolation).

> [!IMPORTANT]
> **SIM800L Power Supply Requirements**: The SIM800L requires an operating voltage between **3.7V and 4.2V** (nominal 4.0V) and draws **up to 2.0A peak current** during GSM RF transmission bursts. Powering SIM800L directly from the ESP32 3.3V or 5V rail will result in modem brownouts (`UNDER-VOLTAGE WARN` / unexpected reboot). Power SIM800L from a dedicated 1S Li-Ion cell or buck converter rated for $\ge 3\text{A}$ with a $1000\mu\text{F}$ low-ESR capacitor across `VCC` and `GND`.

> [!NOTE]
> **UART Logic Level Translation**: SIM800L UART is 2.8V-3.3V tolerant on RX, while ESP32 outputs 3.3V logic. A simple resistor divider ($1\text{ k}\Omega / 2\text{ k}\Omega$) on ESP32 TX $\to$ SIM800L RX prevents signal over-driving.

---

## 3. Firmware Architecture: Non-Blocking FreeRTOS Pipeline

To avoid missing ECG samples during slow cellular network handshakes, the ESP32 firmware uses a double-buffered producer-consumer model running on FreeRTOS:

```
[Hardware Timer @ 250 Hz]
          │ (Interrupt)
          ▼
   +--------------+        When Buffer Full (e.g. 2,500 samples)
   | Sampling ISR | ──────────────────────────────────────────+
   +--------------+                                           │
          │                                                   ▼
   Fills active buffer (Buffer A)                 Enqueues Buffer Pointer
                                                  into FreeRTOS Queue
                                                              │
                                                              ▼
                                                   +----------------------+
                                                   | Cellular Task        |
                                                   | (Core 1)             |
                                                   | - Read MAX30102      |
                                                   | - Read DS18B20       |
                                                   | - Build JSON Payload |
                                                   | - Send via AT HTTP   |
                                                   +----------------------+
```

### Dual-Buffer Mechanism
1. **Buffer A & Buffer B**: Each holds 2,500 samples (10 seconds at 250 Hz).
2. While Core 1 is waiting for cellular transmission of Buffer A, Core 0 continues filling Buffer B in the background via hardware timer interrupts.
3. At no point does a cellular transmission delay interrupt the cardiac sampling clock.

---

## 4. SIM800L AT Command Sequence

### Phase 1: Initialization & Network Registration
```text
AT
<-- OK
ATE0                     (Disable echo)
<-- OK
AT+CPIN?                 (Verify SIM card status)
<-- +CPIN: READY
AT+CSQ                   (Check signal strength, e.g. 15-31 is good)
<-- +CSQ: 18,0
AT+CREG?                 (Check GSM network registration)
<-- +CREG: 0,1           (1 = Registered, home network; 5 = Registered, roaming)
AT+CGATT?                (Check GPRS attach status)
<-- +CGATT: 1            (1 = Attached to GPRS)
```

### Phase 2: GPRS Bearer Configuration
```text
AT+SAPBR=3,1,"CONTYPE","GPRS"
<-- OK
AT+SAPBR=3,1,"APN","internet"   (Operator APN, e.g. "internet", "iot.carrier.com")
<-- OK
AT+SAPBR=1,1                    (Open GPRS bearer)
<-- OK
AT+SAPBR=2,1                    (Query assigned IP address)
<-- +SAPBR: 1,1,"10.142.56.88"
```

### Phase 3: HTTP POST Telemetry Transmission
```text
AT+HTTPINIT
<-- OK
AT+HTTPPARA="CID",1
<-- OK
AT+HTTPPARA="URL","http://192.168.1.100:8000/api/v1/ingest"
<-- OK
AT+HTTPPARA="CONTENT","application/json"
<-- OK
AT+HTTPPARA="USERDATA","X-Device-API-Key: rhm_<key_id>_<secret>"
<-- OK

// Specify payload byte length and maximum timeout
AT+HTTPDATA=1845,10000
<-- DOWNLOAD

// [Transmit JSON payload: device_id, patient_id, session_id, sequence_number, ecg_samples, vitals]
// {"device_id":"ESP32-001","patient_id":"P001","session_id":"SES-ESP32-001-2906c652","sequence_number":1,...}
<-- OK

// Trigger HTTP POST action (Method 1 = POST)
AT+HTTPACTION=1
<-- OK
<-- +HTTPACTION: 1,200,128    (Action 1, HTTP 200, 128 response bytes)

// Read server acknowledgement response
AT+HTTPREAD
<-- +HTTPREAD: 128
<-- {"batch_id":"...","session_id":"SES-...","sequence_number":1,"status":"accepted",...}
<-- OK

// Terminate HTTP session
AT+HTTPTERM
<-- OK
```

---

## 5. TLS / SSL Security and Gateway Architecture for SIM800L

The SIM800L firmware (`SIM800 R14.18`) includes limited SSL/TLS 1.0 support. Many modern cloud infrastructures enforce TLS 1.2 or TLS 1.3 with modern cipher suites that legacy SIM800L basebands cannot negotiate.

### Architectural Solution: Secure Local / Cellular Ingestion Gateway

For field deployments where the modem cannot negotiate TLS 1.3 directly:

1. **Option A: GPRS Private APN (Direct VPN)**
   - The SIM card operates on a private cellular APN that routes traffic directly into a private VPC or VPN tunnel without traversing the public internet.
2. **Option B: Secure Ingestion Reverse Proxy / Gateway**
   - The SIM800L sends HTTP payloads across the cellular network to an authorized static IP gateway server located inside the provider or clinic network.
   - The gateway validates the `X-Device-API-Key`, terminates modern TLS 1.3, and proxies requests to the main FastAPI server.
   - Doctor dashboard access from web browsers always uses modern HTTPS/TLS 1.3.

---

## 6. Pre-Deployment Hardware Checklist

- [ ] Confirm SIM card has active 2G data plan enabled.
- [ ] Measure voltage on SIM800L VCC during transmission: must not drop below 3.6V.
- [ ] Verify AD8232 output voltage swing stays within ESP32 ADC input limits (0V to 3.3V).
- [ ] Ensure right-leg drive (RLD) electrode is connected to patient right leg or lower abdomen for common-mode noise cancellation.
- [ ] Run test with `simulator/send_test_data.py` first to verify server ingestion before flashing ESP32 firmware.
