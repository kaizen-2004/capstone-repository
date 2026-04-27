# IntruFlare Repository Feature Map
_Last updated: 2026-04-27_

## 1) Purpose
This document maps active product features to owning files across:
- backend (`backend/`)
- web dashboard (`web_dashboard_ui/`)
- Flutter mobile app (`condo_guardian_app/`)
- firmware (`firmware/`)
- deployment scripts (`scripts/`, `docs/instructions/deployment/`)
- docs/context (`docs/`)

This is the edit-safety reference for minimal-diff, contract-preserving changes.

---

## 2) Cross-Stack Contracts (Do Not Break)
- Keep monitor route as `<backend>/dashboard/remote/mobile`.
- Preserve API surfaces used by web/mobile:
  - `/api/status`
  - `/api/nodes`
  - `/api/sensors`
  - `/api/alerts`
  - `/api/events`
  - `/api/assistant/query`
  - `/api/enroll/*`
- Preserve node provisioning contract and `POST /configure` payload keys:
  - `wifi_ssid`
  - `wifi_password`
  - `backend_host`
  - `backend_port`
  - `node_id`
  - `node_role`
  - `room_name`
- Keep persistent mobile alert behavior visible/reappearing until user acknowledgment.
- Backend target for remote/Tailscale flows remains `http://100.123.42.91:8765`.

---

## 3) Top-Level Ownership

| Area | Runtime Role | Primary Entry Points |
|---|---|---|
| `backend/` | FastAPI core, event orchestration, storage, camera/sensor services | `backend/app/main.py`, `backend/run_backend.py` |
| `web_dashboard_ui/` | React dashboard and mobile remote web view | `web_dashboard_ui/src/main.tsx`, `web_dashboard_ui/src/app/routes.ts` |
| `condo_guardian_app/` | Flutter mobile companion (monitoring, alerts, enrollment, provisioning) | `condo_guardian_app/lib/main.dart`, `condo_guardian_app/lib/app.dart` |
| `firmware/` | ESP32 HTTP nodes and camera firmware | `firmware/http/*/*.ino`, `firmware/http/common/network_config.h` |
| `scripts/` | local preview and validation helpers | `scripts/preview_full_system.sh` |
| `docs/` | context, process, deployment/instruction references | `docs/context/CURRENT_STATUS.md`, `docs/context/SESSION_BOOTSTRAP.md` |

---

## 4) Backend Feature -> File Map (`backend/`)

### 4.1 App bootstrap and routing
- App lifecycle, router mounting, static dashboard serving:
  - `backend/app/main.py`
- Shared API accessor helpers:
  - `backend/app/api/common.py`

### 4.2 Auth/session/security
- Auth endpoints:
  - `backend/app/api/auth.py`
- Auth guard/token extraction:
  - `backend/app/core/auth.py`
- Password hashing/token/time utilities:
  - `backend/app/core/security.py`

### 4.3 Device/sensor ingestion and node lifecycle
- Register/heartbeat/sensor ingest + camera stream auto-override hook:
  - `backend/app/api/devices.py`
- Persistence model for nodes/sensors/events:
  - `backend/app/db/store.py`

### 4.4 UI/read APIs + runtime settings
- Dashboard/mobile-facing read APIs + live runtime setting application:
  - `backend/app/api/ui.py`
- Request/response schemas:
  - `backend/app/schemas/api.py`

### 4.5 Face enrollment/recognition
- Enrollment endpoints and face profile APIs:
  - `backend/app/api/faces.py`
- Detection/recognition/training pipeline:
  - `backend/app/modules/face_service.py`

### 4.6 Event/alert engine
- Event normalization, cooldowns, alert creation flow:
  - `backend/app/modules/event_engine.py`
- Background policy checks/retention/offline checks:
  - `backend/app/services/supervisor.py`

### 4.7 Camera and fire services
- Camera worker orchestration/snapshots/status:
  - `backend/app/services/camera_manager.py`
- Camera HTTP command/status integration:
  - `backend/app/services/camera_http_control.py`
- Fire model and inference:
  - `backend/app/modules/fire_service.py`

### 4.8 Notifications and remote access
- Push dispatch + VAPID runtime updates:
  - `backend/app/services/notification_dispatcher.py`
- Telegram notifier:
  - `backend/app/services/telegram_notifier.py`
- Remote link (LAN/Tailscale/mDNS) resolution:
  - `backend/app/services/remote_access.py`
- Integrations APIs:
  - `backend/app/api/integrations.py`

### 4.9 Config/test/run
- Env/settings contract:
  - `backend/app/core/config.py`
- Backend run entry:
  - `backend/run_backend.py`
- Baseline tests:
  - `backend/tests/test_api_basics.py`
- Setup/run docs:
  - `backend/README.md`

---

## 5) Web Dashboard Feature -> File Map (`web_dashboard_ui/`)

