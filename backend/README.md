# FastAPI Backend (Windows Local-First)

This backend is the core processing engine for the updated architecture.

## Run

```bash
python -m venv .venv
# activate venv
pip install -r requirements.txt
cp .env.example .env  # first-time setup (then edit values)
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

- `CAMERA_SOURCE_MODE` (`rtsp` default, `webcam` for temporary local testing)
- `CAMERA_WEBCAM_SINGLE_NODE` (`cam_door` default for one-webcam outdoor mode; `none` enables dual-webcam workers)
- `CAMERA_INDOOR_RTSP`
- `CAMERA_DOOR_RTSP`
- `CAMERA_INDOOR_WEBCAM_INDEX` (default `0`)
- `CAMERA_DOOR_WEBCAM_INDEX` (default `1`, auto-fallback to `0` if unavailable)
- `CAMERA_PROCESSING_FPS` (default `12`)
- `FACE_COSINE_THRESHOLD` (default `0.52`; higher is stricter)
- `FACE_DETECTOR_MODEL_PATH` (default `backend/storage/models/face/face_detection_yunet_2023mar.onnx`)
- `FACE_RECOGNIZER_MODEL_PATH` (default `backend/storage/models/face/face_recognition_sface_2021dec.onnx`)
- `FACE_DETECT_SCORE_THRESHOLD` (default `0.90`)
- `FACE_DETECT_NMS_THRESHOLD` (default `0.30`)
- `FACE_DETECT_TOP_K` (default `5000`)
- `AUTHORIZED_PRESENCE_LOGGING_ENABLED` (default `false`; logs authorized re-entry when a recognized face appears in camera view)
- `AUTHORIZED_PRESENCE_SCAN_SECONDS` (default `2`)
- `AUTHORIZED_PRESENCE_COOLDOWN_SECONDS` (default `20`)
- `UNKNOWN_PRESENCE_LOGGING_ENABLED` (default `false`; logs unknown-person re-entry with evidence snapshot)
- `UNKNOWN_PRESENCE_COOLDOWN_SECONDS` (default `20`)
- `INTRUDER_EVENT_COOLDOWN_SECONDS` (default `20`; suppresses repeated sensor intruder triggers per node)

Note: authorized/unknown presence scans share `AUTHORIZED_PRESENCE_SCAN_SECONDS` as the scan interval.

## Mobile Remote / Push Env Vars (Optional)

- `LAN_BASE_URL` (used for mobile bootstrap + QR/share links)
- `TAILSCALE_BASE_URL` (optional secure overlay URL)
- `WEBPUSH_VAPID_PUBLIC_KEY`
- `WEBPUSH_VAPID_PRIVATE_KEY`
- `WEBPUSH_VAPID_SUBJECT` (default `mailto:admin@localhost`)
- `TELEGRAM_BOT_TOKEN` (required for actual Telegram delivery)
- `TELEGRAM_CHAT_ID` (single admin chat/group id, supports private/group)
- `TELEGRAM_LINK_NOTIFICATIONS_ENABLED` (default `true`; sends startup/IP-change links)
- `MDNS_ENABLED` (default `true`; publishes `.local` LAN service when dependency is present)
- `MDNS_SERVICE_NAME` (default `thesis-monitor`)
- `MDNS_HOSTNAME` (optional override for `.local` hostname)

Notes:

- Backend auto-loads project root `.env` by default.
- Override env file path using `THESIS_ENV_FILE=/absolute/path/to/file.env`.
- Dashboard runtime settings can override selected `.env` values (including Telegram/WebPush fields) at runtime.

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
- `GET /api/mobile/bootstrap`
- `POST /api/mobile/device/register`
- `POST /api/mobile/device/unregister`
- `GET /api/mobile/notifications/preferences`
- `POST /api/mobile/notifications/preferences`
- `GET /api/remote/access/links`
- `GET /api/integrations/mdns/status`
- `POST /api/integrations/telegram/send-access-link`

## Notes

- Mobile remote interface is toggle-controlled (`/api/remote/mobile/config`) and disabled by default.
- Push delivery requires VAPID keys and `pywebpush` dependency.
- Telegram fallback now uses bot API delivery when token/chat id are configured.
- Remote access links can be auto-sent to Telegram on startup and endpoint changes.
- Retention cleanup runs in background.
