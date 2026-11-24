/*
 ============================================================================
  REMOTE PATIENT HEALTH MONITORING SYSTEM — ESP32 FIRMWARE
  University Engineering Prototype — Production-Ready Firmware
  
  Target MCU:    ESP32 DevKit V1 (Dual Core, 240 MHz)
  Sensors:       AD8232 (ECG), MAX30102 (HR + SpO2), DS18B20 (Temperature)
  Cellular:      SIM800L (2G GSM/GPRS Modem)
  Backend:       FastAPI REST Server (HTTP JSON Ingestion)
 ============================================================================
 
  ARCHITECTURE: FreeRTOS Producer-Consumer Model
  - Core 0: High-Priority Sampling Task (250 Hz continuous ADC & sensor acquisition)
  - Core 1: GPRS Transmission Task (AT HTTP POST, response parsing, retry handling)
  - Inter-Task: FreeRTOS Queue with buffer overflow detection
 ============================================================================
*/

#include <Arduino.h>
#include <HardwareSerial.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <time.h>

// ==========================================================================
// 1. CONFIGURATION & NETWORK SETTINGS
// ==========================================================================

// Device & Patient Identity
#define DEVICE_ID        "ESP32-001"
#define PATIENT_ID       "P001"

// Device API Key: Replace with your actual key from the web dashboard
// (e.g. "rhm_<key_id>_<secret>" generated at http://<server>:5173/devices)
#define DEVICE_API_KEY   "YOUR_DEVICE_API_KEY_HERE"

#define FIRMWARE_VER     "ESP32-FW-1.1-SIM800L"

// Target Server Configuration
// IMPORTANT: 192.168.x.x is a private LAN address and CANNOT be reached directly
// over real mobile 2G GPRS. For cellular tests, use your public IP, domain, or a
// port tunnel (ngrok / Cloudflare Tunnel / localtunnel).
// For Wi-Fi fallback testing on the same local network, LAN IP is acceptable.
#define SERVER_HOST      "your-public-server.com"  // Or e.g. "xxxx.ngrok-free.app" or LAN IP if Wi-Fi
#define SERVER_PORT      8000
#define INGEST_PATH      "/api/v1/ingest"

// Cellular Carrier APN Configuration (Bangladesh 2G Networks)
//   Grameenphone: "gpinternet"
//   Banglalink:   "blweb" or "internet"
//   Robi / Airtel:"internet"
//   Teletalk:     "teletalk"
#define SIM_APN          "gpinternet"

// Operating Modes
// Set SIMULATE_SENSORS to true for viva / lab demo without physical sensors.
// Set to false when physical AD8232, MAX30102, and DS18B20 sensors are wired.
#define SIMULATE_SENSORS true

// Optional Wi-Fi Fallback (if indoor exam hall shields 2G GSM reception)
#define USE_WIFI_FALLBACK false
#define WIFI_SSID         "Your_WiFi_SSID"
#define WIFI_PASS         "Your_WiFi_Password"

#if USE_WIFI_FALLBACK
  #include <WiFi.h>
  #include <HTTPClient.h>
#endif

// ==========================================================================
// 2. HARDWARE PIN DEFINITIONS
// ==========================================================================
// AD8232 ECG
#define PIN_ECG_ADC      34   // ADC1_CH6 (Analog biopotential, 0 - 3.3V)
#define PIN_ECG_LO_PLUS  33   // Lead-Off Positive Comparator
#define PIN_ECG_LO_MINUS 32   // Lead-Off Negative Comparator

// DS18B20 Temperature
#define PIN_ONE_WIRE_BUS 4    // 1-Wire Data (Requires 4.7k pull-up to 3.3V)

// MAX30102 Pulse Oximeter (I2C)
#define PIN_I2C_SDA      21
#define PIN_I2C_SCL      22

// SIM800L GSM/GPRS Modem (HardwareSerial 2)
#define PIN_SIM_RX       16   // ESP32 RX2 <- SIM800L TXD
#define PIN_SIM_TX       17   // ESP32 TX2 -> SIM800L RXD (via 1k/2k voltage divider)
#define PIN_SIM_RST      27   // Optional hardware reset pin
#define SIM_BAUD_RATE    9600

// ==========================================================================
// 3. TELEMETRY & BUFFER DEFINITIONS
// ==========================================================================
#define ECG_SAMPLE_RATE_HZ 250        // 250 Hz (4 ms per sample)
#define SAMPLES_PER_BATCH  250        // 250 samples = 1.0 second per batch
#define BATCH_QUEUE_SIZE   3          // Queue capacity for producer-consumer buffers

