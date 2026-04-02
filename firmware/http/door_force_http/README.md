# door_force_http

HTTP firmware placeholder for ESP32-C3 door force/IMU node.

Quick setup for current LAN backend:

- Set `WIFI_SSID` and `WIFI_PASSWORD` in `door_force_http.ino`
- Set `BACKEND_BASE` to `http://192.168.1.8:8765` (API base only, no `/dashboard`)
- Firmware starts with moderate TX power, escalates on repeated join failures, then settles to stable runtime TX (`WIFI_POWER_11dBm` preferred, `8.5dBm` fallback)
- Flash firmware to ESP32-C3 and open serial monitor at 115200
- Expected serial logs include `[BOOT]`, `[WiFi] connecting`, `[WiFi] connected`, and `[HTTP] event=...`

Required behavior:

- Wi-Fi connect
- `POST /api/devices/register`
- periodic `POST /api/devices/heartbeat`
- event `POST /api/sensors/event` with `DOOR_FORCE` / `ENTRY_MOTION`