### 5.1 App shell, routes, auth
- React bootstrap:
  - `web_dashboard_ui/src/main.tsx`
- Router setup:
  - `web_dashboard_ui/src/app/App.tsx`
  - `web_dashboard_ui/src/app/routes.ts`
- Login/session gate:
  - `web_dashboard_ui/src/app/components/AuthGate.tsx`
- Layout/nav/header:
  - `web_dashboard_ui/src/app/components/MainLayout.tsx`
  - `web_dashboard_ui/src/app/components/Sidebar.tsx`
  - `web_dashboard_ui/src/app/components/TopBar.tsx`

### 5.2 Data layer and API client bindings
- Live backend API bindings:
  - `web_dashboard_ui/src/app/data/liveApi.ts`
- Typed mock/fallback domain model:
  - `web_dashboard_ui/src/app/data/mockData.ts`

### 5.3 Pages
- Overview dashboard + export:
  - `web_dashboard_ui/src/app/pages/Dashboard.tsx`
- Live monitoring:
  - `web_dashboard_ui/src/app/pages/LiveMonitoring.tsx`
- Events/alerts and snapshot overlays:
  - `web_dashboard_ui/src/app/pages/EventsAlerts.tsx`
- Sensors/service status:
  - `web_dashboard_ui/src/app/pages/SensorsStatus.tsx`
- Stats/charts:
  - `web_dashboard_ui/src/app/pages/Statistics.tsx`
- Runtime settings + face tools + integrations:
  - `web_dashboard_ui/src/app/pages/Settings.tsx`
- Mobile remote (monitoring-first, advanced collapsed):
  - `web_dashboard_ui/src/app/pages/MobileRemote.tsx`

### 5.4 Push + service worker + styling/build
- Push subscribe/register lifecycle:
  - `web_dashboard_ui/src/app/mobile/push.ts`
- Service worker file:
  - `web_dashboard_ui/public/dashboard-sw.js`
- Theme tokens:
  - `web_dashboard_ui/src/styles/theme.css`
- Build base path:
  - `web_dashboard_ui/vite.config.ts`
- Package scripts/deps:
  - `web_dashboard_ui/package.json`

---

## 6) Flutter App Feature -> File Map (`condo_guardian_app/`)

### 6.1 App startup/shell/navigation
- App bootstrap:
  - `condo_guardian_app/lib/main.dart`
  - `condo_guardian_app/lib/app.dart`
- Tab shell + orchestration:
  - `condo_guardian_app/lib/screens/shell_screen.dart`

### 6.2 Screens
- Home snapshot:
  - `condo_guardian_app/lib/screens/home_screen.dart`
- Monitor WebView (uses `/dashboard/remote/mobile`):
  - `condo_guardian_app/lib/screens/monitor_screen.dart`
- Alerts/events/snapshots:
  - `condo_guardian_app/lib/screens/alerts_screen.dart`
  - `condo_guardian_app/lib/screens/events_screen.dart`
  - `condo_guardian_app/lib/screens/snapshots_screen.dart`
- Enrollment flow:
  - `condo_guardian_app/lib/screens/enrollment_screen.dart`
- Assistant query:
  - `condo_guardian_app/lib/screens/assistant_screen.dart`
- Node provisioning:
  - `condo_guardian_app/lib/screens/provisioning_screen.dart`
- App settings:
  - `condo_guardian_app/lib/screens/settings_screen.dart`

### 6.3 Services/storage/models
- API client/auth headers:
  - `condo_guardian_app/lib/core/network/api_client.dart`
- Local settings store:
  - `condo_guardian_app/lib/core/storage/settings_store.dart`
- Backend domain service:
  - `condo_guardian_app/lib/services/backend_service.dart`
- Alert notifications:
  - `condo_guardian_app/lib/services/alert_notification_service.dart`
  - `condo_guardian_app/lib/services/alert_notification_coordinator.dart`
- Provisioning submitter:
  - `condo_guardian_app/lib/services/provisioning_service.dart`
- DTO models:
  - `condo_guardian_app/lib/models/*.dart`

### 6.4 Native bridge
- Android TTS channel `intruflare/tts`:
  - `condo_guardian_app/android/app/src/main/kotlin/com/intruflare/app/MainActivity.kt`

### 6.5 Flutter dependency surface
- Package deps/config:
  - `condo_guardian_app/pubspec.yaml`

---

## 7) Firmware Feature -> File Map (`firmware/`)

### 7.1 Shared config
- Wi-Fi/backend constants:
  - `firmware/http/common/network_config.h`

### 7.2 Active HTTP nodes
- Smoke node 1:
  - `firmware/http/smoke_node1_http/smoke_node1_http.ino`
- Smoke node 2:
  - `firmware/http/smoke_node2_http/smoke_node2_http.ino`