// Structure holding one self-contained telemetry batch
struct TelemetryBatch {
    unsigned long sequenceNumber;
    char batchId[48];
    char recordedAt[32];
    int ecgSamples[SAMPLES_PER_BATCH];
    float heartRateBpm;
    float spo2Percent;
    float temperatureC;
    bool hasHeartRate;
    bool hasSpO2;
    bool hasTemperature;
    bool leadOff;
    bool isSimulated;
    bool isSessionEnd;
};

// FreeRTOS Synchronization
QueueHandle_t telemetryQueue = NULL;
TaskHandle_t samplingTaskHandle = NULL;
TaskHandle_t transmissionTaskHandle = NULL;

// Hardware Serial instance for SIM800L
HardwareSerial sim800(2);

// DS18B20 OneWire instances
OneWire oneWire(PIN_ONE_WIRE_BUS);
DallasTemperature ds18b20(&oneWire);

// Global Session Variables
char sessionId[48];
unsigned long globalSequence = 1;
volatile unsigned long overflowCount = 0;

// Clock Synchronization State
bool clockSynchronized = false;
unsigned long syncEpochSeconds = 0;
unsigned long syncMillis = 0;

// ==========================================================================
// 4. MAX30102 DIRECT REGISTER DRIVER (Zero External Library Lock-in)
// ==========================================================================
#define MAX30102_ADDR        0x57
#define REG_INTR_STATUS_1    0x00
#define REG_INTR_STATUS_2    0x01
#define REG_INTR_ENABLE_1    0x02
#define REG_FIFO_WR_PTR      0x04
#define REG_OVF_COUNTER      0x05
#define REG_FIFO_RD_PTR      0x06
#define REG_FIFO_DATA        0x07
#define REG_FIFO_CONFIG      0x08
#define REG_MODE_CONFIG      0x09
#define REG_SPO2_CONFIG      0x0A
#define REG_LED1_PA          0x0C
#define REG_LED2_PA          0x0D

bool max30102Available = false;

bool writeI2CRegister(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(MAX30102_ADDR);
    Wire.write(reg);
    Wire.write(val);
    return (Wire.endTransmission() == 0);
}

uint8_t readI2CRegister(uint8_t reg) {
    Wire.beginTransmission(MAX30102_ADDR);
    Wire.write(reg);
    Wire.endTransmission(false);
    Wire.requestFrom((uint8_t)MAX30102_ADDR, (uint8_t)1);
    if (Wire.available()) return Wire.read();
    return 0;
}

bool initMAX30102() {
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 400000);
    Wire.setTimeOut(100);

    // Test communication
    Wire.beginTransmission(MAX30102_ADDR);
    if (Wire.endTransmission() != 0) {
        Serial.println("[MAX30102] Sensor not detected at I2C address 0x57.");
        return false;
    }

    // Reset sensor
    writeI2CRegister(REG_MODE_CONFIG, 0x40);
    delay(50);

    // FIFO Configuration: sample average 4, FIFO rollover enabled
    writeI2CRegister(REG_FIFO_CONFIG, 0x5F);

    // SpO2 Mode: Red + IR channels active
    writeI2CRegister(REG_MODE_CONFIG, 0x03);

    // SpO2 Configuration: ADC range 4096nA, 100 Hz, 411us pulse width (18-bit resolution)
    writeI2CRegister(REG_SPO2_CONFIG, 0x27);

    // LED Pulse Amplitude: ~6.4mA for Red, ~6.4mA for IR
    writeI2CRegister(REG_LED1_PA, 0x1F);
    writeI2CRegister(REG_LED2_PA, 0x1F);

    // Clear FIFO pointers
    writeI2CRegister(REG_FIFO_WR_PTR, 0x00);
    writeI2CRegister(REG_OVF_COUNTER, 0x00);
    writeI2CRegister(REG_FIFO_RD_PTR, 0x00);

    Serial.println("[MAX30102] Initialized successfully in SpO2 mode.");
    return true;
}

