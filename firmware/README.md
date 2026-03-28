# Firmware Upload Map

Use this map to avoid flashing the wrong sketch.

## Active Mode (HTTP over Wi-Fi)

Flash these sketches:

1. Door-force node:
   - `firmware/http/door_force_http/door_force_http.ino`
2. Smoke node 1:
   - `firmware/http/smoke_node1_http/smoke_node1_http.ino`
3. Smoke node 2:
   - `firmware/http/smoke_node2_http/smoke_node2_http.ino`

Cameras are RTSP IP cameras and do not use ESP32-CAM firmware in active architecture.

## Backend Runtime

Run backend on the Windows host:

- `python backend/run_backend.py`

## Full Instructions

- `docs/README.md`
- `docs/instructions/transport/http_quick_start.md`
- `docs/instructions/transport/http_deployment.md`
- `docs/instructions/camera/rtsp_dual_camera.md`
