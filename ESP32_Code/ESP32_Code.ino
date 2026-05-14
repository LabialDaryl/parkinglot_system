// =============================================================================
//  SMART PARKING LOT SYSTEM — ESP32 Firmware (Dual-Core)
//  Target board : ESP32 Dev Module (Arduino IDE)
//
//  Architecture:
//    Core 1 (Arduino loop) — Sensors, LCD, Servos  (runs every ~20ms, NEVER blocks)
//    Core 0 (FreeRTOS task) — HTTP communication   (runs in background, can block)
//
//  Hardware
//  ─────────────────────────────────────────────────────────────────────────────
//  LCD 20×4 I2C          : SDA=21, SCL=22  (address 0x27)
//  Entrance servo        : Pin 25  (0° = closed, 90° = open)
//  Exit servo            : Pin 26  (0° = closed, 90° = open)
//  Entrance IR sensor    : Pin 18  (LOW when car detected)
//  Exit IR sensor        : Pin 19  (LOW when car detected)
//  8× Slot IR sensors    : Pins 34,35,36,39,32,33,27,14  (LOW = occupied)
//
//  LCD Display Format (20×4):
//  ─────────────────────────────────────────────────────────────────────────
//  Row 0: "PARKING  [ONLINE ]"   or "PARKING  [OFFLINE]" (network status)
//  Row 1: "Free:6   Rsvd:1"                               (available slots)
//  Row 2: "Occ:1  S:OOXOOOO"                            (occupancy map: O=free, X=occupied)
//  Row 3: "IN:OPEN  OUT:CLOSED"                           (gate status)
//
//  Data Synchronization (when ONLINE):
//  ─────────────────────────────────────────────────────────────────────────
//  1. Core 1 (loop): Reads all 8 IR sensors → updates currentSlotOccupied[]
//  2. Core 1: Updates LCD immediately with sensor data every 300ms or on change
//  3. Core 0 (httpTask): Every 5 seconds:
//     a. Fetches latest slot status from server → updates webReservedCount
//     b. If sensors changed, bulk-syncs to server → server updates database
//     c. Fetches updated server state back
//  4. LCD displays ONLINE status when server responds successfully
//  5. Website polls /api/v1/slots/stats/ every 4 seconds → shows same data
//
//  Required Libraries (install via Library Manager)
//  ─────────────────────────────────────────────────────────────────────────────
//  ArduinoJson      >= 6.x
//  ESP32Servo       (by Kevin Harrington)
//  LiquidCrystal_I2C (by Frank de Brabander)
// =============================================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// =============================================================================
//  USER CONFIGURATION
// =============================================================================
const char* WIFI_SSID        = "PLDTHOMEFIBRdJDaC";
const char* WIFI_PASSWORD    = "PLDTWIFI7ATcY";
const char* SERVER_BASE_URL  = "https://parkinglot-system.onrender.com";

// =============================================================================
//  PIN MAP
// =============================================================================
LiquidCrystal_I2C lcd(0x27, 20, 4);

const int PIN_SERVO_ENTRANCE = 25;
const int PIN_SERVO_EXIT     = 26;
const int PIN_IR_ENTRANCE    = 18;
const int PIN_IR_EXIT        = 19;
const int NUM_SLOTS          = 8;
const int IR_SLOT_PINS[NUM_SLOTS] = {34, 35, 36, 39, 32, 33, 27, 14};
const int DB_SLOT_IDS[NUM_SLOTS]  = {1, 2, 3, 4, 5, 6, 7, 8};

// =============================================================================
//  SERVO & GATE
// =============================================================================
Servo entranceServo;
Servo exitServo;

const int  SERVO_CLOSED_DEG  = 0;
const int  SERVO_OPEN_DEG    = 90;

// Debounce delay: how long the sensor must hold its state before acting
const unsigned long GATE_DEBOUNCE_MS = 2000;  // 2 seconds

