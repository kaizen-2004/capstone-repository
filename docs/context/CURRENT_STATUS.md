# Current Project Status (2026-04-27)

This file is the primary status snapshot for new sessions.

## 1. System Topology

- Primary host: Windows 10 PC (`backend/app/main.py` + local SQLite + retention + alert engine).
- Windows runtime: packaged/local backend process serving dashboard to browser.
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
- Windows packaging/startup guide: `docs/instructions/deployment/windows_local_startup.md`

## 4. Core Modules

- API/Auth: `backend/app/api/`
- Storage: `backend/app/db/store.py`
- Event pipeline: `backend/app/modules/event_engine.py`
- Face module: `backend/app/modules/face_service.py`
- Fire module: `backend/app/modules/fire_service.py`
- Camera runtime: `backend/app/services/camera_manager.py`
- Background supervisor: `backend/app/services/supervisor.py`

## 5. Enhancement State (Phase 2 Mobile)

- Mobile remote interface: implemented (`/dashboard/remote/mobile`), disabled by default and toggle-controlled in Settings.
- Mobile app/PWA notification APIs: implemented (`/api/mobile/bootstrap`, device register/unregister, notification preferences).
- Alert dispatch to mobile push: implemented with web-push dispatcher; active when VAPID keys are configured.
- Telegram fallback: implemented via bot API when `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` are configured.
- Tailscale remote access: optional URL overlay via `TAILSCALE_BASE_URL`; preferred link path when configured.
- LAN mDNS: optional `.local` publishing via `zeroconf` (`MDNS_ENABLED`, `MDNS_SERVICE_NAME`, `MDNS_HOSTNAME`).
- Remote access link operations: `GET /api/remote/access/links`, `GET /api/integrations/mdns/status`, `POST /api/integrations/telegram/send-access-link`.

## 6. Documentation Authority

Use these docs in order for implementation guidance:

1. `docs/README.md`
2. `docs/instructions/transport/http_quick_start.md`
3. `docs/instructions/transport/http_deployment.md`
4. `docs/instructions/camera/rtsp_dual_camera.md`
5. `docs/instructions/deployment/windows_local_startup.md`

Archive docs are not primary source of truth for active implementation.