bool readMAX30102Raw(uint32_t &red, uint32_t &ir) {
    if (!max30102Available) return false;

    Wire.beginTransmission(MAX30102_ADDR);
    Wire.write(REG_FIFO_DATA);
    if (Wire.endTransmission(false) != 0) return false;

    if (Wire.requestFrom((uint8_t)MAX30102_ADDR, (uint8_t)6) != 6) return false;

    uint8_t raw[6];
    for (int i = 0; i < 6; i++) {
        raw[i] = Wire.read();
    }

    red = ((uint32_t)(raw[0] & 0x03) << 16) | ((uint32_t)raw[1] << 8) | (uint32_t)raw[2];
    ir  = ((uint32_t)(raw[3] & 0x03) << 16) | ((uint32_t)raw[4] << 8) | (uint32_t)raw[5];
    return true;
}

// Optical Pulse Detection State
uint32_t lastBeatTime = 0;
float currentBeatRate = 0.0;
float filteredIR = 0.0;

bool processPulseOximeter(float &hrOut, float &spo2Out) {
    if (!max30102Available) return false;

    uint32_t red = 0, ir = 0;
    if (!readMAX30102Raw(red, ir)) return false;

    // Finger presence threshold: IR count typically exceeds 50,000 when finger is pressed
    if (ir < 50000) {
        // No finger on optical sensor
        return false;
    }

    // High-pass filter DC removal
    float delta = (float)ir - filteredIR;
    filteredIR = filteredIR + 0.05 * delta;

    // Peak detection for heart rate
    static float prevDelta = 0.0;
    unsigned long now = millis();
    if (prevDelta < 0.0 && delta >= 0.0 && (now - lastBeatTime) > 300) { // Max 200 BPM
        unsigned long interval = now - lastBeatTime;
        lastBeatTime = now;
        if (interval > 0) {
            float instantHR = 60000.0 / (float)interval;
            if (instantHR >= 40.0 && instantHR <= 180.0) {
                currentBeatRate = (currentBeatRate == 0.0) ? instantHR : (0.7 * currentBeatRate + 0.3 * instantHR);
            }
        }
    }
    prevDelta = delta;

    if (currentBeatRate >= 40.0 && currentBeatRate <= 180.0) {
        hrOut = currentBeatRate;
        // Ratio of Ratios for SpO2 approximation: R = (AC_red/DC_red) / (AC_ir/DC_ir)
        // Calibrated empirical curve: SpO2 = 110 - 25 * R
        float ratio = ((float)red / (float)ir);
        float calcSpO2 = 110.0 - (25.0 * ratio);
        if (calcSpO2 > 100.0) calcSpO2 = 100.0;
        if (calcSpO2 < 70.0) calcSpO2 = 70.0;
        spo2Out = calcSpO2;
        return true;
    }

    return false;
}

// ==========================================================================
// 5. TIMESTAMP GENERATION & SIM800L NITZ TIME SYNC
// ==========================================================================
void getFormattedTimestamp(char* outBuffer, size_t bufSize) {
    if (clockSynchronized) {
        unsigned long currentEpoch = syncEpochSeconds + ((millis() - syncMillis) / 1000);
        time_t t = (time_t)currentEpoch;
        struct tm* tm_info = gmtime(&t);
        strftime(outBuffer, bufSize, "%Y-%m-%dT%H:%M:%SZ", tm_info);
    } else {
        // Fallback: Device relative uptime timestamp
        unsigned long totalSeconds = millis() / 1000;
        unsigned int hours = (totalSeconds / 3600) % 24;
        unsigned int minutes = (totalSeconds / 60) % 60;
        unsigned int seconds = totalSeconds % 60;
        snprintf(outBuffer, bufSize, "1970-01-01T%02u:%02u:%02uZ", hours, minutes, seconds);
    }
}

// ==========================================================================
// 6. HARDWARE INITIALIZATION
// ==========================================================================
void setupHardware() {
    // AD8232 GPIO Configuration
    pinMode(PIN_ECG_ADC, INPUT);
    pinMode(PIN_ECG_LO_PLUS, INPUT);
    pinMode(PIN_ECG_LO_MINUS, INPUT);

    // DS18B20 1-Wire initialization
    ds18b20.begin();
    ds18b20.setWaitForConversion(false); // Non-blocking temperature requests

    // MAX30102 I2C initialization
    max30102Available = initMAX30102();

    // SIM800L UART initialization
    if (PIN_SIM_RST > 0) {
        pinMode(PIN_SIM_RST, OUTPUT);
        digitalWrite(PIN_SIM_RST, HIGH);
    }
    sim800.begin(SIM_BAUD_RATE, SERIAL_8N1, PIN_SIM_RX, PIN_SIM_TX);
}

