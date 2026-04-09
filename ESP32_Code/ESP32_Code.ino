#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>       // Install via Library Manager
#include <ESP32Servo.h>        // Install via Library Manager
#include <Wire.h>
#include <LiquidCrystal_I2C.h> // Install via Library Manager

// ==========================================
// CONFIGURATION
// ==========================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Django Server URL: Change to your laptop's local IP address (e.g. 192.168.1.10)
// Ensure your Django app is running as: python manage.py runserver 0.0.0.0:8000
const char* serverBaseUrl = "http://192.168.1.10:8000"; 

// ==========================================
// PIN DEFINITIONS 
// ==========================================
// LCD Details
LiquidCrystal_I2C lcd(0x27, 20, 4); // Address is usually 0x27 or 0x3F

// Servos
Servo entranceServo;
Servo exitServo;
const int entranceServoPin = 25;
const int exitServoPin = 26;

// IR Sensors (Wait for obstacle: usually LOW)
const int numSlots = 8;
const int irPins[numSlots] = {34, 35, 36, 39, 32, 33, 27, 14};

// LEDs (Red indicators)
const int ledPins[numSlots] = {4, 13, 16, 17, 18, 19, 23, 2};

// Django Database Slot IDs mapping (Assuming ID 1 to 8 map to IR sensors 0 to 7)
const int dbSlotIds[numSlots] = {1, 2, 3, 4, 5, 6, 7, 8};

// State keeping
bool previousOccupancy[numSlots] = {false, false, false, false, false, false, false, false};

// ==========================================
// SETUP
// ==========================================
void setup() {
  Serial.begin(115200);

  // 1. Initialize Default Pins
  for (int i = 0; i < numSlots; i++) {
    pinMode(irPins[i], INPUT);
    pinMode(ledPins[i], OUTPUT);
    digitalWrite(ledPins[i], LOW);
  }

  // 2. Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("System Initializing.");

  // 3. Initialize Servos (Using ESP32Servo to prevent jitter)
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  entranceServo.setPeriodHertz(50);
  exitServo.setPeriodHertz(50);
  entranceServo.attach(entranceServoPin, 500, 2400);
  exitServo.attach(exitServoPin, 500, 2400);
  entranceServo.write(0); // Barrier down
  exitServo.write(0);     // Barrier down

  // 4. Connect to WiFi
  lcd.setCursor(0, 1);
  lcd.print("Connecting WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WiFi Connected!");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP());
  delay(2000);
  lcd.clear();
}

// ==========================================
// MAIN LOOP
// ==========================================
void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    // 1. Fetch web states and update LEDs/LCD
    fetchStatusFromServer();

    // 2. Read physical IR sensors and tell server if anything changed
    checkSensorsAndUpdateServer();
  } else {
    Serial.println("Reconnecting to WiFi...");
    WiFi.reconnect();
  }

  // Poll every 3 seconds to avoid overloading the Django development server
  delay(3000); 
}

// ==========================================
// FUNCTIONS
// ==========================================

void fetchStatusFromServer() {
  HTTPClient http;
  String url = String(serverBaseUrl) + "/api/v1/slots/";
  http.begin(url);
  
  int httpResponseCode = http.GET();
  if (httpResponseCode == 200) {
    String payload = http.getString();
    
    // Parse JSON
    DynamicJsonDocument doc(2048); 
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
       int availableCount = 0;
       int occupiedCount = 0;
       int reservedCount = 0;

       JsonArray results = doc["results"].as<JsonArray>();
       for (JsonObject slot : results) {
          int id = slot["id"];
          String status = slot["status"].as<String>();
          
          if (status == "free") availableCount++;
          else if (status == "occupied") occupiedCount++;
          else if (status == "reserved") reservedCount++;

          // Match Django DB ID to our Physical LEDs
          for (int idx = 0; idx < numSlots; idx++) {
            if (dbSlotIds[idx] == id) {
              if (status == "reserved" || status == "occupied") {
                digitalWrite(ledPins[idx], HIGH); // Turn ON LED
              } else {
                digitalWrite(ledPins[idx], LOW);  // Turn OFF LED
              }
            }
          }
       }

       // Update LCD panel
       lcd.setCursor(0, 0);
       lcd.print("--- PARKING INFO ---");
       lcd.setCursor(0, 1);
       lcd.printf("Free:%d  Rsvd:%d     ", availableCount, reservedCount);
       lcd.setCursor(0, 2);
       lcd.printf("Occupied:%d         ", occupiedCount);
       lcd.setCursor(0, 3);
       lcd.print("System: ONLINE      ");
       
    } else {
      Serial.print("Deserialize JSON failed: ");
      Serial.println(error.f_str());
    }
  } else {
    Serial.printf("Failed fetching status. HTTP Code: %d\n", httpResponseCode);
  }
  
  http.end();
}

void checkSensorsAndUpdateServer() {
  for (int i = 0; i < numSlots; i++) {
    // Assuming LM393 IR module outputs LOW when an obstacle (car) is present
    bool isOccupied = (digitalRead(irPins[i]) == LOW);
    
    // Check if the physical state differs from what was last recorded
    if (isOccupied != previousOccupancy[i]) {
      previousOccupancy[i] = isOccupied;
      String newStatus = isOccupied ? "occupied" : "free";
      
      Serial.printf("Slot %d physically changed. Updating to %s\n", dbSlotIds[i], newStatus.c_str());
      updateSlotStatusOnWeb(dbSlotIds[i], newStatus);
    }
  }
}

void updateSlotStatusOnWeb(int slotId, String newStatus) {
  HTTPClient http;
  String url = String(serverBaseUrl) + "/api/v1/slots/" + String(slotId) + "/status/";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  // Send PATCH request with {"status": "occupied"} 
  String jsonPayload = "{\"status\": \"" + newStatus + "\"}";
  int httpResponseCode = http.PATCH(jsonPayload);

  if (httpResponseCode == 200 || httpResponseCode == 201) {
    Serial.println(" >> Website successfully updated!");
  } else {
    Serial.printf(" >> Failed to update website. Code: %d\n", httpResponseCode);
  }
  http.end();
}

// Function you can trigger via RFID/Keypad or Admin API later
void openEntranceGate() {
  lcd.setCursor(0, 3);
  lcd.print("Gate: OPEN          ");
  entranceServo.write(90); // Lift barrier
  delay(5000); // Keep open for 5 seconds
  entranceServo.write(0); // Close barrier
  lcd.setCursor(0, 3);
  lcd.print("Gate: CLOSED        ");
}