// 4-state gate machine:
//   CLOSED          → sensor detects object   → WAITING_TO_OPEN (start 2s timer)
//   WAITING_TO_OPEN → 2s elapsed              → OPEN (servo opens)
//   WAITING_TO_OPEN → object removed early    → CLOSED (cancel)
//   OPEN            → object removed          → WAITING_TO_CLOSE (start 2s timer)
//   WAITING_TO_CLOSE→ 2s elapsed              → CLOSED (servo closes)
//   WAITING_TO_CLOSE→ object re-detected      → OPEN (cancel close)
enum GateState { GATE_CLOSED, GATE_OPEN };
struct Gate {
  Servo*        servo;
  GateState     state      = GATE_CLOSED;
  unsigned long timerStart = 0;  // when debounce timer started (0 = inactive)
};
Gate entranceGate;
Gate exitGate;

// =============================================================================
//  SHARED STATE (accessed by both cores — use volatile)
//
//  Core 1 (loop) WRITES:  currentSlotOccupied[], needsSync
//  Core 0 (HTTP) READS:   currentSlotOccupied[], needsSync
//  Core 0 (HTTP) WRITES:  webOnline, webReservedCount, serverKnowsOccupied[]
//  Core 1 (loop) READS:   webOnline, webReservedCount
// =============================================================================
volatile bool currentSlotOccupied[NUM_SLOTS] = {};
volatile bool serverKnowsOccupied[NUM_SLOTS] = {};
volatile bool webOnline        = false;
volatile int  webReservedCount = 0;
volatile bool needsSync        = false;  // flag for Core 0 to sync

bool prevEntranceTriggered = false;
bool prevExitTriggered     = false;

// =============================================================================
//  TIMING
// =============================================================================
const unsigned long LCD_REFRESH_MS = 300;    // refresh LCD every 300ms
unsigned long lastLcdRefreshMs     = 0;

// =============================================================================
//  FORWARD DECLARATIONS
// =============================================================================
void updateLCD();
void updateLcdRow3();
void lcdPrintPadded(int col, int row, const char* str, int width);

// =============================================================================
//  GATE LOGIC — debounced 4-state machine (non-blocking)
// =============================================================================
void updateGate(Gate& gate, bool objectDetected, const char* label) {
  unsigned long now = millis();

  switch (gate.state) {

    case GATE_CLOSED:
      if (objectDetected) {
        // Start counting how long the object has been present
        if (gate.timerStart == 0) {
          gate.timerStart = now;
        }
        // Object present for 2s continuously → open
        if (now - gate.timerStart >= GATE_DEBOUNCE_MS) {
          gate.servo->write(SERVO_OPEN_DEG);
          gate.state = GATE_OPEN;
          gate.timerStart = 0;
          Serial.printf("[Gate] %s OPEN\n", label);
          updateLcdRow3();
        }
      } else {
        gate.timerStart = 0;  // reset if object disappears
      }
      break;

    case GATE_OPEN:
      if (!objectDetected) {
        // Start counting how long the object has been gone
        if (gate.timerStart == 0) {
          gate.timerStart = now;
        }
        // No object for 2s continuously → close
        if (now - gate.timerStart >= GATE_DEBOUNCE_MS) {
          gate.servo->write(SERVO_CLOSED_DEG);
          gate.state = GATE_CLOSED;
          gate.timerStart = 0;
          Serial.printf("[Gate] %s CLOSED\n", label);
          updateLcdRow3();
        }
      } else {
        gate.timerStart = 0;  // reset if object reappears
      }
      break;

    default:
      gate.state = GATE_CLOSED;
      break;
  }
}

// =============================================================================
//  LCD RENDERING (Core 1 only)
//
//  Row 0: "PARKING  [ONLINE ]" or "PARKING  [OFFLINE]"
//  Row 1: "Free:6   Rsvd:0"
//  Row 2: "Occ:2  S:OOXOOOOO"
//  Row 3: Gate status
// =============================================================================
void lcdPrintPadded(int col, int row, const char* str, int width) {
  lcd.setCursor(col, row);
  int len = strlen(str);
  lcd.print(str);
  for (int i = len; i < width; i++) lcd.print(' ');
}