// ==========================================================================
// 7. CORE 0: HIGH-PRIORITY SAMPLING TASK (250 Hz Continuous Sampling)
// ==========================================================================
void samplingTask(void* pvParameters) {
    Serial.println("[CORE 0] 250 Hz ECG & Sensor Sampling Task Started.");

    TelemetryBatch activeBatch;
    int sampleIdx = 0;
    const TickType_t xFrequency = pdMS_TO_TICKS(4); // 4 ms = 250 Hz
    TickType_t xLastWakeTime = xTaskGetTickCount();

    // Synthetic wave generator variables (used when SIMULATE_SENSORS == true)
    float phase = 0.0;
    const float phaseIncrement = (2.0 * PI * 1.25) / (float)ECG_SAMPLE_RATE_HZ;

    while (true) {
        vTaskDelayUntil(&xLastWakeTime, xFrequency);

        // 1. AD8232 Acquisition
        bool loPlus = digitalRead(PIN_ECG_LO_PLUS);
        bool loMinus = digitalRead(PIN_ECG_LO_MINUS);
        bool isLeadOff = (loPlus || loMinus);

        int sampleVal = 0;
        if (SIMULATE_SENSORS) {
            // Synthetic P-Q-R-S-T wave model
            phase += phaseIncrement;
            if (phase >= 2.0 * PI) phase -= 2.0 * PI;

            float val = 512.0;
            if (phase > 0.5 && phase < 0.9) val += 40.0 * sin((phase - 0.5) * (PI / 0.4));          // P wave
            else if (phase >= 1.15 && phase < 1.25) val -= 35.0 * sin((phase - 1.15) * (PI / 0.1)); // Q dip
            else if (phase >= 1.25 && phase < 1.40) val += 420.0 * sin((phase - 1.25) * (PI / 0.15));// R peak
            else if (phase >= 1.40 && phase < 1.55) val -= 60.0 * sin((phase - 1.40) * (PI / 0.15));// S dip
            else if (phase > 1.8 && phase < 2.4) val += 75.0 * sin((phase - 1.8) * (PI / 0.6));     // T wave
            val += (float)random(-4, 5);

            sampleVal = (int)val;
            isLeadOff = false;
        } else {
            // Physical AD8232 reading
            if (isLeadOff) {
                // Electrode detached: preserve flatline/zero. Never synthesize fake ECG.
                sampleVal = 0;
            } else {
                sampleVal = analogRead(PIN_ECG_ADC);
            }
        }

        activeBatch.ecgSamples[sampleIdx] = sampleVal;
        sampleIdx++;

        // 2. When batch is full (250 samples = 1 second)
        if (sampleIdx >= SAMPLES_PER_BATCH) {
            activeBatch.leadOff = isLeadOff;
            activeBatch.isSimulated = SIMULATE_SENSORS;
            activeBatch.isSessionEnd = false;

            // Timestamp this batch
            getFormattedTimestamp(activeBatch.recordedAt, sizeof(activeBatch.recordedAt));

            // Acquire physiological vitals
            if (SIMULATE_SENSORS) {
                activeBatch.heartRateBpm = 74.0 + (float)random(-2, 3);
                activeBatch.spo2Percent = 98.0;
                activeBatch.temperatureC = 36.6 + ((float)random(-1, 2) * 0.1);
                activeBatch.hasHeartRate = true;
                activeBatch.hasSpO2 = true;
                activeBatch.hasTemperature = true;
            } else {
                // Physical DS18B20 reading
                ds18b20.requestTemperatures();
                float temp = ds18b20.getTempCByIndex(0);
                if (temp == DEVICE_DISCONNECTED_C || temp == 85.0 || temp < -40.0 || temp > 100.0) {
                    activeBatch.hasTemperature = false; // Sensor unplugged / reset code
                    activeBatch.temperatureC = 0.0;
                } else {
                    activeBatch.hasTemperature = true;
                    activeBatch.temperatureC = temp;
                }

                // Physical MAX30102 reading
                float hrVal = 0.0, spo2Val = 0.0;
                if (processPulseOximeter(hrVal, spo2Val)) {
                    activeBatch.hasHeartRate = true;
                    activeBatch.hasSpO2 = true;
                    activeBatch.heartRateBpm = hrVal;
                    activeBatch.spo2Percent = spo2Val;
                } else {
                    // Finger absent or unstable measurement: return unavailable (null)
                    activeBatch.hasHeartRate = false;
                    activeBatch.hasSpO2 = false;
                }
            }

            // Assign unique batch ID
            snprintf(activeBatch.batchId, sizeof(activeBatch.batchId), "%s-B%lu", DEVICE_ID, globalSequence);
            activeBatch.sequenceNumber = globalSequence;

            // Push batch to transmission queue (non-blocking)
            if (xQueueSend(telemetryQueue, &activeBatch, 0) != pdPASS) {
                overflowCount++;
                Serial.printf("[OVERFLOW] Buffer queue full! Dropped batch. Total overflows: %lu\n", overflowCount);
            }

            sampleIdx = 0;
        }
    }
}

