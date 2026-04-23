# Real-Time Intruder and Fire Monitoring System (Windows Local-First)

## Project Title

**Real-Time Intruder and Fire Monitoring Alert System Using IoT-Based Sensor Fusion and Event-Driven Facial Recognition with Night-Vision Cameras**

## Active Architecture

This repository now follows a **Windows 10 local-first architecture**:

- **Desktop shell:** Tauri (`desktop/`)
- **Frontend:** React dashboard (`web_dashboard_ui/`)
- **Backend:** FastAPI (`backend/`)
- **Sensors:** ESP32-C3 nodes over **HTTP**
- **Cameras:** 2 RTSP IP night-vision streams (`cam_indoor`, `cam_door`)
- **Storage:** local SQLite + file snapshots/logs

Core processing is event-driven:

- Continuous lightweight monitoring for heartbeat/health and trigger detection.
- Heavy analysis (face matching, fire visual confirmation) only on relevant triggers.

## Core Features Implemented (Phase 1)

- Local backend startup and API orchestration.
- Sensor registration, heartbeat, and event ingest over HTTP.
- RTSP camera health monitoring and frame capture.
- Smoke-first fire pipeline with camera confirmation.
- Entry/tamper intruder pipeline with selective face recognition.
- Alert creation, acknowledgment, and local persistence.
- Login-protected dashboard (single admin account).
- Face enrollment via image upload and model training.
- Retention cleanup background job.
- Offline-capable local operation.

## Mobile App / Remote Enhancements (Phase 2)

- Mobile remote interface route is available at `/dashboard/remote/mobile` and admin-toggle controlled in Settings.
- PWA install assets are included (`manifest.webmanifest`, service worker, app icon).
- App notification APIs are implemented:
  - `GET /api/mobile/bootstrap`
  - `POST /api/mobile/device/register`
  - `POST /api/mobile/device/unregister`
  - `GET /api/mobile/notifications/preferences`
  - `POST /api/mobile/notifications/preferences`
- Alert dispatch now attempts mobile push delivery first and keeps Telegram fallback logging path.

## Web-Only Remote Access (Phase 3)

- Native mobile app is intentionally skipped to reduce deployment complexity and keep Android/iOS fully cross-platform via browser.
- Remote access links are now resolved dynamically with priority: `Tailscale -> mDNS (.local) -> LAN`.
- Telegram bot delivery can send access links at startup, when endpoints change, and on manual request from Settings.
- mDNS publishing is supported on LAN when `zeroconf` is installed and `MDNS_ENABLED=true`.

## Run Backend

```bash
python -m venv .venv
# activate venv
pip install -r requirements.txt
cp .env.example .env
# edit .env (TAILSCALE_BASE_URL, LAN_BASE_URL, TELEGRAM_* etc.)
python backend/run_backend.py
```

Backend: `http://127.0.0.1:8765`
Dashboard: `http://127.0.0.1:8765/dashboard`
Mobile remote: `http://127.0.0.1:8765/dashboard/remote/mobile`

Camera source env vars:

- `CAMERA_SOURCE_MODE` (`rtsp` default, `webcam` for temporary local testing)
- `CAMERA_WEBCAM_SINGLE_NODE` (`cam_door` default for single-webcam outdoor testing; set `none` for dual-webcam workers)
- `CAMERA_INDOOR_RTSP` / `CAMERA_DOOR_RTSP` (used when `CAMERA_SOURCE_MODE=rtsp`)
- `CAMERA_INDOOR_WEBCAM_INDEX` (default `0` when `CAMERA_SOURCE_MODE=webcam`)
- `CAMERA_DOOR_WEBCAM_INDEX` (default `1`, auto-fallback to index `0` if unavailable)
- `CAMERA_PROCESSING_FPS` (default `12`)
- `FACE_COSINE_THRESHOLD` (default `0.52`; higher is stricter)
- `FACE_DETECTOR_MODEL_PATH` (default `backend/storage/models/face/face_detection_yunet_2023mar.onnx`)
- `FACE_RECOGNIZER_MODEL_PATH` (default `backend/storage/models/face/face_recognition_sface_2021dec.onnx`)
- `FACE_DETECT_SCORE_THRESHOLD` (default `0.90`)
- `FACE_DETECT_NMS_THRESHOLD` (default `0.30`)
- `FACE_DETECT_TOP_K` (default `5000`)
- `AUTHORIZED_PRESENCE_LOGGING_ENABLED` (default `false`; when `true`, logs authorized re-entry events from live camera view)
- `AUTHORIZED_PRESENCE_SCAN_SECONDS` (default `2`; scan interval for authorized presence logging)
- `AUTHORIZED_PRESENCE_COOLDOWN_SECONDS` (default `20`; minimum seconds between repeated authorized-presence logs)
- `UNKNOWN_PRESENCE_LOGGING_ENABLED` (default `false`; when `true`, logs unknown-person re-entry events and captures evidence snapshots)
- `UNKNOWN_PRESENCE_COOLDOWN_SECONDS` (default `20`; minimum seconds between repeated unknown-person re-entry logs)
- `INTRUDER_EVENT_COOLDOWN_SECONDS` (default `20`; suppresses repeated sensor intruder triggers per node during cooldown)

Note: authorized/unknown presence scans share `AUTHORIZED_PRESENCE_SCAN_SECONDS` as the polling interval.

Temporary webcam test mode example:

```bash
export CAMERA_SOURCE_MODE=webcam
export CAMERA_WEBCAM_SINGLE_NODE=cam_door
export CAMERA_INDOOR_WEBCAM_INDEX=0
export CAMERA_DOOR_WEBCAM_INDEX=1
export FACE_COSINE_THRESHOLD=0.50
export AUTHORIZED_PRESENCE_LOGGING_ENABLED=true
export UNKNOWN_PRESENCE_LOGGING_ENABLED=true
python backend/run_backend.py
```

For one-webcam outdoor-only testing, use `CAMERA_DOOR_WEBCAM_INDEX=0`.

Optional env vars for mobile push:

- `WEBPUSH_VAPID_PUBLIC_KEY`
- `WEBPUSH_VAPID_PRIVATE_KEY`
- `WEBPUSH_VAPID_SUBJECT` (default `mailto:admin@localhost`)
- `LAN_BASE_URL` (recommended for QR/shared links)
- `TAILSCALE_BASE_URL` (optional remote overlay)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_LINK_NOTIFICATIONS_ENABLED` (default `true`)
- `MDNS_ENABLED` (default `true`)
- `MDNS_SERVICE_NAME` (default `thesis-monitor`)
- `MDNS_HOSTNAME` (optional override)

`.env` at project root is auto-loaded by backend startup (`backend/run_backend.py` and FastAPI app startup).

Dashboard runtime settings can override selected `.env` keys (including Telegram/WebPush fields) without editing `.env`. `.env` is treated as startup defaults/fallback.

Default admin:

- Username: `admin`
- Password: `admin123`

## Build Frontend

```bash
cd web_dashboard_ui
npm install
npm run build
```

## Full Preview Automation

Run end-to-end preview checks (tests, build, backend startup, auth, event trigger, alert ack):

```bash
bash scripts/preview_full_system.sh
```

## Desktop Shell (Tauri)

```bash
cd desktop
npm install
npm run dev
```

For LAN mobile testing, allow backend binding override before launching desktop:

```bash
cd desktop
DESKTOP_BACKEND_HOST=0.0.0.0 DESKTOP_BACKEND_PORT=8765 npm run dev
```

MSI build:

```bash
cd desktop
npm run build
```

## Sensor Event Contract

Compatibility contract preserved:

- `POST /api/sensors/event`

Recommended canonical device endpoints:

- `POST /api/devices/register`
- `POST /api/devices/heartbeat`
- `POST /api/sensors/reading`

## Repository Map

- `backend/`: FastAPI backend, modules, and tests
- `desktop/`: Tauri desktop host and MSI bundle config
- `web_dashboard_ui/`: React dashboard UI
- `firmware/http/`: HTTP-based ESP32-C3 firmware
- `docs/`: updated architecture and deployment docs
