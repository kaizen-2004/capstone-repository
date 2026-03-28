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

## Enhancement Stubs (Disabled)

The following are scaffolded but disabled in core phase:

- Telegram integration endpoints.
- Tailscale remote status endpoint.

## Run Backend

```bash
python -m venv .venv
# activate venv
pip install -r requirements.txt
python backend/run_backend.py
```

Backend: `http://127.0.0.1:8765`
Dashboard: `http://127.0.0.1:8765/dashboard`

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
