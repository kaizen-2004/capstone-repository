# door_force_http

HTTP firmware placeholder for ESP32-C3 door force/IMU node.

Required behavior:

- Wi-Fi connect
- `POST /api/devices/register`
- periodic `POST /api/devices/heartbeat`
- event `POST /api/sensors/event` with `DOOR_FORCE` / `ENTRY_MOTION`
