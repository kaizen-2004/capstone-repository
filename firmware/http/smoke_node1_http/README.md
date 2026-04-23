# smoke_node1_http

HTTP firmware for ESP32-C3 smoke sensor node 1 with manual Wi-Fi configuration.

Configuration flow:

- Edit shared network config before upload:
  - `firmware/http/common/network_config.h`
  - `THESIS_WIFI_SSID`
  - `THESIS_WIFI_PASSWORD`
  - `THESIS_BACKEND_BASE` (example: `http://192.168.1.8:8765`)
- Flash the node.
- Node connects directly to Wi-Fi STA mode (no setup AP / onboarding endpoint).

Required behavior:

- Wi-Fi connect
- `POST /api/devices/register`
- periodic `POST /api/devices/heartbeat`
- event `POST /api/sensors/event` with `SMOKE_HIGH` / `SMOKE_NORMAL`