void updateLcdRow3() {
  bool eOpen = (entranceGate.state == GATE_OPEN);
  bool xOpen = (exitGate.state    == GATE_OPEN);
  char buf[21];
  if      (eOpen && xOpen) snprintf(buf, 21, "IN:OPEN  OUT:OPEN");
  else if (eOpen)          snprintf(buf, 21, "IN:OPEN  OUT:CLOSED");
  else if (xOpen)          snprintf(buf, 21, "IN:CLOSED OUT:OPEN");
  else                     snprintf(buf, 21, "Gates: CLOSED");
  lcdPrintPadded(0, 3, buf, 20);
}

void updateLCD() {
  // ── Count occupied slots from physical sensors ──
  int occupied = 0;
  char slotMap[NUM_SLOTS + 1];
  
  for (int i = 0; i < NUM_SLOTS; i++) {
    // Always read fresh from the volatile array (sensors update this in real-time)
    bool occ = (bool)currentSlotOccupied[i];
    if (occ) occupied++;
    slotMap[i] = occ ? 'X' : 'O';
  }
  slotMap[NUM_SLOTS] = '\0';

  // ── Calculate free slots (total - occupied - reserved) ──
  int reserved = (int)webReservedCount;  // From server
  int free = NUM_SLOTS - occupied - reserved;
  if (free < 0) free = 0;

  char buf[21];

  // ── Row 0: System Status ──
  // Shows "PARKING  [ONLINE ]" or "PARKING  [OFFLINE]"
  snprintf(buf, 21, "PARKING  [%s]", webOnline ? "ONLINE " : "OFFLINE");
  lcdPrintPadded(0, 0, buf, 20);

  // ── Row 1: Availability ──
  // Shows "Free:XX   Rsvd:XX"
  snprintf(buf, 21, "Free:%-2d  Rsvd:%-2d", free, reserved);
  lcdPrintPadded(0, 1, buf, 20);

  // ── Row 2: Occupancy Map ──
  // Shows "Occ:XX S:XXXXXXXX" where X=occupied, O=free
  snprintf(buf, 21, "Occ:%-2d S:%s", occupied, slotMap);
  lcdPrintPadded(0, 2, buf, 20);

  // ── Row 3: Gate Status (managed by updateLcdRow3) ──
  // Already updated separately in gate state machine
}

// =============================================================================
//  SENSOR READING (Core 1 only — instant digitalRead, no blocking)
// =============================================================================

bool readSlotSensors() {
  bool changed = false;
  for (int i = 0; i < NUM_SLOTS; i++) {
    // Read physical pin state: LOW = occupied, HIGH = free
    bool occ = (digitalRead(IR_SLOT_PINS[i]) == LOW);
    
    // Check if state differs from last known state
    if (occ != (bool)currentSlotOccupied[i]) {
      currentSlotOccupied[i] = occ;
      changed = true;
      
      // Log the change
      Serial.printf("[Sensor] Slot %d -> %s (Physical: %s)\n", 
                    DB_SLOT_IDS[i],
                    occ ? "OCCUPIED" : "FREE",
                    occ ? "Car detected" : "Slot empty");
    }
  }
  
  // If any sensor changed, mark for server sync
  if (changed) {
    needsSync = true;
    Serial.println("[Sensor] Change detected - will sync to server");
  }
  
  return changed;
}

void readGateSensors() {
  bool ent = (digitalRead(PIN_IR_ENTRANCE) == LOW);
  bool ext = (digitalRead(PIN_IR_EXIT)     == LOW);

  updateGate(entranceGate, ent, "ENTRANCE");
  updateGate(exitGate,     ext, "EXIT");
}

// =============================================================================
//  HTTP TASK — runs on Core 0 in a FreeRTOS task
//  This is the ONLY place that does network I/O.
//  It can block for 5-10 seconds on SSL handshake without affecting sensors.
// =============================================================================

WiFiClientSecure makeSecureClient() {
  WiFiClientSecure c;
  c.setInsecure();
  return c;
}

