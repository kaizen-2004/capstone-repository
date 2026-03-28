# Current Project Status (2026-03-28)

This file is the primary status snapshot for new sessions.

## 1. System Topology

- Primary host: Windows 10 PC (`backend/app/main.py` + local SQLite + retention + alert engine).
- Desktop shell: Tauri (`desktop/src-tauri`) loading local dashboard.
- Frontend: React dashboard (`web_dashboard_ui`) served at `/dashboard`.
- Monitored areas: Living Room and Door Entrance Area.

## 2. Active Data Transport

Active architecture:

- Sensor nodes (ESP32-C3) communicate over HTTP.
- Cameras are RTSP IP streams.
- Backend compatibility endpoint remains `POST /api/sensors/event`.

Data path:

`ESP32-C3 HTTP -> FastAPI ingest -> fusion/event engine -> SQLite + alerts + dashboard`

RTSP path:

`RTSP stream -> camera manager -> lightweight monitoring -> triggered heavy analysis`

## 3. Runtime Entry Points

- Backend: `python backend/run_backend.py`
- Dashboard: `http://127.0.0.1:8765/dashboard`
- Desktop shell: `cd desktop && npm run dev`

## 4. Core Modules

- API/Auth: `backend/app/api/`
- Storage: `backend/app/db/store.py`
- Event pipeline: `backend/app/modules/event_engine.py`
- Face module: `backend/app/modules/face_service.py`
- Fire module: `backend/app/modules/fire_service.py`
- Camera runtime: `backend/app/services/camera_manager.py`
- Background supervisor: `backend/app/services/supervisor.py`

## 5. Enhancement Flags (Disabled)

- Telegram integration: scaffolded, disabled.
- Tailscale remote access integration: scaffolded, disabled.

## 6. Documentation Authority

Use these docs in order for implementation guidance:

1. `docs/README.md`
2. `docs/instructions/transport/http_quick_start.md`
3. `docs/instructions/transport/http_deployment.md`
4. `docs/instructions/camera/rtsp_dual_camera.md`
5. `docs/instructions/deployment/windows_desktop_autostart.md`

Archive docs are not primary source of truth for active implementation.