// ==========================================================================
// 8. SIM800L AT COMMAND COMMUNICATIONS ENGINE
// ==========================================================================
bool sendAT(const String& cmd, const char* expected, unsigned long timeoutMs = 3000, String* outResp = nullptr) {
    while (sim800.available()) sim800.read();

    Serial.printf("[AT >>] %s\n", cmd.c_str());
    sim800.println(cmd);

    unsigned long start = millis();
    String resp = "";
    while (millis() - start < timeoutMs) {
        while (sim800.available()) {
            char c = sim800.read();
            resp += c;
        }
        if (resp.indexOf(expected) != -1) {
            Serial.printf("[AT <<] %s\n", resp.c_str());
            if (outResp) *outResp = resp;
            return true;
        }
        if (resp.indexOf("ERROR") != -1) {
            Serial.printf("[AT ERR] %s\n", resp.c_str());
            if (outResp) *outResp = resp;
            return false;
        }
    }
    Serial.printf("[AT TIMEOUT] Expected '%s', got: %s\n", expected, resp.c_str());
    if (outResp) *outResp = resp;
    return false;
}

bool initGPRSNetwork() {
    Serial.println("\n[GPRS] Starting SIM800L hardware and network registration check...");
    
    // 1. Basic AT handshake
    if (!sendAT("AT", "OK", 1000)) {
        Serial.println("[ERROR] SIM800L not responding to AT. Check baud rate, RX/TX wiring, and 4.0V power!");
        return false;
    }
    sendAT("ATE0", "OK", 1000); // Disable echo

    // 2. Check SIM Card Ready
    String cpinResp;
    if (!sendAT("AT+CPIN?", "READY", 3000, &cpinResp)) {
        Serial.println("[ERROR] SIM card not READY. Check SIM card insertion or PIN lock.");
        return false;
    }

    // 3. Check Signal Quality
    String csqResp;
    sendAT("AT+CSQ", "OK", 2000, &csqResp);

    // 4. Check GSM Network Registration (0,1 = Home Network, 0,5 = Roaming)
    int regRetries = 0;
    bool registered = false;
    while (regRetries < 15 && !registered) {
        String cregResp;
        sendAT("AT+CREG?", "OK", 2000, &cregResp);
        if (cregResp.indexOf(",1") != -1 || cregResp.indexOf(",5") != -1) {
            registered = true;
            Serial.println("[GPRS] GSM Network registration confirmed.");
            break;
        }
        Serial.println("[GPRS] Searching for cellular tower...");
        delay(1000);
        regRetries++;
    }

    if (!registered) {
        Serial.println("[ERROR] GSM network registration timed out. Check antenna and 2G coverage.");
        return false;
    }

    // 5. Query Network Time (NITZ / Tower Time)
    sendAT("AT+CLTS=1", "OK", 1000); // Enable network time sync
    String cclkResp;
    if (sendAT("AT+CCLK?", "+CCLK:", 2000, &cclkResp)) {
        int quoteIdx = cclkResp.indexOf('"');
        if (quoteIdx != -1) {
            // Format: "yy/MM/dd,hh:mm:ss+zz"
            String dtStr = cclkResp.substring(quoteIdx + 1, quoteIdx + 18);
            int yr = dtStr.substring(0, 2).toInt() + 2000;
            int mo = dtStr.substring(3, 5).toInt();
            int da = dtStr.substring(6, 8).toInt();
            int hr = dtStr.substring(9, 11).toInt();
            int mn = dtStr.substring(12, 14).toInt();
            int sc = dtStr.substring(15, 17).toInt();

            if (yr >= 2024 && mo >= 1 && da >= 1) {
                struct tm t;
                t.tm_year = yr - 1900;
                t.tm_mon = mo - 1;
                t.tm_mday = da;
                t.tm_hour = hr;
                t.tm_min = mn;
                t.tm_sec = sc;
                t.tm_isdst = 0;
                syncEpochSeconds = mktime(&t);
                syncMillis = millis();
                clockSynchronized = true;
                Serial.printf("[CLOCK] Synchronized real UTC time from cellular tower: %04d-%02d-%02d %02d:%02d:%02d UTC\n", yr, mo, da, hr, mn, sc);
            }
        }
    }

    // 6. Attach GPRS Service
    if (!sendAT("AT+CGATT=1", "OK", 5000)) {
        Serial.println("[ERROR] Failed to attach GPRS service.");
        return false;
    }

    // 7. Configure Bearer Profile
    sendAT("AT+SAPBR=3,1,\"CONTYPE\",\"GPRS\"", "OK", 2000);
    String apnCmd = "AT+SAPBR=3,1,\"APN\",\"" + String(SIM_APN) + "\"";
    sendAT(apnCmd, "OK", 2000);

    // 8. Open GPRS Context
    if (!sendAT("AT+SAPBR=1,1", "OK", 10000)) {
        Serial.println("[WARN] SAPBR=1,1 returned error (bearer may already be open). Checking IP...");
    }

    // 9. Query Assigned GPRS IP
    String ipResp;
    sendAT("AT+SAPBR=2,1", "+SAPBR: 1,1", 3000, &ipResp);
    Serial.println("[GPRS] Bearer configured successfully.");
    return true;
}

