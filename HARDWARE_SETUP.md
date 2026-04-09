# Hardware Setup Guide: ESP32 Smart Parking System

This document outlines the hardware requirements, pin configurations, and wiring instructions for integrating an ESP32 (CH340C) with your Django-based Parking Reservation System.

## 1. Hardware Components Needed

*   **1x ESP32 Development Board (CH340C)**: The main microcontroller. Note: You may need to install CH340 USB drivers on Windows if the board isn't recognized.
*   **8x IR Proximity Sensors (e.g., FC-51/LM393 based)**: To detect if a car is physically present in a slot.
*   **8x Red LEDs**: To visually indicate if a slot is booked/reserved.
*   **8x 220Ω or 330Ω Resistors**: For the LEDs to prevent them from burning out or drawing too much current from the ESP32.
*   **2x Servo Motors (e.g., SG90 or MG996R)**: To control the entrance and exit boom barriers.
*   **1x I2C 20x4 LCD Display**: To display parking status (available, occupied, booked slots).
*   **1x 5V External Power Supply**: Minimum 2 Amps (Ideally 3A). **Crucial for the servo motors.**
*   **Breadboards and Jumper Wires**

---

## 2. Pin Mapping

The ESP32 has a limited number of safe GPIO pins. The mapping below avoids overlapping pins, avoids interfering with the boot process (strapping pins), and utilizes input-only pins where appropriate.

### I2C LCD Display (20x4)
- **SDA** -> GPIO 21
- **SCL** -> GPIO 22
- **VCC** -> 5V (from external power)
- **GND** -> GND

### Servo Motors (Entrance / Exit)
- **Entrance Servo Signal** -> GPIO 25
- **Exit Servo Signal** -> GPIO 26
- **VCC** -> 5V (from external power)
- **GND** -> GND

### IR Proximity Sensors (Occupancy)
*Power the IR sensors using the ESP32's `3.3V` pin to ensure their data output doesn't exceed 3.3V (protecting the ESP32 GPIOs).*
- **Slot 1 Data** -> GPIO 34 *(Input only pin)*
- **Slot 2 Data** -> GPIO 35 *(Input only pin)*
- **Slot 3 Data** -> GPIO 36 (VP) *(Input only pin)*
- **Slot 4 Data** -> GPIO 39 (VN) *(Input only pin)*
- **Slot 5 Data** -> GPIO 32
- **Slot 6 Data** -> GPIO 33
- **Slot 7 Data** -> GPIO 27
- **Slot 8 Data** -> GPIO 14
- **VCC** -> ESP32 3.3V Pin
- **GND** -> GND

### Red LEDs (Booking Indicators)
*Important: Connect a 220Ω - 330Ω resistor in series with the positive (longer) leg of each LED. The negative (shorter) leg goes to GND.*
- **Slot 1** -> GPIO 4
- **Slot 2** -> GPIO 13
- **Slot 3** -> GPIO 16
- **Slot 4** -> GPIO 17
- **Slot 5** -> GPIO 18
- **Slot 6** -> GPIO 19
- **Slot 7** -> GPIO 23
- **Slot 8** -> GPIO 2

---

## 3. Power Distribution Strategy (CRITICAL)

**Do NOT power the Servo Motors directly from the ESP32's 5V (VIN) pin while it is plugged into USB.** Servos draw significant current peaks (up to 1A per motor when moving or stalled). Drawing this from the ESP32 will cause the board to brown-out (reboot randomly) and could permanently damage your computer's USB port or the ESP32's voltage regulator.

1.  **Common Ground:** The most important rule in electronics is that all components must share the same Ground. Connect the GND of your external 5V power supply to one of the GND pins on the ESP32.
2.  **Servos & LCD Power:** Connect the VCC (Red wire) of the two servos and the VCC of the LCD directly to the **External 5V Power Supply**, *not* the ESP32.
3.  **Sensor Power:** Power the 8 IR sensors using the ESP32's `3.3V` pin. This ensures the output logic is 3.3V safe.
4.  **ESP32 Power:** 
    *   *During Development:* Power the ESP32 via your computer's USB cable (so you can read serial logs and upload code). Just ensure the common ground is connected.
    *   *For Standalone deployment:* You can route the external 5V power into the ESP32's `VIN` (or `5V`) pin to power it without a computer.

## 4. Software Communication Architecture Overview

Your ESP32 will act as an IoT client for your Django system. 

1.  **HTTP/REST Polling or WebSockets**: The ESP32 needs to connect to the WiFi network. It should periodically (e.g., every 3-5 seconds) send an HTTP GET request to your Django REST API to fetch the current status of reservations.
2.  **State Management**: If Django says "Slot 1 is booked", the ESP32 triggers `digitalWrite(4, HIGH)` to turn on the Red LED for Slot 1.
3.  **Updating Occupancy**: If an IR Sensor detects an obstacle (car parked), the ESP32 sends an HTTP POST/PATCH request to your Django backend (e.g., `/api/slots/1/occupy/`) to update the database, which your frontend uses to display occupied status.
4.  **Entrance/Exit Logic**:
    *   An RFID or keypad can be added later to trigger the entrance.
    *   Alternatively, the admin clicks "Open Gate" on the Django dashboard, the ESP32 reads this command during its polling cycle, and writes a PWM signal to the Servo (GPIO 25) to sweep from 0° -> 90°, holds for 5 seconds, and returns to 0°.

## 5. IDE Setup (Arduino IDE / PlatformIO)
Because you have the CH340C version:
1. Ensure the board selected in your IDE is **"DOIT ESP32 DEVKIT V1"** or standard **"ESP32 Dev Module"**.
2. Select the correct COM port.
3. The CH340C handles auto-reset perfectly, so you usually will *not* need to hold the physical `BOOT` button on the board when uploading code.