void fetchStatusFromServer() {
  WiFiClientSecure client = makeSecureClient();
  HTTPClient http;

  String url = String(SERVER_BASE_URL) + "/api/v1/slots/";
  http.begin(client, url);
  http.setTimeout(10000);  // Can be long — runs on separate core

  int code = http.GET();
  if (code != 200) {
    Serial.printf("[Fetch] GET /api/v1/slots/ -> HTTP %d (OFFLINE)\n", code);
    webOnline = false;
    http.end();
    return;
  }

  webOnline = true;
  String payload = http.getString();
  http.end();

  DynamicJsonDocument doc(4096);
  DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    Serial.printf("[Fetch] JSON parse error: %s\n", err.f_str());
    return;
  }

  int cntReserved = 0;
  int cntOccupied = 0;
  JsonArray slots;
  if (doc.containsKey("results"))
    slots = doc["results"].as<JsonArray>();
  else
    slots = doc.as<JsonArray>();

  for (JsonObject slot : slots) {
    int    id     = slot["id"]     | 0;
    String status = slot["status"] | "unknown";
    
    if (status == "reserved") cntReserved++;
    if (status == "occupied") cntOccupied++;

    // Update server-known occupancy for comparison with physical sensors
    for (int i = 0; i < NUM_SLOTS; i++) {
      if (DB_SLOT_IDS[i] == id) {
        serverKnowsOccupied[i] = (status == "occupied");
      }
    }
  }

  webReservedCount = cntReserved;
  Serial.printf("[Fetch] ONLINE - Reserved:%d, Occupied:%d, Total:%d\n", 
                cntReserved, cntOccupied, slots.size());
}

// Bulk-sync all changed slots in a SINGLE HTTP call
void bulkSyncToServer() {
  // Build the list of slots that are out of sync
  DynamicJsonDocument doc(1024);
  JsonArray arr = doc.createNestedArray("slots");
  bool anyDiff = false;

  for (int i = 0; i < NUM_SLOTS; i++) {
    bool physical = (bool)currentSlotOccupied[i];
    bool serverKnows = (bool)serverKnowsOccupied[i];
    
    // If physical state differs from server's knowledge, sync it
    if (physical != serverKnows) {
      JsonObject entry = arr.createNestedObject();
      entry["id"]     = DB_SLOT_IDS[i];
      entry["status"] = physical ? "occupied" : "free";
      anyDiff = true;
      Serial.printf("[Sync] Slot %d -> %s\n", DB_SLOT_IDS[i], physical ? "occupied" : "free");
    }
  }

  if (!anyDiff) {
    Serial.println("[Sync] All slots in sync with server");
    return;
  }

  WiFiClientSecure client = makeSecureClient();
  HTTPClient http;

  String url = String(SERVER_BASE_URL) + "/api/v1/slots/bulk-update/";
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000);

  String body;
  serializeJson(doc, body);
  Serial.printf("[HTTP] POST bulk-update: %s\n", body.c_str());

  int code = http.POST(body);
  if (code == 200) {
    // Mark all synced after successful update
    for (int i = 0; i < NUM_SLOTS; i++) {
      serverKnowsOccupied[i] = currentSlotOccupied[i];
    }
    Serial.println("[Sync] Bulk update successful - all slots synced");
  } else {
    Serial.printf("[Sync] Bulk update FAILED (HTTP %d) - will retry next cycle\n", code);
  }
  http.end();
}

// The FreeRTOS task function that runs on Core 0
// Handles all network communication to keep it off the sensor-reading core
void httpTask(void* parameter) {
  const unsigned long POLL_INTERVAL = 5000;  // 5 seconds between server polls

  // Wait for WiFi before starting
  while (WiFi.status() != WL_CONNECTED) {
    vTaskDelay(500 / portTICK_PERIOD_MS);
  }

  Serial.println("[HTTP] Core 0 task started - ready to sync with server");

  for (;;) {
    if (WiFi.status() == WL_CONNECTED) {
      // ── 1. Fetch latest status from server ──
      // This updates webReservedCount and serverKnowsOccupied[]
      fetchStatusFromServer();

      // ── 2. Sync any sensor-detected changes to server ──
      // If a sensor detected a change since last poll, send it
      if (needsSync) {
        needsSync = false;
        bulkSyncToServer();
      }
    } else {
      webOnline = false;
      Serial.println("[WiFi] Disconnected, attempting reconnect...");
      WiFi.reconnect();
    }

    // Wait before next cycle (this delay does NOT affect Core 1 sensor reads)
    vTaskDelay(POLL_INTERVAL / portTICK_PERIOD_MS);
  }
}

