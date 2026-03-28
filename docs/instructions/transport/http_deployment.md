# HTTP Deployment Guide

## Architecture

`ESP32-C3 nodes -> HTTP APIs -> FastAPI backend -> fusion -> alerts/dashboard`

## Required APIs

- `POST /api/devices/register`
- `POST /api/devices/heartbeat`
- `POST /api/sensors/reading`
- `POST /api/sensors/event`

## Minimal Event Payload

```json
{
  "node_id": "smoke_node1",
  "event": "SMOKE_HIGH",
  "location": "Living Room",
  "value": 0.82,
  "details": {
    "threshold": 0.70
  }
}
```

## Failure Handling

- Node heartbeat timeout triggers `NODE_OFFLINE` event and alert.
- Camera disconnect state appears in dashboard and auto-reconnect is attempted.
- Internet loss does not stop local monitoring/alerts.

## Security Notes

- Keep backend on local network.
- Use strong admin password via env vars.
- Do not expose backend publicly without secure overlay (Tailscale in later phase).
