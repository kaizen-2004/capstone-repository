# smoke_node2_http

HTTP firmware placeholder for ESP32-C3 smoke sensor node 2.

Required behavior:

- Wi-Fi connect
- `POST /api/devices/register`
- periodic `POST /api/devices/heartbeat`
- event `POST /api/sensors/event` with `SMOKE_HIGH` / `SMOKE_NORMAL`
