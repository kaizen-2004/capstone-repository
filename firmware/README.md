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
