# cam_door_esp32cam

Active ESP32-CAM firmware for replacing `cam_door` with an AI Thinker ESP32-CAM (OV2640).

## Board

- `AI Thinker ESP32-CAM`

## Wi-Fi Configuration

This firmware now uses manual Wi-Fi configuration before upload.

Edit shared network config:

- `firmware/http/common/network_config.h`

Set these values:

- `THESIS_WIFI_SSID`
- `THESIS_WIFI_PASSWORD`
- `THESIS_BACKEND_BASE` (example: `http://192.168.1.8:8765`)

No setup AP / onboarding API is used.

Default camera identity:

- `NODE_ID = "cam_door"`
- `ROOM_NAME = "Door Entrance Area"`

## URLs After Boot

- Stream: `http://<camera-ip>:81/stream`
- Snapshot: `http://<camera-ip>/capture`
- Flash snapshot: `http://<camera-ip>/capture?flash=1`
- Snapshot alias: `http://<camera-ip>/snapshot.jpg?flash=1`
- Control: `http://<camera-ip>/control?cmd=status`

Supported control commands:

- `flash_on`
- `flash_off`
- `flash_pulse`
- `status`

## Backend

Set before running `python backend/run_backend.py`:

```bash
export CAMERA_DOOR_RTSP="http://<camera-ip>:81/stream"
```

This allows the backend to:

- read the live stream as `cam_door`
- trigger bright flash-assisted snapshots on `DOOR_FORCE`
- use `/api/ui/camera/control` for manual flash/status commands

## Upload

```bash
arduino-cli compile -u -p <serial-port> -b esp32:esp32:esp32cam "firmware/http/cam_door_esp32cam"
```
