# IntruFlare App (Frontend Only)

Flutter frontend scaffold for a condo intruder and fire monitoring system.

## Included screens
- Home dashboard summary
- Monitor screen using `WebView`
- Alerts screen with polling-based refresh and alert acknowledgement
- Node provisioning screen for ESP32-C3 setup AP mode
- Face enrollment screen with mobile image capture and upload
- Guided FAQ assistant screen
- Settings screen for backend URL, dashboard URL, bearer token, and polling interval

## Quick start
1. Create a new Flutter project or open this folder as your Flutter app.
2. Run:
   ```bash
   flutter pub get
   flutter run
   ```
3. Open **Settings** inside the app and configure:
   - Backend base URL
   - Dashboard URL
   - Bearer token (if your API requires it)
   - Alert polling interval

## Android package migration (safe rollout)

Android `namespace` is now `com.intruflare.app` and default `applicationId` is `com.intruflare.app`.

To keep existing installed users updatable while migrating to the new package name:

1. Build and ship a **legacy compatibility release** first (same old package id):
   ```bash
   USE_LEGACY_APPLICATION_ID=true flutter build apk --release
   ```
   This produces an APK that still updates installs of `com.example.condo_guardian_app`.

2. Publish a migration notice in-app/backend UI telling users to install the new app listing.

3. Build the **new package** (default behavior, no flag):
   ```bash
   flutter build apk --release
   ```
   This produces `com.intruflare.app`.

4. Keep both tracks available during transition:
   - Legacy track: security fixes and migration prompt only.
   - New track: full feature development.

## Suggested backend contract

### General app API
- `GET /api/status`
- `GET /api/nodes`
- `GET /api/sensors`
- `GET /api/alerts`
- `POST /api/alerts/{id}/acknowledge`
- `POST /api/assistant/query`

### Example `GET /api/status` response
```json
{
  "ok": true,
  "backend": "online",
  "active_alerts": 1,
  "nodes_online": 4,
  "nodes_offline": 0,
  "last_sync": "2026-04-23T09:30:00Z"
}
```

### Example `GET /api/alerts` response
```json
{
  "alerts": [
    {
      "id": "alert_123",
      "title": "Door vibration detected",
      "message": "Forced entry pattern detected at entrance area.",
      "severity": "warning",
      "created_at": "2026-04-23T09:30:00Z",
      "acknowledged": false
    }
  ]
}
```

### Example `POST /api/assistant/query` request
```json
{
  "question_id": "last_alert_reason"
}
```

### Example `POST /api/assistant/query` response
```json
{
  "answer": "The last alert was triggered by the door-force node after abnormal vibration and entry motion were detected at the entrance area."
}
```

## Provisioning contract
The provisioning screen assumes the phone is already connected to the node setup AP.

Suggested setup AP base URL:
- `http://192.168.4.1`

Suggested node endpoint:
- `POST /configure`

Suggested request body:
```json
{
  "wifi_ssid": "CondoWiFi",
  "wifi_password": "secret123",
  "backend_host": "monitor-pc.tailnet.ts.net",
  "backend_port": 8765,
  "node_id": "door_force_01",
  "node_role": "door_force",
  "room_name": "Door Entrance Area"
}
```

Allowed `node_role` values (MVP): `smoke_node1`, `smoke_node2`, `door_force`, `cam_door`.
Allowed `room_name` values (MVP): `Living Room`, `Door Entrance Area`.

Suggested success response:
```json
{
  "success": true,
  "message": "Configuration saved. Rebooting node."
}
```

## Enrollment contract
The enrollment screen captures mobile photos and uploads them one at a time.

Suggested endpoints:
- `POST /api/enroll/start`
- `POST /api/enroll/upload`
- `POST /api/enroll/complete`

### Example `POST /api/enroll/start` request
```json
{
  "full_name": "Steve Villa",
  "user_code": "authorized_01"
}
```

### Example `POST /api/enroll/upload`
- content type: `multipart/form-data`
- fields:
  - `user_code`
  - `capture_source` = `mobile_app`
  - `sample_index`
- file field name:
  - `image`

### Example `POST /api/enroll/complete` request
```json
{
  "user_code": "authorized_01"
}
```

## WebView notes
For MVP, the simplest option is a lightweight login inside the dashboard WebView.

If you later want smoother UX, add a backend bootstrap flow that exchanges the app token for a WebView session cookie.

## Important connection notes
- The app uses `Authorization: Bearer <token>` for API calls if a token is saved in Settings.
- The monitor screen loads whatever URL you place in **Dashboard URL**.
- If you are using Tailscale, use a stable MagicDNS or tailnet hostname instead of a raw changing IP for the backend and dashboard URLs.
- If your backend uses self-signed HTTPS, the WebView and HTTP client may need extra platform configuration.
- The app is written as an Android-first MVP. iOS support may need additional camera and WebView permission work.

## Recommended next backend steps
1. Implement the API routes above.
2. Return JSON with the same field names used by this frontend.
3. Decide whether your dashboard WebView uses its own login or a bootstrap session.
4. Decide whether alerts stay polling-based or upgrade later to websocket/push.
