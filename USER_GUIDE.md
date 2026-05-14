# 📘 ParkSmart – Detailed User Guide Manual

**System:** Smart Parking Lot Reservation System  
**Stack:** Django 5 · Django REST Framework · ESP32 (Arduino) · SQLite · APScheduler  
**Timezone:** Asia/Manila (PHT, UTC+8)  
**Version:** 2.0 (Dual-Core ESP32 Firmware)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Getting Started – Local Development](#3-getting-started--local-development)
4. [Environment Variables](#4-environment-variables)
5. [End-User Booking Flow](#5-end-user-booking-flow)
6. [Admin Panel Guide](#6-admin-panel-guide)
7. [REST API Reference (ESP32)](#7-rest-api-reference-esp32)
8. [ESP32 Firmware Guide](#8-esp32-firmware-guide)
9. [Background Scheduler](#9-background-scheduler)
10. [Data Models Reference](#10-data-models-reference)
11. [Deployment to Render](#11-deployment-to-render)
12. [Troubleshooting](#12-troubleshooting)
13. [Security Notes](#13-security-notes)

---

## 1. System Overview

**ParkSmart** is an IoT-enabled parking reservation web application. Users can browse available parking slots, make short-duration reservations through a web browser, and physically check in using the ESP32-powered hardware gate at the parking entrance.

### Key Features

| Feature | Description |
|---|---|
| Live slot map | Home page shows real-time counts: Free / Reserved / Occupied / Total |
| Slot selection | Interactive grid with color-coded status per slot |
| Short reservations | Choose 5, 10, or 15-minute hold window |
| Booking code | Unique 5-character alphanumeric code (e.g. `A9X2B`) generated per reservation |
| Countdown timer | Live countdown on confirmation page; auto-refreshes on expiry |
| Auto-release | APScheduler checks every 30 s; expired reservations are auto-cancelled and slots freed |
| Cancel reservation | User can cancel an active reservation from the confirmation page |
| Admin panel | Password-protected dashboard for slot management and reports |
| REST API | JSON endpoints consumed by ESP32 to sync physical sensor data |
| ESP32 hardware | Dual-core firmware: sensors/gates on Core 1, HTTP on Core 0 |

### Slot Status Definitions

| Status | Color | Meaning |
|---|---|---|
| `free` | 🟢 Green | Available for booking |
| `reserved` | 🟡 Yellow | Booked online; waiting for car to arrive |
| `occupied` | 🔴 Red | IR sensor confirmed car is physically present |
| `maintenance` | ⚪ Gray | Disabled by admin; not bookable |

### Reservation Status Definitions

| Status | Meaning |
|---|---|
| `active` | Booking code is valid; countdown running |
| `checked_in` | Car arrived and was validated at the gate |
| `expired` | Reservation window ended; slot auto-released |
| `cancelled` | User or admin cancelled the booking |
| `completed` | Full parking session finished |

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User's Browser                             │
│  home → select slot → reservation form → confirmation (countdown)   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP (Django Views)
┌──────────────────────────────▼──────────────────────────────────────┐
│                        Django Web Server                            │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────────┐ │
│  │  Public Views  │  │  Admin Views     │  │  REST API (DRF)      │ │
│  │  home          │  │  /admin-panel/   │  │  /api/v1/slots/      │ │
│  │  select_slot   │  │  dashboard       │  │  /api/v1/slots/bulk  │ │
│  │  reserve_slot  │  │  slot_management │  │  /api/v1/reservations│ │
│  │  confirmation  │  │  reports         │  │  /validate/          │ │
│  └────────────────┘  └─────────────────┘  └──────────┬───────────┘ │
│                                                        │             │
│  ┌────────────────────────────────────────────────────┐│            │
│  │  SQLite Database  (db.sqlite3)                      ││            │
│  │   ParkingSlot  ·  Reservation                       ││            │
│  └────────────────────────────────────────────────────┘│            │
│  ┌──────────────────────────────────────────┐           │            │
│  │  APScheduler (every 30s)                 │           │            │
│  │  release_expired_reservations()           │           │            │
│  └──────────────────────────────────────────┘           │            │
└────────────────────────────────────────────────────────┼────────────┘
                                                         │ HTTPS / JSON
┌────────────────────────────────────────────────────────▼────────────┐
│                     ESP32 Dev Module (CH340C)                        │
│                                                                      │
│  Core 1 (Arduino loop ~10ms)      Core 0 (FreeRTOS httpTask)        │
│  ┌──────────────────────────┐     ┌──────────────────────────────┐  │
│  │ Read 8× IR slot sensors  │     │ GET  /api/v1/slots/          │  │
│  │ Read entrance/exit IR    │     │ POST /api/v1/slots/bulk-     │  │
│  │ Gate servo state machine │     │      update/  (on change)    │  │
│  │ Update 20×4 LCD display  │     │ Poll every 5 seconds         │  │
│  └──────────────────────────┘     └──────────────────────────────┘  │
│                                                                      │
│  Hardware: Servos · IR Sensors · LCD · LEDs                         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Getting Started – Local Development

### Prerequisites

- Python 3.10+
- pip
- Git

### Step-by-Step Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd parkinglot_system

# 2. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment variables
copy .env.example .env
# Edit .env and set a strong DJANGO_SECRET_KEY and ADMIN_PASSWORD

# 5. Apply database migrations
python manage.py migrate

# 6. Seed the 8 default parking slots (matches ESP32 hardware DB_SLOT_IDS 1–8)
python manage.py seed_slots

# 7. Start the development server
python manage.py runserver
```

Open your browser at: **http://127.0.0.1:8000/**

Admin panel: **http://127.0.0.1:8000/admin-panel/login/**

> **Note:** The APScheduler (auto-release) only starts when running `runserver` or `gunicorn`. It does NOT run during `migrate` or other management commands.

---

## 4. Environment Variables

Configure these in a `.env` file at the project root (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | insecure dev key | Django secret key — **MUST be changed in production** |
| `ADMIN_PASSWORD` | `admin123` | Password for the `/admin-panel/` login page |
| `DEBUG` | `True` | Set to `False` in production |

The settings file (`parking_system/settings.py`) reads these via `python-dotenv`.

---

## 5. End-User Booking Flow

### Step 1 – Home Page (`/`)

- Shows live parking statistics: **Available**, **Reserved**, **Occupied**, **Total**.
- Three-step process description is displayed.
- Click **"Book Now"** to begin.

### Step 2 – Select a Slot (`/slots/`)

- An interactive grid of all parking slots is displayed.
- Each slot card is color-coded by status:
  - **Green border** → clickable, takes you to the booking form.
  - **Yellow/Red/Gray border** → not selectable (already reserved, occupied, or under maintenance).
- Click any **green (Free)** slot card to proceed.

### Step 3 – Fill the Reservation Form (`/book/<slot_id>/`)

Fill in the following fields:

| Field | Options | Notes |
|---|---|---|
| **Duration** | 5 min / 10 min / 15 min | Radio button toggle; 5 min pre-selected |
| **Vehicle Type** | Car, Motorcycle, SUV, Truck, Van, Other | Dropdown |
| **Vehicle Color** | Free text | e.g. "Red", "Silver" |
| **Plate Number** | Free text | e.g. "ABC 1234" — must be unique among active reservations |

> **Validation:** If the same plate number already has an `active` or `checked_in` reservation, the form will reject the submission with an error message.

Click **"Confirm Reservation"** to submit.

### Step 4 – Confirmation Page (`/confirmation/<booking_code>/`)

After a successful booking:

- A **5-character booking code** is displayed prominently (e.g. `A9X2B`).
- A **live countdown timer** starts immediately, counting down from your chosen duration.
- The timer syncs with the server every 10 seconds.
- When the timer reaches `00:00`, the page automatically reloads and shows **"Reservation Expired"**.

**Available Actions:**

| Button | Action |
|---|---|
| **TAKE A SCREENSHOT** | Opens a printable receipt page in a new tab |
| **CANCEL RESERVATION** | Immediately cancels the active booking and frees the slot (with a confirmation dialog) |
| **Go Home** | Returns to the home page |

### Step 5 – Check In at the Gate

Present your **booking code** at the ESP32 hardware terminal. The ESP32:
1. Validates the code via `POST /api/v1/reservations/validate/`.
2. If valid: marks reservation as `checked_in`, slot as `occupied`, and opens the servo gate.
3. If expired or already used: returns an error response (gate stays closed).

### Checking an Existing Reservation

Click **"Check Reservation"** in the navbar to open a modal dialog. Enter your 5-character booking code to jump directly to your confirmation page.

---

## 6. Admin Panel Guide

Access at: `/admin-panel/login/`  
Password is set via the `ADMIN_PASSWORD` environment variable (default: `admin123`).

> The admin panel uses Django **session-based** authentication (not the Django superuser system). The session key `is_admin` is set to `True` on login.

### 6.1 Dashboard (`/admin-panel/`)

Displays:

| Metric | Description |
|---|---|
| **Occupancy Rate** | `(occupied + reserved) / total × 100%` — colored red >80%, green <30% |
| **Total Slots** | Total count with Free and Maintenance sub-counts |
| **Active / Reserved** | Slots currently holding an active reservation |
| **Currently Occupied** | Slots where a car is physically detected |
| **Today's Reservations** | Count of bookings made today |
| **Recent Reservations** | Table of last 20 reservations with live mini-countdown for active ones |

### 6.2 Slot Management (`/admin-panel/slots/`)

#### Add a New Slot

Fill in:
- **Slot Number** — e.g. `C-01` (auto-converted to uppercase; must be unique)
- **Location** — e.g. `Basement 1`

Click **"Add Slot"**. The slot is immediately available for booking.

#### Toggle Maintenance Mode

| Slot Status | Button | Result |
|---|---|---|
| `free` | **Disable (Maintenance)** | Sets status to `maintenance`; slot disappears from booking grid |
| `maintenance` | **Enable** | Sets status back to `free` |
| `reserved` or `occupied` | **In Use** (disabled) | Cannot change while in use |

#### Delete a Slot

- Click the 🗑️ button next to a slot.
- A browser confirmation dialog appears.
- **Cannot delete** slots that are `reserved` or `occupied` (button is disabled).
- Deletion is permanent and cascades to related reservations.

### 6.3 Reports & Analytics (`/admin-panel/reports/`)

| Metric | Description |
|---|---|
| **Reservations (30 Days)** | Total booking count in the last 30 days |
| **Total Successfully Parked** | All-time `checked_in` count |
| **No-Shows (Expired)** | All-time `expired` count |
| **Turnover Success Rate** | `checked_in / total_all_time × 100%` |
| **Last 7 Days Breakdown** | Per-day table: total, checked-in, expired, with a visual progress bar |

### 6.4 Django Admin Interface (`/admin/`)

The standard Django admin at `/admin/` is also available for superusers with full model access:
- **ParkingSlot** — filterable by status and location; searchable by slot number.
- **Reservation** — filterable by status, vehicle type, duration; searchable by booking code and plate number.

To create a superuser:
```bash
python manage.py createsuperuser
```

---

## 7. REST API Reference (ESP32)

All endpoints are under `/api/v1/`. Authentication is **open** (AllowAny) — secure your network or add token auth for production.

### 7.1 List All Slots

```
GET /api/v1/slots/
```

**Response:**
```json
{
  "count": 8,
  "results": [
    {
      "id": 1,
      "slot_number": "P-1",
      "location": "Main Parking Area",
      "status": "free",
      "status_display": "Free",
      "created_at": "2026-05-13T03:00:00Z",
      "updated_at": "2026-05-13T03:05:00Z"
    }
  ]
}
```

---

### 7.2 Get Single Slot

```
GET /api/v1/slots/<id>/
```

Returns details for a single parking slot.

---

### 7.3 Update a Single Slot Status

```
PATCH /api/v1/slots/<id>/status/
Content-Type: application/json

{"status": "occupied"}
```

Valid values: `free`, `occupied`, `reserved`, `maintenance`.

**Smart Transitions:**

| Slot Was | ESP32 Sends | Result |
|---|---|---|
| `reserved` | `occupied` | Auto-checks in the active reservation (`checked_in` status), sets slot to `occupied` |
| `reserved` | `free` | **Ignored** — slot stays `reserved` (car hasn't arrived yet) |
| `free` | `occupied` | Slot becomes `occupied` normally |
| `occupied` | `free` | Slot becomes `free` normally |

---

### 7.4 Bulk Update Slots (Primary ESP32 Endpoint)

```
POST /api/v1/slots/bulk-update/
Content-Type: application/json

{
  "slots": [
    {"id": 1, "status": "occupied"},
    {"id": 2, "status": "free"},
    {"id": 3, "status": "occupied"}
  ]
}
```

Used by the ESP32 to sync all changed slots in a single HTTP call, dramatically reducing latency vs. 8 individual PATCH calls. Applies the same smart transition rules as the single-slot endpoint.

**Response:**
```json
{
  "results": [
    {"id": 1, "ok": true, "status": "occupied"},
    {"id": 2, "ok": true, "status": "free"},
    {"id": 3, "ok": true, "skipped": true, "reason": "reserved"}
  ]
}
```

---

### 7.5 Validate Booking Code (Gate Check-in)

```
POST /api/v1/reservations/validate/
Content-Type: application/json

{"booking_code": "A9X2B"}
```

| HTTP Status | Meaning |
|---|---|
| `200 OK` | Valid — reservation set to `checked_in`, slot set to `occupied` |
| `404 Not Found` | Booking code does not exist |
| `410 Gone` | Reservation has expired |
| `409 Conflict` | Already checked in |
| `400 Bad Request` | Reservation in an invalid state |

**Success Response:**
```json
{
  "valid": true,
  "message": "Check-in successful",
  "reservation": {
    "booking_code": "A9X2B",
    "slot_number": "P-3",
    "slot_location": "Main Parking Area",
    "vehicle_type": "Car",
    "vehicle_color": "Red",
    "plate_number": "ABC 1234",
    "status": "checked_in",
    "time_remaining": 0
  }
}
```

---

### 7.6 Get Reservation by Booking Code

```
GET /api/v1/reservations/<booking_code>/
```

Returns full reservation details. Booking code is case-insensitive (auto-uppercased).

---

## 8. ESP32 Firmware Guide

File: `ESP32_Code/ESP32_Code.ino`

### Required Arduino Libraries

Install via Arduino IDE → Library Manager:

| Library | Version |
|---|---|
| `ArduinoJson` | ≥ 6.x |
| `ESP32Servo` | by Kevin Harrington |
| `LiquidCrystal_I2C` | by Frank de Brabander |

Board: **DOIT ESP32 DEVKIT V1** or **ESP32 Dev Module**

### User Configuration (Top of File)

```cpp
const char* WIFI_SSID       = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD   = "YOUR_WIFI_PASSWORD";
const char* SERVER_BASE_URL = "https://your-server.onrender.com";
```

### Pin Map Summary

| Component | Pin(s) |
|---|---|
| LCD SDA | GPIO 21 |
| LCD SCL | GPIO 22 |
| Entrance Servo | GPIO 25 |
| Exit Servo | GPIO 26 |
| Entrance IR Sensor | GPIO 18 |
| Exit IR Sensor | GPIO 19 |
| Slot IR Sensors (1–8) | GPIO 34, 35, 36, 39, 32, 33, 27, 14 |

> IR sensors (slots) are wired to **3.3V** power to keep output logic safe for ESP32 GPIOs.  
> Servos are wired to **external 5V** power supply — do NOT power from ESP32's VIN/USB.

### Dual-Core Architecture

| Core | Task | Details |
|---|---|---|
| **Core 1** (Arduino `loop()`) | Sensors, LCD, Gates | Runs every ~10ms; zero network calls; instant response |
| **Core 0** (FreeRTOS `httpTask`) | HTTP communication | Polls server every 5 seconds; can block on SSL handshake without affecting sensors |

### Gate State Machine

Each gate (entrance / exit) runs a **debounced 2-state machine**:

```
CLOSED → (object detected for ≥ 2s) → OPEN  (servo → 90°)
OPEN   → (object gone for ≥ 2s)     → CLOSED (servo → 0°)
```

The 2-second debounce prevents false triggers from brief IR noise.

### LCD Display Layout (20×4)

```
Row 0: PARKING  [ONLINE ]     ← or [OFFLINE] if no server
Row 1: Free:6   Rsvd:0
Row 2: Occ:2  S:OOXOOOOO      ← X=occupied, O=free
Row 3: IN:CLOSED OUT:CLOSED   ← gate status
```

### HTTP Sync Logic

1. **On startup:** Connects to WiFi (15-second timeout). Falls back to offline mode if WiFi fails — sensors and gates still work.
2. **Every 5 seconds (Core 0):** Fetches slot list from `GET /api/v1/slots/` to get reserved count and server-side state.
3. **On sensor change:** Sets `needsSync = true`. Core 0 picks this up and calls `POST /api/v1/slots/bulk-update/` with only the changed slots.
4. **SSL:** Uses `WiFiClientSecure` with `setInsecure()` (no certificate verification) for simplicity with self-signed/Let's Encrypt certs on Render.

---

## 9. Background Scheduler

**File:** `bookings/tasks.py`  
**Library:** `APScheduler` via `django-apscheduler`

### `release_expired_reservations()`

Runs every **30 seconds** while the server is running.

Logic:
1. Queries all reservations with `status='active'` AND `expires_at < now`.
2. For each expired reservation:
   - Sets `reservation.status = 'expired'`
   - Sets `reservation.slot.status = 'free'`
   - Saves both records.
3. Logs the count of released reservations.

### Scheduler Start Condition

The scheduler only starts when the process is `runserver` or `gunicorn`. It will **not** run during:
- `migrate`
- `seed_slots`
- Any other management command

This prevents duplicate scheduler instances and errors during deployment builds.

---

## 10. Data Models Reference

### `ParkingSlot`

| Field | Type | Notes |
|---|---|---|
| `id` | AutoField | Primary key |
| `slot_number` | CharField(10) | Unique; e.g. `P-1`, `A-01` |
| `location` | CharField(100) | e.g. `Main Parking Area` |
| `status` | CharField | `free`, `reserved`, `occupied`, `maintenance` |
| `created_at` | DateTimeField | Auto set on creation |
| `updated_at` | DateTimeField | Auto updated on save |

**Properties:** `status_color` (Bootstrap class), `status_icon` (emoji)

### `Reservation`

| Field | Type | Notes |
|---|---|---|
| `id` | AutoField | Primary key |
| `slot` | ForeignKey → ParkingSlot | Cascades on delete |
| `booking_code` | CharField(5) | Unique; auto-generated alphanumeric |
| `reserved_at` | DateTimeField | Auto set on creation |
| `expires_at` | DateTimeField | Set from `reserved_at + duration_minutes` |
| `duration_minutes` | IntegerField | Choices: 5, 10, 15 |
| `status` | CharField | `active`, `expired`, `checked_in`, `completed`, `cancelled` |
| `checked_in_at` | DateTimeField | Nullable; set when car arrives |
| `vehicle_type` | CharField | Car, Motorcycle, SUV, Truck, Van, Other |
| `vehicle_color` | CharField(50) | Free text |
| `plate_number` | CharField(20) | Indexed; validated unique per active reservation |

**Properties:** `is_expired` (bool), `time_remaining` (seconds), `status_badge` (Bootstrap class)

### Booking Code Generation (`bookings/utils.py`)

- 5-character string from `A-Z` + `0-9` (uppercase only).
- Collision-safe: loops until a non-existing code is found.
- Stored with `db_index=True` for fast lookups.

---

## 11. Deployment to Render

The project includes a `render.yaml` for one-click deployment.

### Build Command (runs on each deploy)

```bash
pip install -r requirements.txt && \
python manage.py collectstatic --noinput && \
python manage.py migrate && \
python manage.py seed_slots
```

### Start Command

```bash
gunicorn parking_system.wsgi:application
```

### Environment Variables on Render

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | Auto-generated by Render |
| `ADMIN_PASSWORD` | Set your own strong password |
| `DEBUG` | `False` |

### Static Files

WhiteNoise serves static files in production (`whitenoise.middleware.WhiteNoiseMiddleware`). Files are collected to `/staticfiles/` during the build step.

### Database

SQLite (`db.sqlite3`) is used for both development and production. Note that Render's free tier has an ephemeral filesystem — the database resets on each deploy. For persistent data, configure a PostgreSQL database (update `DATABASES` in `settings.py`) and add `psycopg2-binary` to `requirements.txt`.

---

## 12. Troubleshooting

### Slot shows as `reserved` but nobody booked it

**Cause:** A reservation expired but the scheduler hasn't run yet (runs every 30s).  
**Fix:** Wait up to 30 seconds, or trigger the cleanup manually in the Django shell:
```python
python manage.py shell
>>> from bookings.tasks import release_expired_reservations
>>> release_expired_reservations()
```

### "Slot is no longer available" error when trying to book

**Cause:** The slot was reserved by someone else between you viewing the grid and submitting the form.  
**Fix:** Return to the slot selection page and choose a different slot.

### Plate number rejected as "already has an ongoing reservation"

**Cause:** The same plate is still in `active` or `checked_in` status from a previous booking.  
**Fix:** Either wait for the reservation to expire (auto-released within 30s of expiry) or cancel the previous reservation via its confirmation page.

### ESP32 shows `[OFFLINE]` on LCD

**Causes and fixes:**
1. **WiFi not connected** — Check SSID/password in the `.ino` file; ensure the router is reachable.
2. **Server URL wrong** — Verify `SERVER_BASE_URL` matches your deployed URL exactly (include `https://`).
3. **Server is sleeping** — Render free tier instances sleep after inactivity. The first request may take 30–60 seconds to wake the server.

### ESP32 not detected by PC (Windows)

- The CH340C USB chip requires drivers. Download and install the **CH340 driver** from the manufacturer's website.
- After installation, verify the COM port appears in Device Manager.
- Select the correct COM port in Arduino IDE before uploading.

### Admin panel login fails

- Verify the `ADMIN_PASSWORD` environment variable is set correctly in `.env` (local) or in Render's environment variables (production).
- The default fallback password is `admin123` if the environment variable is not set.

### APScheduler errors in logs

- Only one scheduler instance should run. If you see "Scheduler already running" errors, it means the app is being loaded multiple times (e.g., Django dev server autoreload). This is handled by the `scheduler_started` global flag.

---

## 13. Security Notes

> [!WARNING]
> The following defaults are **insecure** and must be changed before public deployment.

| Issue | Risk | Fix |
|---|---|---|
| Default `ADMIN_PASSWORD = admin123` | Anyone can access the admin panel | Set a strong `ADMIN_PASSWORD` environment variable |
| Default `DJANGO_SECRET_KEY` | Sessions/tokens can be forged | Render auto-generates this; set your own for other hosts |
| `DEBUG = True` in dev | Exposes full stack traces | Set `DEBUG=False` in production |
| REST API `AllowAny` | Any device can read/write slot status | Add API token authentication for production ESP32 deployments |
| ESP32 SSL `setInsecure()` | No certificate verification (MITM risk) | Use `setCACert()` with the server's root CA certificate in production |
| SQLite in production | Ephemeral on Render free tier | Migrate to PostgreSQL for persistent storage |

---

*© 2026 ParkSmart Reservation System. All rights reserved.*
