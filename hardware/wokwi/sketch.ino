/*
  REMOTE PATIENT HEALTH MONITORING
  WOKWI ESP32 SIMULATION - VERSION 2.0 (PRESCRIPTION & TWO-WAY DIRECTIVES)

  Sensors:
  - Potentiometer GPIO34: Heart Rate
  - Potentiometer GPIO35: SpO2
  - DS18B20 GPIO4: Temperature
  - Synthetic ECG: 250 Hz

  Peripherals & Actuators:
  - 20x4 I2C LCD (0x27): SDA GPIO21, SCL GPIO22 (Patient Advice & Vitals)
  - Push Button NEXT: GPIO18 (Cycles 4-page Prescription)
  - Push Button CONFIRM: GPIO19 (Acknowledges Doctor Directive)

  Network:
  - Wokwi-GUEST Wi-Fi
  - ngrok HTTP tunnel
  - FastAPI backend

  Time:
  - NTP synchronization
  - UTC timestamps
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <time.h>
#include <math.h>

// ==========================================
// 1. WIFI SETTINGS
// ==========================================

#define WIFI_SSID "Wokwi-GUEST"
#define WIFI_PASSWORD ""

// ==========================================
// 2. SERVER & AUTH SETTINGS
// ==========================================

#define SERVER_BASE_URL "http://sculptor-chewer-buffer.ngrok-free.dev/api/v1"
#define INGEST_URL SERVER_BASE_URL "/ingest"

#define DEVICE_ID "ESP32-001"
#define PATIENT_ID "P001"

// Device API key for ESP32-001
#define DEVICE_API_KEY "rhm_80eedcd9eedb1f43_EnZ6ej9kDYl23pm0qLtnBqvpcdZgphdovZ3hSHHYgVc"

// ==========================================
// 3. HARDWARE PINS
// ==========================================

#define PIN_HR_POT 34
#define PIN_SPO2_POT 35
#define PIN_DS18B20 4

#define PIN_BTN_NEXT 18
#define PIN_BTN_CONFIRM 19

// ==========================================
// 4. ECG & BATCH SETTINGS
// ==========================================

#define SAMPLE_RATE_HZ 250
#define SAMPLES_PER_BATCH 250
#define TOTAL_BATCHES 5

#define FIRMWARE_VERSION "wokwi-sim-2.0"

// ==========================================
// 5. GLOBAL OBJECTS & STATE
// ==========================================

OneWire oneWire(PIN_DS18B20);
DallasTemperature tempSensor(&oneWire);
LiquidCrystal_I2C lcd(0x27, 20, 4);

String sessionId;
uint32_t sequenceNumber = 1;
bool timeSynchronized = false;
bool batchUploadsCompleted = false;

// Doctor Prescription Data Structure
struct PrescriptionData {
  bool active = false;
  int id = 0;
  String assessment = "";
  String medication = "";
  String dosage = "";
  String frequency = "";
  String duration = "";
  String instructions = "";
  String followUp = "";
};

PrescriptionData currentRx;
int rxPage = 1; // 1 to 4

enum LCDMode {
  LCD_MODE_VITALS,
  LCD_MODE_PRESCRIPTION,
  LCD_MODE_ACKNOWLEDGED
};

LCDMode lcdMode = LCD_MODE_VITALS;
unsigned long ackDisplayStartTime = 0;
unsigned long lastInboxCheckTime = 0;
const unsigned long INBOX_CHECK_INTERVAL_MS = 15000; // Check inbox every 15s

// Button debounce tracking
unsigned long lastNextPress = 0;
unsigned long lastConfirmPress = 0;
const unsigned long DEBOUNCE_DELAY_MS = 300;

// ==========================================
// 6. ECG GENERATION
// ==========================================

float gaussian(float x, float center, float width) {
  float z = (x - center) / width;
  return expf(-0.5f * z * z);
}

int syntheticEcgSample(uint32_t sampleIndex, float bpm) {
  float seconds = sampleIndex / (float)SAMPLE_RATE_HZ;
  float period = 60.0f / bpm;
  float phase = fmodf(seconds, period) / period;
  float y = 2048.0f;

  // P wave
  y += 95.0f * gaussian(phase, 0.18f, 0.025f);
  // Q wave
  y -= 120.0f * gaussian(phase, 0.37f, 0.012f);
  // R wave
  y += 900.0f * gaussian(phase, 0.40f, 0.010f);
  // S wave
  y -= 220.0f * gaussian(phase, 0.43f, 0.014f);
  // T wave
  y += 260.0f * gaussian(phase, 0.68f, 0.055f);
  // Baseline wander
  y += 12.0f * sinf(2.0f * PI * 0.25f * seconds);

  return constrain((int)lroundf(y), 0, 4095);
}

// ==========================================
// 7. TIME SYNCHRONIZATION
// ==========================================

bool synchronizeTime() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi unavailable. Cannot synchronize time.");
    return false;
  }

  Serial.println();
  Serial.println("Synchronizing UTC time using NTP...");
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");

  struct tm timeinfo;
  for (int attempt = 1; attempt <= 30; attempt++) {
    if (getLocalTime(&timeinfo, 500)) {
      int year = timeinfo.tm_year + 1900;
      if (year >= 2026) {
        Serial.println("NTP time synchronized!");
        Serial.printf(
          "UTC date/time: %04d-%02d-%02d %02d:%02d:%02d\n",
          year,
          timeinfo.tm_mon + 1,
          timeinfo.tm_mday,
          timeinfo.tm_hour,
          timeinfo.tm_min,
          timeinfo.tm_sec
        );
        timeSynchronized = true;
        return true;
      }
    }
    Serial.print(".");
    delay(500);
  }

  Serial.println();
  Serial.println("NTP synchronization not completed.");
  timeSynchronized = false;
  return false;
}

String utcTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 1000)) {
    return "";
  }
  char buffer[25];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buffer);
}

// ==========================================
// 8. WIFI CONNECTION
// ==========================================

bool connectWiFi() {
  Serial.println();
  Serial.println("Connecting to Wokwi Wi-Fi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 60) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Wi-Fi connected!");
    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());
    return true;
  }

  Serial.println("Wi-Fi connection failed!");
  return false;
}

// ==========================================
// 9. SENSOR ACQUISITION
// ==========================================

float readHeartRate() {
  int raw = analogRead(PIN_HR_POT);
  return 50.0f + (raw / 4095.0f) * 80.0f;
}

float readSpO2() {
  int raw = analogRead(PIN_SPO2_POT);
  return 85.0f + (raw / 4095.0f) * 15.0f;
}

float readTemperature() {
  tempSensor.requestTemperatures();
  float value = tempSensor.getTempCByIndex(0);
  if (value == DEVICE_DISCONNECTED_C || value < -50 || value > 100) {
    return NAN;
  }
  return value;
}

// ==========================================
// 10. LCD RENDERING SYSTEM
// ==========================================

void printLCDLine(int row, String text) {
  lcd.setCursor(0, row);
  if (text.length() > 20) {
    text = text.substring(0, 20);
  }
  while (text.length() < 20) {
    text += " ";
  }
  lcd.print(text);
}

void renderLCD(float bpm, float spo2, float temp) {
  if (lcdMode == LCD_MODE_ACKNOWLEDGED) {
    printLCDLine(0, "********************");
    printLCDLine(1, "  PRESCRIPTION ACK  ");
    printLCDLine(2, "SENT TO DOCTOR DASH ");
    printLCDLine(3, "********************");
    return;
  }

  if (lcdMode == LCD_MODE_PRESCRIPTION && currentRx.active) {
    if (rxPage == 1) {
      printLCDLine(0, "* DOCTOR ADVICE 1/4 *");
      printLCDLine(1, "Pt: " + String(PATIENT_ID));
      printLCDLine(2, "Rx: " + currentRx.assessment);
      printLCDLine(3, "[NEXT:Pg  CONF:Ack]");
    } else if (rxPage == 2) {
      printLCDLine(0, "* MEDICINE 2/4 *");
      printLCDLine(1, "Med: " + currentRx.medication);
      printLCDLine(2, "Dosage: " + currentRx.dosage);
      printLCDLine(3, "[NEXT:Pg  CONF:Ack]");
    } else if (rxPage == 3) {
      printLCDLine(0, "* SCHEDULE 3/4 *");
      printLCDLine(1, "Freq: " + currentRx.frequency);
      printLCDLine(2, "Dur: " + currentRx.duration);
      printLCDLine(3, "[NEXT:Pg  CONF:Ack]");
    } else if (rxPage == 4) {
      printLCDLine(0, "* DIRECTIVE 4/4 *");
      printLCDLine(1, "Ins:" + currentRx.instructions.substring(0, 16));
      printLCDLine(2, "F/U:" + (currentRx.followUp.length() > 0 ? currentRx.followUp : "As scheduled"));
      printLCDLine(3, "PRESS CONFIRM TO ACK");
    }
    return;
  }

  // Default: LCD_MODE_VITALS
  printLCDLine(0, "* RURAL HEALTH MON *");

  char line1[21];
  snprintf(line1, sizeof(line1), "HR:%3.0f bpm SpO2:%2.0f%%", bpm, spo2);
  printLCDLine(1, String(line1));

  char line2[21];
  if (isnan(temp)) {
    snprintf(line2, sizeof(line2), "Temp: Disconnected");
  } else {
    snprintf(line2, sizeof(line2), "Temp: %4.1f C (OK)", temp);
  }
  printLCDLine(2, String(line2));

  if (currentRx.active) {
    printLCDLine(3, "Rx: NEW! Press NEXT");
  } else {
    printLCDLine(3, "Rx: No new directive");
  }
}

// ==========================================
// 11. INBOX POLLING & ACKNOWLEDGEMENT
// ==========================================

void checkInbox(float bpm, float spo2, float temp) {
  if (WiFi.status() != WL_CONNECTED) return;

  String inboxUrl = String(SERVER_BASE_URL) + "/devices/" + String(DEVICE_ID) + "/inbox";

  HTTPClient http;
  http.setTimeout(8000);

  if (!http.begin(inboxUrl)) {
    Serial.println("[INBOX] HTTP connection failed.");
    return;
  }

  http.addHeader("X-Device-API-Key", DEVICE_API_KEY);
  int code = http.GET();

  if (code == 200) {
    String payload = http.getString();
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload);

    if (!err) {
      JsonArray messages = doc["messages"].as<JsonArray>();
      if (messages.size() > 0) {
        JsonObject msg = messages[0];
        int msgId = msg["id"];

        // If this is a new prescription or previously unacknowledged
        if (!currentRx.active || currentRx.id != msgId) {
          currentRx.id = msgId;
          currentRx.assessment = msg["assessment"] | "";
          currentRx.medication = msg["medication"] | "";
          currentRx.dosage = msg["dosage"] | "";
          currentRx.frequency = msg["frequency"] | "";
          currentRx.duration = msg["duration"] | "";
          currentRx.instructions = msg["instructions"] | "";
          currentRx.followUp = msg["follow_up_date"] | "";
          currentRx.active = true;

          rxPage = 1;
          lcdMode = LCD_MODE_PRESCRIPTION;

          Serial.println();
          Serial.println("==================================================");
          Serial.printf(">>> [INBOX] NEW DOCTOR PRESCRIPTION RECEIVED (#%d) <<<\n", msgId);
          Serial.printf("Assessment: %s\n", currentRx.assessment.c_str());
          Serial.printf("Medication: %s (%s)\n", currentRx.medication.c_str(), currentRx.dosage.c_str());
          Serial.printf("Schedule:   %s, Duration: %s\n", currentRx.frequency.c_str(), currentRx.duration.c_str());
          Serial.printf("Directive delivered to 20x4 LCD display.\n");
          Serial.println("==================================================");

          renderLCD(bpm, spo2, temp);
        }
      }
    }
  } else {
    Serial.printf("[INBOX] Poll status: %d\n", code);
  }

  http.end();
}

void sendAcknowledgement(float bpm, float spo2, float temp) {
  if (!currentRx.active || WiFi.status() != WL_CONNECTED) return;

  String ackUrl = String(SERVER_BASE_URL) + "/devices/" + String(DEVICE_ID) + "/acknowledge";

  HTTPClient http;
  http.setTimeout(8000);

  if (!http.begin(ackUrl)) {
    Serial.println("[ACK] Connection failed.");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-API-Key", DEVICE_API_KEY);

  JsonDocument doc;
  doc["prescription_id"] = currentRx.id;
  String payload;
  serializeJson(doc, payload);

  Serial.printf("[ACK] Transmitting confirmation for Prescription #%d to server...\n", currentRx.id);
  int code = http.POST(payload);
  String response = http.getString();
  http.end();

  Serial.printf("[ACK] HTTP Response: %d\n", code);
  if (code == 200) {
    Serial.println(">>> [ACK] Prescription acknowledged and recorded in Doctor Dashboard! <<<");
    currentRx.active = false;
    lcdMode = LCD_MODE_ACKNOWLEDGED;
    ackDisplayStartTime = millis();
    renderLCD(bpm, spo2, temp);
  } else {
    Serial.printf("[ACK] Server rejected confirmation: %s\n", response.c_str());
  }
}

// ==========================================
// 12. SEND ECG BATCH
// ==========================================

bool sendBatch(float bpm, float spo2, float temperature) {
  if (WiFi.status() != WL_CONNECTED) {
    if (!connectWiFi()) return false;
  }

  if (!timeSynchronized) {
    if (!synchronizeTime()) {
      Serial.println("Waiting for valid UTC time before upload.");
      return false;
    }
  }

  String timestamp = utcTimestamp();
  if (timestamp.length() == 0) {
    Serial.println("Invalid timestamp. Upload cancelled.");
    timeSynchronized = false;
    return false;
  }

  JsonDocument doc;
  String batchId = DEVICE_ID + String("-") + sessionId + String("-B") + String(sequenceNumber);

  doc["device_id"] = DEVICE_ID;
  doc["patient_id"] = PATIENT_ID;
  doc["session_id"] = sessionId;
  doc["batch_id"] = batchId;
  doc["sequence_number"] = sequenceNumber;
  doc["recorded_at"] = timestamp;
  doc["ecg_sampling_rate_hz"] = SAMPLE_RATE_HZ;
  doc["ecg_unit"] = "adc_counts";

  JsonArray samples = doc["ecg_samples"].to<JsonArray>();
  uint32_t firstSample = (sequenceNumber - 1) * SAMPLES_PER_BATCH;

  for (int i = 0; i < SAMPLES_PER_BATCH; i++) {
    samples.add(syntheticEcgSample(firstSample + i, bpm));
  }

  doc["heart_rate_bpm"] = bpm;
  doc["spo2_percent"] = spo2;

  if (isnan(temperature)) {
    doc["temperature_c"] = nullptr;
  } else {
    doc["temperature_c"] = temperature;
  }

  doc["lead_off"] = false;
  doc["is_simulated"] = true;
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["is_session_end"] = (sequenceNumber == TOTAL_BATCHES);

  String payload;
  serializeJson(doc, payload);

  Serial.println();
  Serial.printf("Uploading batch %lu/%d\n", (unsigned long)sequenceNumber, TOTAL_BATCHES);
  Serial.print("Recording timestamp: ");
  Serial.println(timestamp);
  Serial.printf("ECG samples: %d | Payload: %u bytes\n", SAMPLES_PER_BATCH, payload.length());

  HTTPClient http;
  http.setTimeout(15000);

  if (!http.begin(INGEST_URL)) {
    Serial.println("HTTP initialization failed!");
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-API-Key", DEVICE_API_KEY);

  int responseCode = http.POST(payload);
  String response = http.getString();
  http.end();

  Serial.printf("HTTP Status: %d\n", responseCode);
  Serial.println("Server response:");
  Serial.println(response);

  if (responseCode >= 200 && responseCode < 300) {
    JsonDocument reply;
    if (!deserializeJson(reply, response)) {
      String status = reply["status"] | "";
      if (status == "accepted" || status == "duplicate") {
        Serial.println("Batch accepted!");
        return true;
      }
    }
  }

  Serial.println("Upload not acknowledged.");
  return false;
}

// ==========================================
// 13. SETUP
// ==========================================

void setup() {
  Serial.begin(115200);

  analogReadResolution(12);

  pinMode(PIN_HR_POT, INPUT);
  pinMode(PIN_SPO2_POT, INPUT);

  pinMode(PIN_BTN_NEXT, INPUT_PULLUP);
  pinMode(PIN_BTN_CONFIRM, INPUT_PULLUP);

  tempSensor.begin();

  // Initialize 20x4 I2C LCD
  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  printLCDLine(0, "RURAL HEALTH MONITOR");
  printLCDLine(1, "Dev: " DEVICE_ID);
  printLCDLine(2, "Initializing Wi-Fi..");
  printLCDLine(3, "Firmware: " FIRMWARE_VERSION);

  sessionId = "WOKWI-" + String((uint32_t)(ESP.getEfuseMac() & 0xFFFFFFFF), HEX) + "-" + String(millis());

  Serial.println();
  Serial.println("================================================");
  Serial.println("REMOTE PATIENT HEALTH MONITORING - FIRMWARE v2.0");
  Serial.println("Two-Way Doctor-to-Patient LCD Prescription Directives");
  Serial.println("================================================");
  Serial.print("Session ID: ");
  Serial.println(sessionId);

  if (connectWiFi()) {
    synchronizeTime();
  } else {
    Serial.println("Time synchronization postponed.");
  }

  printLCDLine(2, "Wi-Fi Connected!   ");
  delay(1200);

  Serial.println();
  Serial.println("System initialized. Entering main operational loop.");
}

// ==========================================
// 14. MAIN LOOP
// ==========================================

void loop() {
  float bpm = readHeartRate();
  float spo2 = readSpO2();
  float temperature = readTemperature();

  // --- 1. Acknowledged State Timeout (revert to vitals after 3.5s) ---
  if (lcdMode == LCD_MODE_ACKNOWLEDGED) {
    if (millis() - ackDisplayStartTime > 3500) {
      lcdMode = LCD_MODE_VITALS;
      renderLCD(bpm, spo2, temperature);
    }
  }

  // --- 2. Check Push Buttons ---
  unsigned long now = millis();

  // NEXT Button (Cycle Prescription Pages)
  if (digitalRead(PIN_BTN_NEXT) == LOW && (now - lastNextPress > DEBOUNCE_DELAY_MS)) {
    lastNextPress = now;
    if (currentRx.active) {
      lcdMode = LCD_MODE_PRESCRIPTION;
      rxPage = (rxPage % 4) + 1;
      Serial.printf("[BUTTON] NEXT -> Viewing Prescription Page %d/4\n", rxPage);
      renderLCD(bpm, spo2, temperature);
    } else {
      Serial.println("[BUTTON] NEXT pressed (No active prescription).");
    }
  }

  // CONFIRM Button (Acknowledge Doctor Prescription)
  if (digitalRead(PIN_BTN_CONFIRM) == LOW && (now - lastConfirmPress > DEBOUNCE_DELAY_MS)) {
    lastConfirmPress = now;
    if (currentRx.active) {
      Serial.println("[BUTTON] CONFIRM pressed -> Acknowledging Doctor Prescription...");
      sendAcknowledgement(bpm, spo2, temperature);
    } else {
      Serial.println("[BUTTON] CONFIRM pressed (No active prescription).");
    }
  }

  // --- 3. Periodic Inbox Check (Every 15s) ---
  if (now - lastInboxCheckTime >= INBOX_CHECK_INTERVAL_MS) {
    lastInboxCheckTime = now;
    checkInbox(bpm, spo2, temperature);
  }

  // --- 4. Render LCD ---
  renderLCD(bpm, spo2, temperature);

  // --- 5. Upload ECG Batches (First 5 Batches) ---
  if (!batchUploadsCompleted) {
    if (sequenceNumber <= TOTAL_BATCHES) {
      Serial.println();
      Serial.println("--------- PATIENT VITALS ---------");
      Serial.printf("Heart Rate: %.1f BPM\n", bpm);
      Serial.printf("SpO2: %.1f %%\n", spo2);
      if (isnan(temperature)) {
        Serial.println("Temperature: unavailable");
      } else {
        Serial.printf("Temperature: %.2f C\n", temperature);
      }
      Serial.println("----------------------------------");

      bool success = sendBatch(bpm, spo2, temperature);
      if (success) {
        sequenceNumber++;
      } else {
        Serial.println("Batch not accepted. Will retry.");
      }
    } else {
      batchUploadsCompleted = true;
      Serial.println();
      Serial.println("==================================================");
      Serial.println("ALL FIVE ECG BATCHES COMPLETED & STORED IN CLOUD");
      Serial.println("CONTINUING CONTINUOUS SENSOR MONITORING & INBOX POLLING");
      Serial.println("==================================================");
    }
  }

  delay(200);
}