- Door-force node:
  - `firmware/http/door_force_http/door_force_http.ino`
- Door camera ESP32-CAM:
  - `firmware/http/cam_door_esp32cam/cam_door_esp32cam.ino`

### 7.3 Diagnostics and legacy
- Wi-Fi diagnostic sketch:
  - `firmware/wifi_diag/wifi_diag.ino`
- Legacy archive (non-active by default):
  - `firmware/archive/`

---

## 8) Deployment and Validation Feature -> File Map
- Windows startup and packaging instructions:
  - `docs/instructions/deployment/windows_local_startup.md`
- Full-system local smoke preview:
  - `scripts/preview_full_system.sh`

---

## 9) Docs and Session Context
- Current status:
  - `docs/context/CURRENT_STATUS.md`
- Session bootstrap:
  - `docs/context/SESSION_BOOTSTRAP.md`
- Docs index:
  - `docs/README.md`

---

## 10) End-to-End Operational Flows

### 10.1 Sensor/fire/intrusion flow
1. Firmware sends register/heartbeat/sensor payloads to backend.
2. `backend/app/api/devices.py` ingests and persists via `backend/app/db/store.py`.
3. `backend/app/modules/event_engine.py` normalizes/correlates events and creates alerts.
4. UI/mobile fetch updates via `/api/status`, `/api/events`, `/api/alerts`, `/api/sensors`, `/api/nodes`.
5. Notifications emit through push/telegram services when enabled.

### 10.2 Face enrollment flow
1. Web/mobile enrollment starts via `/api/enroll/*`.
2. Face data handled by `backend/app/api/faces.py` + `backend/app/modules/face_service.py`.
3. Trained templates/profiles are persisted in store.
4. Recognition events later surface through event/alert APIs and snapshots.

### 10.3 Mobile monitor flow
1. Flutter monitor resolves `<backend>/dashboard/remote/mobile`.
2. Web route in `web_dashboard_ui/src/app/routes.ts` serves `MobileRemote`.
3. Backend static mount in `backend/app/main.py` serves dashboard build.

---

## 11) Endpoint Ownership Matrix (Core)

| Endpoint | Backend Owner | Primary Consumers |
|---|---|---|
| `/api/status` | `backend/app/api/ui.py` | web dashboard, Flutter home |
| `/api/nodes` | `backend/app/api/ui.py` | web sensors/status, Flutter home/settings |
| `/api/sensors` | `backend/app/api/ui.py` | web sensors/dashboard, Flutter home |
| `/api/events` | `backend/app/api/ui.py` | web events/live, Flutter events/snapshots |
| `/api/alerts` | `backend/app/api/ui.py` | web alerts, Flutter alerts + notification coordinator |
| `/api/assistant/query` | `backend/app/api/ui.py` | Flutter assistant (and optional web assistant usage) |
| `/api/enroll/*` | `backend/app/api/faces.py` | web settings enrollment, Flutter enrollment |
| `POST /configure` | node firmware HTTP handler | Flutter provisioning service |

---

## 12) Facts, Assumptions, Unknowns

### Facts
- Backend serves dashboard static files from `web_dashboard_ui/dist`.
- Monitor route expectation is `/dashboard/remote/mobile`.
- Provisioning payload keys listed in this map are active compatibility requirements.
- Web and Flutter both consume snapshot overlays with bounding-box payloads.

### Assumptions
- `firmware/archive/` is treated as legacy/non-active unless explicitly requested as active scope.

### Unknowns / Follow-up
- Service worker path alignment should be verified:
  - registration in `web_dashboard_ui/src/app/mobile/push.ts` uses `/dashboard/sw.js`
  - current worker file is `web_dashboard_ui/public/dashboard-sw.js`

---

## 13) Smallest Safe Edit Surfaces
- Runtime behavior toggles and policy updates: `backend/app/api/ui.py`, `backend/app/services/supervisor.py`
- Device ingest or node-heartbeat behavior: `backend/app/api/devices.py`
- Camera stream URL/override logic: `backend/app/services/camera_http_control.py`
- Mobile remote UX-only changes: `web_dashboard_ui/src/app/pages/MobileRemote.tsx`, `web_dashboard_ui/src/styles/theme.css`
- Flutter monitor/provisioning UX: `condo_guardian_app/lib/screens/monitor_screen.dart`, `condo_guardian_app/lib/screens/provisioning_screen.dart`

---

## 14) Validation Checklist for Future Edits
- Backend focused check: run targeted backend tests first (`backend/tests/test_api_basics.py`).
- Web focused check: build dashboard (`npm run build` in `web_dashboard_ui`).
- Flutter focused check: run targeted flutter analysis/test for changed modules.
- Firmware focused check: compile only affected sketch.
- Re-verify contract endpoints and monitor route after any routing/config edits.