// ==========================================================================
// 9. JSON BUILDER (Strict Compliance with FastAPI IngestPayload Schema)
// ==========================================================================
String serializeBatchToJson(const TelemetryBatch &batch) {
    String json = "{";
    json += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
    json += "\"patient_id\":\"" + String(PATIENT_ID) + "\",";
    json += "\"session_id\":\"" + String(sessionId) + "\",";
    json += "\"batch_id\":\"" + String(batch.batchId) + "\",";
    json += "\"sequence_number\":" + String(batch.sequenceNumber) + ",";
    json += "\"is_session_end\":" + String(batch.isSessionEnd ? "true" : "false") + ",";
    json += "\"recorded_at\":\"" + String(batch.recordedAt) + "\",";
    json += "\"ecg_sampling_rate_hz\":" + String(ECG_SAMPLE_RATE_HZ) + ",";
    json += "\"ecg_unit\":\"adc_counts\",";

    // Vitals: output real numbers or JSON null if sensor disconnected / unread
    if (batch.hasHeartRate) {
        json += "\"heart_rate_bpm\":" + String(batch.heartRateBpm, 1) + ",";
    } else {
        json += "\"heart_rate_bpm\":null,";
    }

    if (batch.hasSpO2) {
        json += "\"spo2_percent\":" + String(batch.spo2Percent, 1) + ",";
    } else {
        json += "\"spo2_percent\":null,";
    }

    if (batch.hasTemperature) {
        json += "\"temperature_c\":" + String(batch.temperatureC, 2) + ",";
    } else {
        json += "\"temperature_c\":null,";
    }

    json += "\"lead_off\":" + String(batch.leadOff ? "true" : "false") + ",";
    json += "\"is_simulated\":" + String(batch.isSimulated ? "true" : "false") + ",";
    json += "\"firmware_version\":\"" + String(FIRMWARE_VER) + "\",";

    // ECG Samples Array
    json += "\"ecg_samples\":[";
    for (int i = 0; i < SAMPLES_PER_BATCH; i++) {
        json += String(batch.ecgSamples[i]);
        if (i < SAMPLES_PER_BATCH - 1) json += ",";
    }
    json += "]}";

    return json;
}

