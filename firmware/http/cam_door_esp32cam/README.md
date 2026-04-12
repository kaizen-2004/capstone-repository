# cam_door_esp32cam

Active ESP32-CAM firmware for replacing `cam_door` with an AI Thinker ESP32-CAM (OV2640).

## Board

- `AI Thinker ESP32-CAM`

## Provisioning Flow (SoftAP + NVS)

This firmware supports Wi-Fi onboarding without reflashing when network changes.

1. Boot node.
2. If saved Wi-Fi credentials are missing/invalid, setup AP starts (open network):
   - SSID format: `Thesis-Setup-XXXXXX`
   - API base: `http://192.168.4.1`
3. Send credentials to `POST /api/provision/wifi`.
4. Node saves credentials in NVS and switches to STA.
5. Check `GET /api/provision/status` for connected IP/mDNS.

Setup AP timeout:

- 10 minutes, then AP closes automatically.
- Call `POST /api/provision/reset` to clear saved Wi-Fi and force setup AP mode.
- After reset, setup AP mode stays preferred across reboot until new Wi-Fi credentials are provisioned.

Optional compile-time fallbacks still exist (`WIFI_SSID`, `WIFI_PASSWORD`, `WIFI_HOSTNAME`) but normal operation should use provisioning.

Default camera identity:

- `NODE_ID = "cam_door"`
- `ROOM_NAME = "Door Entrance Area"`

## URLs After Boot

- Stream: `http://<camera-ip>:81/stream`
- Snapshot: `http://<camera-ip>/capture`
- Flash snapshot: `http://<camera-ip>/capture?flash=1`
- Snapshot alias: `http://<camera-ip>/snapshot.jpg?flash=1`
- Control: `http://<camera-ip>/control?cmd=status`

Provisioning endpoints:

- `GET /api/provision/info`
- `GET /api/provision/status`
- `GET /api/provision/scan`
- `POST /api/provision/wifi`
- `POST /api/provision/reset`

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