// =============================================================================
//  SETUP
// =============================================================================
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n[Boot] Smart Parking System (Dual-Core) starting...");

  // -- Slot IR sensor pins --
  for (int i = 0; i < NUM_SLOTS; i++) {
    pinMode(IR_SLOT_PINS[i], INPUT);
    currentSlotOccupied[i] = (digitalRead(IR_SLOT_PINS[i]) == LOW);
  }

  // -- Gate IR sensor pins --
  pinMode(PIN_IR_ENTRANCE, INPUT);
  pinMode(PIN_IR_EXIT,     INPUT);

  // -- LCD --
  Wire.begin();
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Smart Parking v2.0  ");
  lcd.setCursor(0, 1);
  lcd.print("Dual-Core Mode      ");

  // -- Servos --
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  entranceServo.setPeriodHertz(50);
  exitServo.setPeriodHertz(50);
  entranceServo.attach(PIN_SERVO_ENTRANCE, 500, 2400);
  exitServo.attach(PIN_SERVO_EXIT,         500, 2400);
  entranceServo.write(SERVO_CLOSED_DEG);
  exitServo.write(SERVO_CLOSED_DEG);

  entranceGate.servo  = &entranceServo;
  exitGate.servo      = &exitServo;

  // -- WiFi --
  lcd.setCursor(0, 2);
  lcd.print("Connecting WiFi...  ");
  Serial.printf("[WiFi] Connecting to %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(300);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WiFi] IP: ");
    Serial.println(WiFi.localIP());
    lcd.setCursor(0, 2);
    lcd.print("WiFi OK             ");
    lcd.setCursor(0, 3);
    lcd.print(WiFi.localIP());
    delay(1500);
  } else {
    Serial.println("[WiFi] FAILED — running offline");
    lcd.setCursor(0, 2);
    lcd.print("WiFi: FAILED        ");
    lcd.setCursor(0, 3);
    lcd.print("Running offline     ");
    delay(1500);
  }

  // -- Launch HTTP task on Core 0 --
  xTaskCreatePinnedToCore(
    httpTask,     // task function
    "httpTask",   // name
    8192,         // stack size (bytes)
    NULL,         // parameter
    1,            // priority
    NULL,         // task handle
    0             // Core 0
  );
  Serial.println("[Boot] HTTP task launched on Core 0");

  // Show initial dashboard
  lcd.clear();
  updateLCD();
  updateLcdRow3();
  Serial.println("[Boot] Ready! Sensors on Core 1, HTTP on Core 0");
}

// =============================================================================
//  MAIN LOOP — Core 1 ONLY
//  Runs every ~10ms. Handles sensor reads and LCD updates.
//  ZERO network calls here — HTTP task runs on Core 0.
// =============================================================================
void loop() {
  unsigned long now = millis();

  // ── 1. SLOT SENSORS (instant digitalRead, no blocking) ──────────────
  // Returns true if any slot's occupancy changed since last read
  bool sensorChanged = readSlotSensors();

  // ── 2. GATE SENSORS (debounced state machine) ────────────────────
  readGateSensors();

  // ── 3. LCD REFRESH ───────────────────────────────────────────────
  // Update immediately if:
  //   - A sensor detected a change (occupancy updated)
  //   - OR the refresh interval has elapsed (for online status / server updates)
  if (sensorChanged || (now - lastLcdRefreshMs >= LCD_REFRESH_MS)) {
    lastLcdRefreshMs = now;
    updateLCD();
    // Note: updateLcdRow3() is called separately in gate state machine
  }

  // ── 4. NO NETWORK CALLS HERE ──────────────────────────────────────
  // All HTTP communication happens on Core 0 via the httpTask FreeRTOS thread
  
  delay(10);  // Yield back to scheduler every 10ms
}
