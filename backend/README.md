# FastAPI Backend (Windows Local-First)

This backend is the core processing engine for the updated architecture.

## Run

```bash
python -m venv .venv
# activate venv
pip install -r requirements.txt
python backend/run_backend.py
```

Backend URL: `http://127.0.0.1:8765`

Dashboard URL (served static build): `http://127.0.0.1:8765/dashboard`

## Default Admin

- Username: `admin`
- Password: `admin123`

Override using env vars:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

## Camera Env Vars

- `CAMERA_INDOOR_RTSP`
- `CAMERA_DOOR_RTSP`
- `CAMERA_PROCESSING_FPS` (default `12`)

## Core APIs

- `POST /api/devices/register`
- `POST /api/devices/heartbeat`
- `POST /api/sensors/reading`
- `POST /api/sensors/event`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/ui/events/live`
- `GET /api/ui/nodes/live`
- `GET /api/ui/stats/daily`
- `GET /api/ui/settings/live`
- `POST /api/alerts/{id}/ack`

## Notes

- Telegram and Tailscale endpoints are scaffolded and disabled by default.
- Retention cleanup runs in background.
