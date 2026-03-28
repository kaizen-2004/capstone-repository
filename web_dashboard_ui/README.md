# Monitoring Dashboard UI

React frontend for the Windows local-first monitoring system.

## Runtime Integration

The dashboard is served by the FastAPI backend at `/dashboard`.

- Build command: `npm run build`
- Build output: `web_dashboard_ui/dist`
- Backend route: `/dashboard` and `/dashboard/*`

## Core Features

- Login-protected single-admin access.
- Live alerts/events with acknowledgment workflow.
- Sensor and RTSP camera status monitoring.
- Face enrollment and model training workflow.
- Daily statistics and settings views.

## Architecture Fit

- Sensor transport: HTTP (ESP32-C3 nodes).
- Camera transport: RTSP (indoor + door cameras).
- Core operation: local-first and offline-capable.

## Build

```bash
cd web_dashboard_ui
npm install
npm run build
```

## Development

```bash
cd web_dashboard_ui
npm run dev
```

## Notes

- Backend compatibility APIs are under `/api/ui/*` and `/api/faces/*`.
- Telegram/Tailscale remote integrations are intentionally disabled in core phase.
