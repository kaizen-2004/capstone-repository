# Firmware Upload Map

Use this map to avoid flashing the wrong sketch.

## Active Mode (HTTP over Wi-Fi)

Node onboarding/setup AP provisioning is available for active sensor node sketches.

Provisioning contract (sensor nodes):

- Setup AP SSID format: `Thesis-Setup-<chipSuffix>`
- Setup AP base URL: `http://192.168.4.1`
- Endpoint: `POST /configure`
- Required JSON fields: `wifi_ssid`, `wifi_password`, `backend_host`, `backend_port`, `node_id`, `node_role`, `room_name`

Role values accepted by active sensor sketches:

- `door_force_http`: `door_force`
- `smoke_node1_http`: `smoke_node1` (also accepts `smoke` alias)
- `smoke_node2_http`: `smoke_node2` (also accepts `smoke` alias)

The sketches still support compile-time fallback values from the shared header.

Edit this file:

- `firmware/http/common/network_config.h`

Compile-time fallback values:

- `THESIS_WIFI_SSID`
- `THESIS_WIFI_PASSWORD`
- `THESIS_BACKEND_BASE` (example: `http://192.168.1.8:8765`)

Flash these sketches:

1. Door-force node:
   - `firmware/http/door_force_http/door_force_http.ino`
2. Smoke node 1:
   - `firmware/http/smoke_node1_http/smoke_node1_http.ino`
3. Smoke node 2:
   - `firmware/http/smoke_node2_http/smoke_node2_http.ino`
4. Door camera when using ESP32-CAM AI Thinker:
   - `firmware/http/cam_door_esp32cam/cam_door_esp32cam.ino`

For ESP32-CAM door-camera replacement, set `CAMERA_DOOR_RTSP` to `http://<camera-ip>:81/stream` before starting the backend.

## Backend Runtime

Run backend on the Windows host:

- `python backend/run_backend.py`

## Full Instructions

- `docs/README.md`
- `docs/instructions/transport/http_quick_start.md`
- `docs/instructions/transport/http_deployment.md`
- `docs/instructions/camera/rtsp_dual_camera.md`