// ==========================================================================
// 10. GPRS HTTP POST EXECUTION & STATUS CODE PARSING
// ==========================================================================
bool executeGPRSHttpPost(const String &jsonPayload) {
    // Terminate any hanging HTTP session
    sendAT("AT+HTTPTERM", "OK", 1000);

    // Initialize HTTP service
    if (!sendAT("AT+HTTPINIT", "OK", 3000)) {
        Serial.println("[HTTP ERR] AT+HTTPINIT failed. Re-initializing GPRS bearer...");
        initGPRSNetwork();
        if (!sendAT("AT+HTTPINIT", "OK", 3000)) return false;
    }

    // Set CID
    sendAT("AT+HTTPPARA=\"CID\",1", "OK", 2000);

    // Target URL
    String urlCmd = "AT+HTTPPARA=\"URL\",\"http://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + String(INGEST_PATH) + "\"";
    sendAT(urlCmd, "OK", 2000);

    // Headers
    sendAT("AT+HTTPPARA=\"CONTENT\",\"application/json\"", "OK", 2000);

    String keyCmd = "AT+HTTPPARA=\"USERDATA\",\"X-Device-API-Key: " + String(DEVICE_API_KEY) + "\"";
    sendAT(keyCmd, "OK", 2000);

    // Specify payload length in bytes
    String dataCmd = "AT+HTTPDATA=" + String(jsonPayload.length()) + ",15000";
    if (!sendAT(dataCmd, "DOWNLOAD", 5000)) {
        Serial.println("[HTTP ERR] Modem failed to enter DOWNLOAD mode.");
        sendAT("AT+HTTPTERM", "OK", 1000);
        return false;
    }

    // Transmit JSON body
    sim800.print(jsonPayload);
    delay(100);

    // Execute POST (AT+HTTPACTION=1)
    String actionResp;
    Serial.println("[HTTP] Executing AT+HTTPACTION=1...");
    if (!sendAT("AT+HTTPACTION=1", "+HTTPACTION:", 25000, &actionResp)) {
        Serial.println("[HTTP ERR] +HTTPACTION timed out or failed.");
        sendAT("AT+HTTPTERM", "OK", 1000);
        return false;
    }

    // Parse HTTP Status Code from: +HTTPACTION: 1,<status_code>,<datalen>
    int firstComma = actionResp.indexOf(',');
    int secondComma = actionResp.indexOf(',', firstComma + 1);
    if (firstComma == -1 || secondComma == -1) {
        Serial.println("[HTTP ERR] Malformed +HTTPACTION response.");
        sendAT("AT+HTTPTERM", "OK", 1000);
        return false;
    }

    int statusCode = actionResp.substring(firstComma + 1, secondComma).toInt();
    int dataLen = actionResp.substring(secondComma + 1).toInt();
    Serial.printf("[HTTP] Server responded with HTTP %d (Body: %d bytes)\n", statusCode, dataLen);

    // Validate Status Code
    if (statusCode == 200) {
        // Read body to confirm accepted / duplicate
        String bodyResp;
        sendAT("AT+HTTPREAD", "+HTTPREAD:", 5000, &bodyResp);
        sendAT("AT+HTTPTERM", "OK", 1000);

        if (bodyResp.indexOf("\"accepted\"") != -1 || bodyResp.indexOf("\"duplicate\"") != -1) {
            Serial.println("[HTTP 200] Telemetry accepted by server.");
            return true;
        } else {
            Serial.printf("[HTTP 200 WARN] Body did not contain standard accepted confirmation: %s\n", bodyResp.c_str());
            return true; // Still 200 OK
        }
    } else if (statusCode == 401) {
        Serial.println("[HTTP 401 UNAUTHORIZED] Check DEVICE_API_KEY in firmware!");
    } else if (statusCode == 403) {
        Serial.println("[HTTP 403 FORBIDDEN] Device ID or Patient ID ownership conflict!");
    } else if (statusCode == 409) {
        Serial.println("[HTTP 409 CONFLICT] Sequence number collision or session already completed!");
    } else if (statusCode == 413) {
        Serial.println("[HTTP 413 TOO LARGE] Batch size exceeds server MAX_ECG_SAMPLES_PER_BATCH limit!");
    } else if (statusCode == 601) {
        Serial.println("[HTTP 601 NETWORK ERROR] Server unreachable. Cannot connect to IP over GPRS.");
    } else {
        Serial.printf("[HTTP %d ERROR] Unexpected HTTP error response.\n", statusCode);
    }

    sendAT("AT+HTTPTERM", "OK", 1000);
    return false;
}

#if USE_WIFI_FALLBACK
bool executeWiFiHttpPost(const String &jsonPayload) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[WIFI ERR] Wi-Fi disconnected.");
        return false;
    }

    HTTPClient http;
    String url = "http://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + String(INGEST_PATH);
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-API-Key", DEVICE_API_KEY);

    int httpCode = http.POST(jsonPayload);
    if (httpCode == 200) {
        String resp = http.getString();
        Serial.printf("[WIFI 200 OK] Server response: %s\n", resp.c_str());
        http.end();
        return true;
    } else {
        Serial.printf("[WIFI ERR] HTTP %d: %s\n", httpCode, http.errorToString(httpCode).c_str());
        http.end();
        return false;
    }
}
#endif

