# door_force_http

HTTP firmware for ESP32-C3 door force/IMU node with V380-style provisioning.

Provisioning flow:

- On first boot (or after reset), node starts setup AP `Thesis-Setup-xxxxxx`.
- Use onboarding UI with setup base URL `http://192.168.4.1`.
- Send SSID/password/hostname/backend base through `/api/provision/wifi`.
- Node connects to STA and auto-disables setup AP shortly after successful join.
- Reset provisioning through `/api/provision/reset` (also used by backend reprovision-all).

Useful endpoints:

- `GET /api/provision/info`
- `GET /api/provision/status`
- `GET /api/provision/scan`
- `POST /api/provision/wifi`
- `POST /api/provision/reset`

Required behavior:

- Wi-Fi connect
- `POST /api/devices/register`
- periodic `POST /api/devices/heartbeat`
- event `POST /api/sensors/event` with `DOOR_FORCE` / `ENTRY_MOTION`
