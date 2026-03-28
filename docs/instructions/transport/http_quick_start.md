# HTTP Quick Start (ESP32-C3 Nodes)

Use this for the fastest core deployment path.

## 1. Node Roles

- `smoke_node1` -> `firmware/http/smoke_node1_http/`
- `smoke_node2` -> `firmware/http/smoke_node2_http/`
- `door_force` -> `firmware/http/door_force_http/`

## 2. Backend Setup

```bash
python -m venv .venv
# activate venv
pip install -r requirements.txt
python backend/run_backend.py
```

Backend ingest endpoint:

- `http://<PC_IP>:8765/api/sensors/event`

## 3. Node Boot Flow

Each node should:

1. Connect to Wi-Fi.
2. Register to backend via `POST /api/devices/register`.
3. Send heartbeat via `POST /api/devices/heartbeat`.
4. Send events via `POST /api/sensors/event`.

## 4. Validation

- Open `http://127.0.0.1:8765/dashboard`.
- Login as admin.
- Confirm nodes appear in Sensors & Nodes.
- Trigger smoke/door event and confirm alert generation.