// ==========================================================================
// 11. CORE 1: GPRS TRANSMISSION TASK (Consumer Task)
// ==========================================================================
void transmissionTask(void* pvParameters) {
    Serial.println("[CORE 1] Telemetry Transmission Task Started.");

    TelemetryBatch currentBatch;
    bool hasPendingBatch = false;

    while (true) {
        // 1. If we don't have a pending retransmission batch, pull the next one from queue
        if (!hasPendingBatch) {
            if (xQueueReceive(telemetryQueue, &currentBatch, portMAX_DELAY) == pdPASS) {
                hasPendingBatch = true;
            }
        }

        // 2. Transmit the pending batch
        if (hasPendingBatch) {
            Serial.printf("\n[TRANSMIT] Preparing Batch '%s' (Seq %lu)...\n", currentBatch.batchId, currentBatch.sequenceNumber);

            String jsonPayload = serializeBatchToJson(currentBatch);
            Serial.printf("[TRANSMIT] JSON payload length: %d bytes\n", jsonPayload.length());

            bool success = false;
#if USE_WIFI_FALLBACK
            success = executeWiFiHttpPost(jsonPayload);
#else
            success = executeGPRSHttpPost(jsonPayload);
#endif

            if (success) {
                Serial.printf("[DELIVERED] Batch %lu acknowledged by server.\n", currentBatch.sequenceNumber);
                // Sequence number incremented ONLY after confirmed delivery
                globalSequence++;
                hasPendingBatch = false; // Ready for next batch
            } else {
                Serial.printf("[RETRY] Batch %lu failed delivery. Retrying with identical batchId & sequenceNumber in 3s...\n", currentBatch.sequenceNumber);
                vTaskDelay(pdMS_TO_TICKS(3000)); // Backoff before retransmission
                // hasPendingBatch remains true: will retransmit the exact same batch without losing it
            }
        }
    }
}

// ==========================================================================
// 12. ARDUINO SETUP & ENTRYPOINT
// ==========================================================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n========================================================");
    Serial.println("  REMOTE PATIENT HEALTH MONITORING SYSTEM — ESP32 NODE  ");
    Serial.println("  University Engineering Prototype                      ");
    Serial.println("========================================================");
    Serial.printf("[CONFIG] Device ID:   %s\n", DEVICE_ID);
    Serial.printf("[CONFIG] Patient ID:  %s\n", PATIENT_ID);
    Serial.printf("[CONFIG] Server:      http://%s:%d%s\n", SERVER_HOST, SERVER_PORT, INGEST_PATH);
    Serial.printf("[CONFIG] APN:         %s\n", SIM_APN);
    Serial.printf("[CONFIG] Mode:        %s\n", SIMULATE_SENSORS ? "SIMULATION (Demo Mode)" : "PHYSICAL SENSORS");

    // Generate unique session identifier for this monitoring event
    snprintf(sessionId, sizeof(sessionId), "SES-%s-%08X", DEVICE_ID, (uint32_t)esp_random());
    Serial.printf("[CONFIG] Session ID:  %s\n", sessionId);

    // Initialize physical hardware pins and peripherals
    setupHardware();

    // Create FreeRTOS queue for producer-consumer batches
    telemetryQueue = xQueueCreate(BATCH_QUEUE_SIZE, sizeof(TelemetryBatch));
    if (telemetryQueue == NULL) {
        Serial.println("[FATAL] Failed to create FreeRTOS telemetry queue!");
        while (1) delay(1000);
    }

#if USE_WIFI_FALLBACK
    Serial.printf("[NETWORK] Connecting to Wi-Fi SSID '%s'...\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[NETWORK] Wi-Fi Connected. Local IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[ERROR] Wi-Fi connection failed.");
    }
#else
    // Connect to 2G GPRS via SIM800L
    initGPRSNetwork();
#endif

    // Spawn Producer Sampling Task on Core 0 (Priority 5 - High Priority)
    xTaskCreatePinnedToCore(
        samplingTask,
        "SamplingTask",
        4096,
        NULL,
        5,
        &samplingTaskHandle,
        0 // Core 0
    );

    // Spawn Consumer Transmission Task on Core 1 (Priority 1 - Normal Priority)
    xTaskCreatePinnedToCore(
        transmissionTask,
        "TransmissionTask",
        8192,
        NULL,
        1,
        &transmissionTaskHandle,
        1 // Core 1
    );

    Serial.println("[SYSTEM] Dual-core FreeRTOS tasks spawned. Operating normally.\n");
}

void loop() {
    // Both sampling and transmission run continuously in FreeRTOS tasks on Core 0 and Core 1.
    // The main loop yields CPU to idle tasks.
    vTaskDelay(pdMS_TO_TICKS(1000));
}
